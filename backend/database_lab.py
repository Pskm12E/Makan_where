"""Administrator-only, fixed evidence queries. Never accepts arbitrary SQL."""
import copy
import hashlib
import hmac
import secrets
from datetime import datetime
from uuid import uuid4
from flask import jsonify
from sqlalchemy import and_, func, inspect, select, text
from sqlalchemy.exc import DBAPIError
from pymongo.errors import WriteError, DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash
from .models import db, Area, FoodPlace, Dish, User, Favourite, PopulationRun, now
from .mongo import community_db, VALIDATORS, rating_pipeline
from .services import authenticated

LIVE_SQL = {'area', 'category', 'cuisine', 'place_cuisine', 'food_place', 'dish', 'user', 'favourite', 'discovery_event', 'population_run', 'tag', 'place_tag', 'menu_publication', 'menu_entry'}
VIEW_SQL = '''SELECT p.place_id, p.place_name, COUNT(d.dish_id) AS available_dishes,
MIN(d.price) AS starting_price, AVG(d.price) AS average_price
FROM food_place p LEFT JOIN catalogue_effective_menu d ON d.place_id = p.place_id AND d.is_available = 1
WHERE p.archived_at IS NULL GROUP BY p.place_id, p.place_name'''


def install_views():
    from .catalogue_design import EFFECTIVE_MENU_SQL
    with db.engine.begin() as connection:
        connection.execute(text('DROP VIEW IF EXISTS catalogue_menu_summary'))
        connection.execute(text('DROP VIEW IF EXISTS catalogue_effective_menu'))
        connection.execute(text('CREATE VIEW catalogue_effective_menu AS ' + EFFECTIVE_MENU_SQL))
        connection.execute(text('CREATE VIEW catalogue_menu_summary AS ' + VIEW_SQL))


def integrity_audit():
    """Check every live SQL FK, including composite references and nullable fields."""
    orphan_checks = []
    for name in sorted(LIVE_SQL):
        table = db.metadata.tables[name]
        for constraint in table.foreign_key_constraints:
            elements = list(constraint.elements)
            target = elements[0].column.table
            join = and_(*(e.parent == e.column for e in elements))
            nonnull = and_(*(e.parent.is_not(None) for e in elements))
            total = db.session.scalar(select(func.count()).select_from(table.outerjoin(target, join)).where(nonnull, elements[0].column.is_(None)))
            orphan_checks.append({'reference': f'{name} → {target.name}', 'orphans': total})
    duplicate_query = select(FoodPlace.source_name, FoodPlace.source_id, func.count().label('count')).where(
        FoodPlace.source_name.is_not(None), FoodPlace.source_id.is_not(None)).group_by(FoodPlace.source_name, FoodPlace.source_id).having(func.count() > 1)
    potential = select(FoodPlace.place_name, FoodPlace.address, func.count().label('count')).where(FoodPlace.address != '').group_by(
        FoodPlace.place_name, FoodPlace.address).having(func.count() > 1)
    users = set(db.session.scalars(select(User.user_id)))
    places = set(db.session.scalars(select(FoodPlace.place_id)))
    dish_places = dict(db.session.execute(select(Dish.dish_id, Dish.place_id)).all())
    documents = list(community_db().content.find({}, {'author_id': 1, 'place_id': 1, 'kind': 1, 'thread_id': 1, 'dishes': 1, 'removed_by_id': 1}))
    ids = {c['_id']: c for c in documents}
    reference_errors = {'authors': 0, 'places': 0, 'dishLinks': 0, 'threadLinks': 0, 'votes': 0, 'reports': 0}
    for c in documents:
        reference_errors['authors'] += c['author_id'] not in users or (c.get('removed_by_id') is not None and c['removed_by_id'] not in users)
        reference_errors['places'] += c['place_id'] not in places
        dish_ids = [d['dish_id'] for d in c['dishes']]
        reference_errors['dishLinks'] += len(dish_ids) != len(set(dish_ids)) or any(dish_places.get(d) != c['place_id'] for d in dish_ids)
        if c['kind'] == 'comment':
            parent = ids.get(c.get('thread_id'), {})
            reference_errors['threadLinks'] += parent.get('kind') != 'thread' or parent.get('place_id') != c['place_id']
    for v in community_db().upvotes.find({}, {'user_id': 1, 'content_id': 1}):
        reference_errors['votes'] += v['user_id'] not in users or v['content_id'] not in ids
    for r in community_db().reports.find({}, {'reporter_id': 1, 'content_id': 1, 'resolved_by_id': 1}):
        reference_errors['reports'] += r['reporter_id'] not in users or r['content_id'] not in ids or (r.get('resolved_by_id') is not None and r['resolved_by_id'] not in users)
    duplicate_votes = list(community_db().upvotes.aggregate([{'$group': {'_id': {'u': '$user_id', 'c': '$content_id'}, 'n': {'$sum': 1}}}, {'$match': {'n': {'$gt': 1}}}, {'$count': 'groups'}]))
    return {'sqlForeignKeys': orphan_checks, 'duplicateSourceIdentities': len(list(db.session.execute(duplicate_query))),
        'potentialSameNameAddress': [dict(r) for r in db.session.execute(potential.limit(20)).mappings()],
        'potentialDuplicateNote': 'Same name/address is a review candidate, not proof of duplication. Separate OSM nodes/ways and branches may be legitimate; no automatic deletion.',
        'mongoReferences': reference_errors, 'duplicateVoteGroups': duplicate_votes[0]['groups'] if duplicate_votes else 0,
        'boundary': 'MongoDB cannot enforce a foreign key into SQL. Application checks, soft deletion and this reconciliation audit cover that boundary; no cross-engine ACID transaction is claimed.'}


