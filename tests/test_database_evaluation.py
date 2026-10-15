"""Database-focused acceptance experiments, with recorded observations.

Every app fixture owns fresh SQL/Mongo databases. Faults are scoped to those
clients; no live services are stopped and no production records are used.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import csv
import hashlib
import json
import math
import statistics
import threading
import time
import pytest
from pymongo.collection import Collection
from pymongo.errors import AutoReconnect, WriteError
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from test_api import app, Browser
from test_admin import administrator
from test_imports import row
from backend.models import db, User, Dish, Content, FoodPlace, Favourite, PopulationRun, now
from backend.mongo import community_db, next_id, ratings
from backend.database_lab import integrity_audit
from backend.population import seed_coursework, counts, VERSION


@pytest.fixture(autouse=True)
def engine_evidence(app, record_property):
    with app.app_context():
        dialect = db.engine.dialect.name
        version = db.session.scalar(text('SELECT sqlite_version()' if dialect == 'sqlite' else 'SELECT VERSION()'))
        with db.engine.connect() as connection:
            isolation = connection.get_isolation_level()
        mongo = community_db()
        record_property('engines', {'sql': version, 'mongo': mongo.command('buildInfo')['version'],
            'sqlIsolation': isolation, 'mongoTopology': 'replica set' if mongo.command('hello').get('setName') else 'standalone',
            'mongoWriteConcern': mongo.content.write_concern.document or 'server default'})


def evidence(record_property, area, invariant, observed):
    record_property('area', area)
    record_property('invariant', invariant)
    record_property('observed', observed)


def concurrent_requests(app, user_id, method, path, bodies, workers=6):
    # Each worker gets its own cookie jar, Flask request and SQL session.
    clients = [Browser(app) for _ in bodies]
    for browser in clients:
        with browser.client.session_transaction() as session:
            session['user_id'] = user_id
    gate = threading.Barrier(workers)
    def send(pair):
        browser, body = pair
        gate.wait(timeout=15)
        response = browser.send(method, path, body)
        return response.status_code, response.json
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(send, zip(clients, bodies)))


def assert_clean():
    audit = integrity_audit()
    assert not any(audit['mongoReferences'].values()), audit
    assert not any(r['orphans'] for r in audit['sqlForeignKeys']), audit
    assert audit['duplicateVoteGroups'] == audit['duplicateSourceIdentities'] == 0


def test_mongo_lifecycle_and_embedded_atomicity(app, record_property):
    owner, reader = Browser(app, 'owner'), Browser(app, 'reader')
    review = owner.review()
    thread = owner.send('POST', '/api/content', {'kind': 'thread', 'placeId': 1, 'title': 'Question', 'text': 'Lunch?'}).json['content']['id']
    reply = reader.send('POST', '/api/content', {'kind': 'comment', 'placeId': 1, 'threadId': thread, 'text': 'Try rice.'}).json['content']['id']
    assert reader.send('PATCH', f'/api/content/{review}', {'title':'Other', 'text':'Edit', 'rating':1}).status_code == 403
    assert owner.send('PATCH', f'/api/content/{review}', {'title':'Revised', 'text':'Revised', 'rating':3, 'dishes':[{'id':2, 'feedback':'Good'}]}).status_code == 200
    with app.app_context():
        mongo = community_db()
        saved = mongo.content.find_one({'_id':review})
        with pytest.raises(WriteError) as invalid:
            mongo.content.update_one({'_id':review}, {'$set': {'rating':6, 'body':'Must not persist', 'dishes':[]}})
        assert invalid.value.code == 121
        assert mongo.content.find_one({'_id':review}) == saved
        assert ratings([1])[0]['rating'] == 3
        assert db.session.scalar(select(func.count()).select_from(Content)) == 0
    assert owner.send('DELETE', f'/api/content/{thread}').status_code == 200
    ids = {c['id'] for c in reader.client.get('/api/content?place_id=1').json['content']}
    assert review in ids and thread not in ids and reply not in ids
    assert reader.send('PUT', f'/api/content/{reply}/upvote').status_code == 404
    assert owner.send('DELETE', f'/api/content/{review}').status_code == 200
    with app.app_context():
        assert mongo.content.count_documents({}) == 3  # identities retained
        assert ratings([1]) == []
        assert_clean()
    evidence(record_property, 'MongoDB operations', 'Validated document updates are atomic; ownership, aggregation and soft-delete visibility agree.',
        {'documentsRetained':3, 'visibleAfterRemoval':0, 'invalidUpdateCode':121, 'legacySqlContentRows':0})


@pytest.mark.parametrize('reference', ['authors','places','dishLinks','threadLinks','votes','reports'])
def test_cross_database_audit_detects_each_broken_reference(app, record_property, reference):
    owner = Browser(app, 'owner')
    review = owner.review()
    with app.app_context():
        mongo = community_db()
        assert_clean()
        if reference == 'authors': mongo.content.update_one({'_id':review}, {'$set':{'author_id':999999}})
        elif reference == 'places': mongo.content.update_one({'_id':review}, {'$set':{'place_id':999999}})
        elif reference == 'dishLinks': mongo.content.update_one({'_id':review}, {'$set':{'dishes':[{'dish_id':4,'feedback':None}]}})
        elif reference == 'threadLinks':
            mongo.content.insert_one({'_id':next_id('content'),'kind':'comment','place_id':1,'author_id':owner.user['id'],
                'body':'Invalid parent','thread_id':review,'created_at':now(),'updated_at':now(),'removed_at':None,'dishes':[]})
        elif reference == 'votes': mongo.upvotes.insert_one({'user_id':owner.user['id'],'content_id':999999,'voted_at':now()})
        else: mongo.reports.insert_one({'_id':1,'reporter_id':999999,'content_id':review,'reason':'Test','status':'open','created_at':now()})
        found = integrity_audit()['mongoReferences']
        assert found[reference] == 1, found
    evidence(record_property, 'Cross-database behaviour', 'Reconciliation reports an out-of-band broken '+reference+' reference.', found)


def test_archived_sql_place_keeps_references_but_hides_mongo_content(app, record_property):
    owner, admin = Browser(app,'owner'), administrator(app)
    cid = owner.review()
    assert admin.send('DELETE','/api/admin/establishments/1').status_code == 200
    assert owner.client.get('/api/establishments/1').status_code == 404
    assert owner.client.get('/api/content?place_id=1').status_code == 404
    assert owner.client.get('/api/content').json['content'] == []
    assert owner.send('PATCH', f'/api/content/{cid}', {'title':'x','text':'x','rating':1}).status_code == 404
    with app.app_context():
        assert db.session.get(FoodPlace,1) is not None
        assert community_db().content.find_one({'_id':cid}) is not None
        assert_clean()
    evidence(record_property, 'Cross-database behaviour', 'SQL soft archive hides community access while retaining valid SQL/Mongo references.', {'retained':True,'publicRead':404,'edit':404,'orphans':0})


def test_simultaneous_favourite_put_is_idempotent(app, record_property):
    owner = Browser(app,'owner')
    statuses = []
    for place in (1,2,3,4):
        replies = concurrent_requests(app, owner.user['id'], 'PUT', f'/api/favourites/{place}', [None]*6)
        statuses.extend(code for code,_ in replies)
        assert all(code == 200 for code,_ in replies), replies
    with app.app_context():
        saved = db.session.scalar(select(func.count()).select_from(Favourite))
        assert saved == 4
        assert_clean()
    evidence(record_property, 'Concurrency and recovery', 'Six concurrent PUT requests per user/place all succeed and retain one favourite per pair.',
        {'workers':6,'requests':24,'httpStatuses':dict(Counter(statuses)),'storedPairs':saved})


def test_simultaneous_votes_and_content_ids(app, record_property):
    owner = Browser(app,'owner')
    cid = owner.review()
    replies = concurrent_requests(app, owner.user['id'], 'PUT', f'/api/content/{cid}/upvote', [None]*24)
    assert all(code == 200 for code,_ in replies), replies
    payload = {'kind':'thread','placeId':1,'title':'Concurrent','text':'Independent request'}
    created = concurrent_requests(app, owner.user['id'], 'POST','/api/content',[payload]*24)
    assert all(code == 201 for code,_ in created), created
    ids = [body['content']['id'] for _,body in created]
    assert len(set(ids)) == 24
    with app.app_context():
        assert community_db().upvotes.count_documents({}) == 1
        assert community_db().content.count_documents({}) == 25
        assert_clean()
    evidence(record_property, 'Concurrency and recovery', 'Atomic Mongo counters allocate distinct IDs and the compound unique index retains one vote per pair.',
        {'workers':6,'voteRequests':24,'storedVotes':1,'createRequests':24,'uniqueCreatedIds':len(set(ids))})


def test_simultaneous_report_resolution_has_one_winner(app, record_property):
    owner, admin = Browser(app,'owner'), administrator(app)
    cid = owner.review()
    rid = owner.send('POST',f'/api/content/{cid}/reports',{'reason':'Test'}).json['id']
    bodies = [{'status':'resolved' if i%2 else 'dismissed','note':f'Decision {i}'} for i in range(6)]
    replies = concurrent_requests(app, admin.user['id'], 'PATCH', f'/api/admin/reports/{rid}', bodies)
    statuses = Counter(code for code,_ in replies)
    assert statuses == {200:1,409:5}, replies
    winner = next(body for body,(code,_) in zip(bodies,replies) if code == 200)
    with app.app_context():
        saved = community_db().reports.find_one({'_id':rid})
        assert saved['status'] == winner['status'] and saved['resolution_note'] == winner['note']
        assert saved['resolved_by_id'] == admin.user['id']
    evidence(record_property, 'Concurrency and recovery', 'Conditional status=open update permits exactly one moderation decision.', {'workers':6,'httpStatuses':dict(statuses),'winningDecisionRetained':True})


@pytest.mark.parametrize('point', ['before_write','after_write_before_ack'])
def test_population_resumes_after_partial_mongo_failure(app, tmp_path, monkeypatch, record_property, point):
    source = tmp_path / 'source.csv'
    record = row()
    with source.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=record); writer.writeheader(); writer.writerow(record)
    with app.app_context():
        mongo = community_db()
        original = Collection.insert_one
        calls = 0
        def fail_once(collection, document, *args, **kwargs):
            nonlocal calls
            if collection.full_name == mongo.content.full_name:
                calls += 1
                if calls == 18:
                    if point == 'after_write_before_ack': original(collection,document,*args,**kwargs)
                    raise AutoReconnect('Injected failure in disposable test database')
            return original(collection,document,*args,**kwargs)
        with monkeypatch.context() as fault:
            fault.setattr(Collection,'insert_one',fail_once)
            with pytest.raises(AutoReconnect): seed_coursework(source)
        partial = counts()
        assert partial['mongo']['content'] == (17 if point == 'before_write' else 18)
        assert db.session.get(PopulationRun,VERSION+':sql') is not None
        assert partial['sql']['discovery_event'] == 300
        kept = mongo.content.find_one({})['_id']
        mongo.content.update_one({'_id':kept},{'$set':{'body':'Preserved manual edit'}})
        resumed = seed_coursework(source)
        assert resumed['after']['mongo'] == {'content':720,'upvotes':600,'reports':20}
        assert resumed['after']['sql'] == partial['sql']
        assert mongo.content.find_one({'_id':kept})['body'] == 'Preserved manual edit'
        repeated = seed_coursework(source)
        assert all(n == 0 for rows in repeated['added'].values() for n in rows.values())
        assert_clean()
    evidence(record_property, 'Concurrency and recovery', 'A committed SQL phase and partial Mongo phase resume without duplicates or overwriting edits.',
        {'injectedAt':point,'partialDocuments':partial['mongo']['content'],'recovered':resumed['after']['mongo'],'repeatAdded':0,'sqlRowsUnchangedOnResume':True})


def test_failure_after_content_commit_is_detectably_ambiguous(app, monkeypatch, record_property):
    owner=Browser(app,'owner')
    import backend.community as community
    payload={'kind':'thread','placeId':1,'title':'Ambiguous acknowledgement','text':'Test request'}
    def disconnected(_): raise AutoReconnect('Injected response read failure')
    with monkeypatch.context() as fault:
        fault.setattr(community,'serialize',disconnected)
        response=owner.send('POST','/api/content',payload)
    assert response.status_code == 503
    visible=owner.client.get('/api/content?place_id=1').json['content']
    assert len(visible) == 1
    with app.app_context(): assert_clean()
    evidence(record_property, 'Concurrency and recovery', 'A 503 after a Mongo commit must not be described as rollback; read-back reveals the committed post.',
        {'httpStatus':503,'documentsCommitted':1,'readAfterRecovery':200,'automaticPostRetrySafe':False})


def test_sql_failure_blocks_mongo_write_then_recovers(app, monkeypatch, record_property):
    owner=Browser(app,'owner')
    from sqlalchemy.orm import Session
    original=Session.get
    def failed(session,entity,*args,**kwargs):
        if entity is FoodPlace: raise OperationalError('injected',{},Exception('test SQL unavailable'))
        return original(session,entity,*args,**kwargs)
    payload={'kind':'thread','placeId':1,'title':'Recovery','text':'Retry after restoring SQL'}
    with monkeypatch.context() as fault:
        fault.setattr(Session,'get',failed)
        response=owner.send('POST','/api/content',payload)
    assert response.status_code == 503
    with app.app_context(): assert community_db().content.count_documents({}) == 0
    assert owner.send('POST','/api/content',payload).status_code == 201
    with app.app_context():
        assert community_db().content.count_documents({}) == 1
        assert_clean()
    evidence(record_property, 'Cross-database behaviour', 'Failed SQL reference lookup prevents Mongo insert; restored SQL allows the request.', {'failureStatus':503,'writesDuringFailure':0,'retryStatus':201})


def distribution(samples):
    ordered=sorted(samples)
    return {'samplesMs':[round(v,4) for v in samples],'medianMs':round(statistics.median(samples),4),
            'p95Ms':round(ordered[math.ceil(.95*len(ordered))-1],4),'minMs':round(min(samples),4),'maxMs':round(max(samples),4)}


def test_real_disconnect_rolls_back_sql_and_preserves_acknowledged_mongo_write(app, record_property):
    from pymongo import MongoClient
    from backend.models import Area
    owner=Browser(app,'owner')
    cid=owner.review()
    with app.app_context():
        with db.engine.connect() as conn:
            conn.begin()
            conn.execute(Area.__table__.insert().values(area_name='Uncommitted disconnect probe'))
            # Closing an actual connection with an open transaction rolls back.
        db.session.remove()
        db.engine.dispose()
        assert db.session.scalar(select(func.count()).select_from(Area).where(Area.area_name=='Uncommitted disconnect probe')) == 0
        separate=MongoClient(app.config['MONGODB_URI'],serverSelectionTimeoutMS=4000)
        try:
            assert separate[app.config['MONGODB_DATABASE']].content.find_one({'_id':cid})['body']=='Really enjoyed it.'
        finally:
            separate.close()
        assert_clean()
    evidence(record_property, 'Concurrency and recovery', 'Real SQL connection closure rolls back uncommitted work; an independent Mongo client reads an acknowledged write.',
        {'sqlUncommittedRowsAfterReconnect':0,'mongoAcknowledgedDocumentsRead':1,'databaseProcessRestarted':False})


def test_recorded_evaluation_access_and_stale_detection(app, tmp_path, record_property):
    from backend.evaluation import source_fingerprint
    admin, reader=administrator(app), Browser(app,'reader')
    path=tmp_path/'evidence.json'
    app.config['DATABASE_EVALUATION_FILE']=str(path)
    assert reader.client.get('/api/admin/database-evaluation').status_code == 403
    assert app.test_client().get('/api/admin/database-evaluation').status_code == 401
    assert admin.client.get('/api/admin/database-evaluation').json['status']=='not_run'
    path.write_text(json.dumps({'formatVersion':1,'sourceSha256':source_fingerprint(),'experiments':[]}),encoding='utf-8')
    assert admin.client.get('/api/admin/database-evaluation').json['currentSource'] is True
    path.write_text(json.dumps({'formatVersion':1,'sourceSha256':'old','experiments':[]}),encoding='utf-8')
    assert admin.client.get('/api/admin/database-evaluation').json['status']=='stale'
    evidence(record_property, 'Evidence integrity', 'Recorded results are admin-only and stale/missing results cannot masquerade as current measurements.',
        {'guest':401,'normalUser':403,'missing':'not_run','oldSource':'stale'})


def paired_benchmark(indexed, scan):
    expected=indexed()
    assert scan() == expected
    for _ in range(3): indexed(); scan()
    samples={'indexed':[],'scan':[]}
    for repetition in range(20):
        for name,query in ([('indexed',indexed),('scan',scan)] if repetition%2 == 0 else [('scan',scan),('indexed',indexed)]):
            start=time.perf_counter_ns(); rows=query(); elapsed=(time.perf_counter_ns()-start)/1e6
            assert rows == expected
            samples[name].append(elapsed)
    return {'warmupsPerVariant':3,'repetitionsPerVariant':20,'order':'alternating paired order','resultRows':len(expected),
        'resultSha256':hashlib.sha256(json.dumps(expected,default=str).encode()).hexdigest(),
        **{name:distribution(values) for name,values in samples.items()}}


def test_controlled_sql_index_benchmark(app, record_property):
    with app.app_context():
        # Same real dish table, same connection, rows and projection. No index is
        # dropped; hints choose scan/index on this disposable database only.
        db.session.execute(Dish.__table__.insert(),[{'place_id':1 if i%300==0 else 2+i%5,'dish_name':f'Benchmark {i}', 'price':1+i%97} for i in range(30000)])
        db.session.commit()
        dialect=db.engine.dialect.name
        if dialect == 'sqlite': indexed_hint='INDEXED BY ix_dish_place_id'; scan_hint='NOT INDEXED'; explain='EXPLAIN QUERY PLAN '
        else: indexed_hint='FORCE INDEX (ix_dish_place_id)'; scan_hint='IGNORE INDEX (ix_dish_place_id, uq_dish_source, PRIMARY)'; explain='EXPLAIN FORMAT=JSON '
        suffix=' WHERE place_id=1 AND is_available=1 ORDER BY dish_id LIMIT 20'
        indexed_sql='SELECT dish_id, price FROM dish '+indexed_hint+suffix
        scan_sql='SELECT dish_id, price FROM dish '+scan_hint+suffix
        with db.engine.connect() as conn:
            run=lambda query: [list(r) for r in conn.execute(text(query)).all()]
            result=paired_benchmark(lambda:run(indexed_sql),lambda:run(scan_sql))
            result.update({'datasetRows':conn.scalar(select(func.count()).select_from(Dish)), 'indexedSql':indexed_sql, 'scanSql':scan_sql,
                'indexedPlan':run(explain+indexed_sql),'scanPlan':run(explain+scan_sql), 'cache':'warm; no server cache flush',
                'optimizerDefaultPlan':run(explain+'SELECT dish_id, price FROM dish'+suffix)})
            if dialect != 'sqlite':
                # Executed, untimed diagnostic samples, separate from timed pairs.
                # Retain real r_rows/r_loops instead of presenting EXPLAIN estimates as work.
                result['indexedExecution'] = json.loads(conn.scalar(text('ANALYZE FORMAT=JSON '+indexed_sql)))
                result['scanExecution'] = json.loads(conn.scalar(text('ANALYZE FORMAT=JSON '+scan_sql)))
        assert 'ix_dish_place_id' in json.dumps(result['indexedPlan'])
    evidence(record_property, 'Controlled benchmarks', 'Indexed and forced-scan SQL variants return identical ordered rows under the same workload.',result)


def test_controlled_mongo_index_benchmark(app, record_property):
    owner=Browser(app,'owner')
    with app.app_context():
        mongo=community_db(); stamp=now()
        mongo.content.insert_many([{'_id':i+1,'kind':'review','place_id':1 if i%300==0 else 2+i%5,
            'author_id':owner.user['id'],'title':'Benchmark','body':'Deterministic synthetic workload','rating':1+i%5,
            'created_at':stamp,'updated_at':stamp,'removed_at':None,'removed_by_id':None,'dishes':[]} for i in range(30000)])
        query={'place_id':1,'removed_at':None,'kind':'review','_id':{'$gt':0}}
        def run(hint): return list(mongo.content.find(query,{'_id':1,'rating':1}).sort('_id',1).limit(20).hint(hint))
        result=paired_benchmark(lambda:run('place_feed'),lambda:run({'$natural':1}))
        def explain(hint):
            plan=mongo.command('explain', {'find':'content','filter':query,'projection':{'_id':1,'rating':1},'sort':{'_id':1},'limit':20,'hint':hint},verbosity='executionStats')
            stats=plan['executionStats']
            return {'returned':stats['nReturned'],'keysExamined':stats['totalKeysExamined'],'documentsExamined':stats['totalDocsExamined'], 'winningPlan':plan['queryPlanner']['winningPlan']}
        result.update({'datasetRows':30000,'query':query,'projection':{'_id':1,'rating':1},'limit':20,'sort':{'_id':1},
            'indexedPlan':explain('place_feed'),'scanPlan':explain({'$natural':1}),'cache':'warm; no server cache flush'})
        assert result['indexedPlan']['documentsExamined'] < result['scanPlan']['documentsExamined']
        assert result['indexedPlan']['returned'] == result['scanPlan']['returned'] == 20
    evidence(record_property, 'Controlled benchmarks', 'Same Mongo feed query/results; executionStats measures document work for index versus collection scan.',result)