def constraint_probes():
    results = []
    # Each probe uses its own rollback-only SQL transaction. No live records change.
    with db.engine.connect() as conn:
        def sql_probe(name, setup, invalid, accepted_codes):
            trans = conn.begin()
            try:
                setup(conn)
                savepoint = conn.begin_nested()
                try:
                    invalid(conn)
                    results.append({'check': name, 'passed': False, 'result': 'Database unexpectedly accepted invalid data.'})
                except DBAPIError as error:
                    # MariaDB CHECK (4025) can map to OperationalError rather
                    # than IntegrityError. Check exact driver codes, so an
                    # unrelated syntax/connection failure cannot count as PASS.
                    code = getattr(error.orig, 'sqlite_errorcode', None)
                    if code is None and error.orig.args:
                        code = error.orig.args[0]
                    results.append({'check': name, 'passed': code in accepted_codes,
                        'result': f'Database rejected the write with error code {code}.', 'errorType': type(error.orig).__name__})
                finally:
                    savepoint.rollback()
            finally:
                trans.rollback()
        marker = 'probe_' + uuid4().hex
        holder = {}
        def add_area(c):
            holder['id'] = c.execute(Area.__table__.insert().values(area_name=marker)).inserted_primary_key[0]
        sql_probe('PRIMARY KEY: duplicate area_id', add_area,
            lambda c: c.execute(Area.__table__.insert().values(area_id=holder['id'], area_name=marker + '_other')), {1062, 1555})
        sql_probe('UNIQUE: duplicate area name', add_area,
            lambda c: c.execute(Area.__table__.insert().values(area_name=marker)), {1062, 2067})
        missing = conn.scalar(select(func.max(FoodPlace.place_id))) or 0
        conn.rollback()
        sql_probe('FOREIGN KEY: dish with missing place', lambda c: None,
            lambda c: c.execute(Dish.__table__.insert().values(place_id=missing + 100000, dish_name=marker, price=1)), {1452, 1216, 787})
        place_id = conn.scalar(select(FoodPlace.place_id).limit(1))
        conn.rollback()
        if place_id:
            sql_probe('CHECK: negative dish price', lambda c: None,
                lambda c: c.execute(Dish.__table__.insert().values(place_id=place_id, dish_name=marker, price=-1)), {4025, 3819, 275})
        sql_probe('NOT NULL: area name', lambda c: None,
            lambda c: c.execute(Area.__table__.insert().values(area_name=None)), {1048, 1299})
    mongo = community_db()
    # Validators/indexes copied from LIVE metadata, tested on a private disposable collection.
    name = 'lab_probe_' + uuid4().hex
    options = mongo.content.options()
    collection = mongo.create_collection(name, validator=options.get('validator', {}), validationAction='error')
    valid = {'_id': 1, 'kind': 'review', 'author_id': 1, 'place_id': 1, 'body': 'Disposable validator probe',
             'title': 'Probe', 'rating': 4, 'created_at': now(), 'updated_at': now(),
             'removed_at': None, 'removed_by_id': None, 'dishes': []}
    try:
        collection.insert_one(valid)
        for label, item, expected in [
            ('MongoDB _id unique', valid, 11000),
            ('MongoDB review rating 1–5', {**valid, '_id': 2, 'rating': 6}, 121),
            ('MongoDB subtype needs rating', {k: v for k, v in {**valid, '_id': 3}.items() if k != 'rating'}, 121),
        ]:
            try:
                collection.insert_one(copy.deepcopy(item))
                results.append({'check': label, 'passed': False, 'result': 'Invalid document accepted.'})
            except WriteError as error:
                results.append({'check': label, 'passed': error.code == expected, 'result': f'MongoDB error code {error.code}; expected {expected}.'})
        vote_index = next((v for v in mongo.upvotes.list_indexes() if v['name'] == 'one_vote_per_user'), None)
        if vote_index:
            collection.create_index(list(vote_index['key'].items()), unique=vote_index.get('unique', False), sparse=True)
            # Content validator remains active; add vote identity fields to valid documents.
            collection.insert_one({**valid, '_id': 10, 'user_id': 1, 'content_id': 1})
            try:
                collection.insert_one({**valid, '_id': 11, 'user_id': 1, 'content_id': 1})
                results.append({'check': 'MongoDB compound unique vote', 'passed': False})
            except DuplicateKeyError:
                results.append({'check': 'MongoDB compound unique vote', 'passed': True, 'result': 'Duplicate (user_id, content_id) rejected.'})
        else:
            results.append({'check': 'MongoDB compound unique vote', 'passed': False, 'result': 'Required live index missing.'})
    finally:
        mongo.drop_collection(name)
    return {'checks': results, 'scope': 'SQL writes rolled back; Mongo probes use copied live validators/indexes in a new disposable collection, removed afterwards.'}


def security_evidence():
    # Public dummy password + throwaway pepper; never return real account hashes.
    from .passwords import METHOD, PREFIX
    password, pepper = 'Public demonstration password', secrets.token_bytes(32)
    prehash = hmac.new(pepper, password.encode(), hashlib.sha256).hexdigest()
    first, second = [generate_password_hash(prehash, method=METHOD) for _ in range(2)]
    wrong = hmac.new(secrets.token_bytes(32), password.encode(), hashlib.sha256).hexdigest()
    hashes = list(db.session.scalars(select(User.password_hash)))
    return {'algorithm': METHOD, 'newFormatAccounts': sum(h.startswith(PREFIX) for h in hashes),
        'legacyAccounts': sum(not h.startswith(PREFIX) for h in hashes),
        'dummyHashes': [first, second], 'differentSalts': first.split('$')[1] != second.split('$')[1],
        'correctPasswordWorks': check_password_hash(first, prehash), 'wrongPepperRejected': not check_password_hash(first, wrong),
        'explanation': 'HMAC-SHA256 with PASSWORD_PEPPER, then scrypt with a per-password random salt. The environment secret is never stored in SQL or served by this API. These two hashes use a throwaway demonstration secret. Legacy hashes upgrade after successful login. Losing/changing the real pepper requires a controlled password reset.'}


def lab_snapshot():
    from .evaluation import recorded_evaluation
    from .course_evidence import collect_course_evidence
    from .schema import application_schema
    from .population import counts, CSV
    from .imports import import_csv
    from .query_evidence import collect_query_evidence
    schema = application_schema()
    for table in schema['tables']:
        table['role'] = 'live' if table['name'] in LIVE_SQL else 'legacy SQL migration source (not used by live community features)'
    mongo = community_db()
    collections = [{ 'name': name, 'count': mongo[name].count_documents({}),
        'validator': mongo[name].options().get('validator', {}),
        'indexes': [{k: v for k, v in dict(index).items() if k in ('name', 'key', 'unique', 'partialFilterExpression')} for index in mongo[name].list_indexes()]
        } for name in ('content', 'upvotes', 'reports')]
    examples = list(mongo.content.find({}, {'body': 0}).sort('_id', 1).limit(2))
    for item in examples:
        for key, value in item.items():
            if isinstance(value, datetime):
                item[key] = value.isoformat() + 'Z'
    ids = list(db.session.scalars(select(FoodPlace.place_id).where(FoodPlace.archived_at.is_(None))))
    pipeline = rating_pipeline(ids)
    mongo_plan = mongo.command('explain', {'find': 'content', 'filter': {
        'place_id': ids[0] if ids else 1, 'kind': 'review', 'removed_at': None},
        'sort': {'_id': 1}, 'limit': 10}, verbosity='executionStats')
    execution = mongo_plan.get('executionStats', {})
    preview = import_csv(str(CSV))
    preview.pop('place_ids', None)
    preview['csv'] = CSV.name
    latest = mongo.population_runs.find_one({}, sort=[('_id', -1)])
    return {'generatedAt': now().isoformat() + 'Z', 'counts': counts(), 'schema': schema,
        'evaluation': recorded_evaluation(),
        'mongo': {'version': mongo.command('buildInfo')['version'], 'collections': collections, 'examples': examples,
            'pipeline': rating_pipeline(['<active SQL place IDs>']), 'results': list(mongo.content.aggregate(pipeline + [{'$limit': 6}])),
            'feedExplain': {'query': {'place_id': ids[0] if ids else 1, 'kind': 'review', 'removed_at': None},
                'sort': {'_id': 1}, 'limit': 10, 'winningPlan': mongo_plan.get('queryPlanner', {}).get('winningPlan'),
                'returned': execution.get('nReturned'), 'keysExamined': execution.get('totalKeysExamined'),
                'documentsExamined': execution.get('totalDocsExamined')}},
        'population': {'csvPreview': preview, 'latestRun': latest['summary'] if latest else None,
            'receipts': [{'key': r.run_key, 'at': r.created_at.isoformat() + 'Z', **r.details} for r in db.session.scalars(select(PopulationRun))]},
        'audit': integrity_audit(), 'queries': collect_query_evidence(),
        'course': collect_course_evidence(db.engine),
        'view': {'name': 'catalogue_menu_summary', 'sql': VIEW_SQL,
            'rows': [dict(r) for r in db.session.execute(text('SELECT * FROM catalogue_menu_summary ORDER BY place_id LIMIT 10')).mappings()]},
        'normalization': {'joinedExample': [dict(r) for r in db.session.execute(select(FoodPlace.place_id, FoodPlace.place_name,
            FoodPlace.area_id, Area.area_name).join(Area).order_by(FoodPlace.place_id).limit(8)).mappings()],
            'dependencies': [
                ['food_place', 'place_id → place_name, address, area_id, category_id, …', 'One venue identity determines its attributes. Names alone are not keys.'],
                ['area', 'area_id → area_name; area_name → area_id (UNIQUE NOT NULL)', 'Area name is stored once; rename one row instead of every venue.'],
                ['dish', 'dish_id → place_id, dish_name, price, …', 'Dish names can repeat at different venues; use a surrogate primary key.'],
                ['menu_publication', 'publication_id → source observation; payload_sha256 → publication_id', 'One immutable source observation; URLs alone are not unique observations.'],
                ['menu_entry', '(publication_id, source_item_id) → item_name, reference_price, description, dietary_label', 'A source item ID is scoped to its publication. Shared facts are stored once.'],
                ['dish (outlet offering)', '(place_id, publication_id, source_item_id) → dish_id; dish_id → outlet overrides', 'Stable existing dish IDs retain Mongo feedback and legacy SQL links. Reference offerings clear legacy payload columns.'],
                ['place_tag', '(place_id, tag_id) is the key', 'Multivalued tags use relationship rows; the retained JSON column is empty after migration.'],
                ['user', 'user_id → profile; email → user_id; username → user_id', 'Email and username are alternate candidate keys, enforced UNIQUE NOT NULL.'],
                ['favourite', '(user_id, place_id) → saved_at', 'Composite key permits many venues per user but only one save per pair.'],
                ['place_cuisine', '(place_id, cuisine_id) is the key', 'Junction table resolves a many-to-many relationship without comma-separated cuisine IDs.'],
            ],
            'reasoning': 'A denormalized Venue(place_id, area_id, area_name) has the transitive dependency place_id → area_id → area_name. Decompose into food_place and area. Joining on area_id is lossless because area_id is a key of area; the dependencies are preserved. This explains this decomposition, not a proof that every field in the whole system is 3NF.',
            'tradeoff': 'Shared menu facts and tag memberships are normalized. Legacy dish columns support manual dishes and offline upgrade compatibility; effective menus use the joined catalogue_effective_menu view. Enrichment/receipt JSON are explicit non-flat operational exceptions. Mongo embeds bounded feedback; unbounded replies/votes are separate. This is not a whole-schema BCNF claim.'}}


def register_lab(app, limiter):
    @app.get('/api/admin/database-evaluation')
    @authenticated(admin=True)
    @limiter.limit('10 per minute')
    def evaluation():
        from .evaluation import recorded_evaluation
        return jsonify(recorded_evaluation())

    @app.get('/api/admin/database-lab')
    @authenticated(admin=True)
    @limiter.limit('10 per minute')
    def snapshot():
        return jsonify(lab_snapshot())

    @app.post('/api/admin/database-lab/probes')
    @authenticated(admin=True)
    @limiter.limit('5 per minute')
    def probes():
        return jsonify(constraint_probes())

    @app.post('/api/admin/database-lab/security')
    @authenticated(admin=True)
    @limiter.limit('5 per minute')
    def security():
        return jsonify(security_evidence())
