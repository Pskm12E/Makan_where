"""Validate the proposed design without modifying the current application DB.

Always uses a fresh in-memory SQL database. Optional Mongo probes use a new
random test database via MONGODB_TEST_URI and remove only that database.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import sys
from uuid import uuid4
from sqlalchemy import create_engine, event, select, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mysql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from database.design_v2 import metadata, place, publication, entry, offering, tag, place_tag, NEW_TABLES, EFFECTIVE_MENU_SQL, formal_evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env',type=Path)
    args=parser.parse_args()
    if args.env:
        from scripts.run_demo import load_env
        load_env(args.env)
    output=ROOT/'docs/evidence/design-v2-validation.json'
    result={'status':'proposed design validated in isolation; not a live migration',
        'generatedAt':datetime.now(timezone.utc).isoformat(),'checks':[], 'formal':formal_evidence()}
    source_files=['database/design_v2.py','scripts/verify_design_v2.py',
        'backend/course_evidence.py','backend/mongo.py',
        'data/menus/kfc_sg_reference_20261004.json','data/menus/sukiya_sg_reference_20261004.json']
    result['sourceSha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files}
    def check(name, passed, observed):
        result['checks'].append({'check':name,'passed':bool(passed),'observed':observed})
        if not passed: raise AssertionError(name)
    proof=result['formal']
    check('BCNF of the three menu relations under declared FDs',all(not p['bcnfViolations'] for p in proof['parts']),proof['parts'])
    check('Both decomposition steps are lossless',all(p['proved'] for p in proof['losslessSplits']),proof['losslessSplits'])
    check('All declared FDs are preserved',proof['dependencyPreserved'],proof['dependencyPreserved'])
    menus=[json.loads((ROOT/'data/menus'/filename).read_text(encoding='utf-8')) for filename in
        ['kfc_sg_reference_20261004.json','sukiya_sg_reference_20261004.json']]
    engine=create_engine('sqlite:///:memory:')
    @event.listens_for(engine,'connect')
    def enforce_fks(connection,_): connection.execute('PRAGMA foreign_keys=ON')
    metadata.create_all(engine)
    # 72 KFC + 4 Suki-Ya fixture outlets mirror retained import cardinalities.
    # They are NOT real production rows or verified outlet-menu confirmations.
    baseline=[]; offering_id=0; next_place=1
    with engine.begin() as conn:
        for pub_id,(menu,outlets) in enumerate(zip(menus,[72,4]),1):
            assert menu['currency']=='SGD'  # fixed application price domain, not a repeated stored constant
            payload_hash=hashlib.sha256(json.dumps({k:menu[k] for k in ['sourceName','sourceUrl','observedAt','currency','items']},sort_keys=True).encode()).hexdigest()
            ids=list(range(next_place,next_place+outlets)); next_place+=outlets
            conn.execute(place.insert(),[{'place_id':pid,'place_name':f'Prototype outlet {pid}'} for pid in ids])
            conn.execute(publication.insert().values(publication_id=pub_id,source_name=menu['sourceName'],source_url=menu['sourceUrl'],
                observed_at=datetime.fromisoformat(menu['observedAt']).replace(tzinfo=None),payload_sha256=payload_hash,is_reference=True))
            conn.execute(entry.insert(),[{'publication_id':pub_id,'source_item_id':item['sourceId'],'item_name':item['name'],
                'description':item.get('description',''),'reference_price':Decimal(item['price']),'dietary_label':item.get('dietary','')} for item in menu['items']])
            rows=[]
            for pid in ids:
                for item in menu['items']:
                    offering_id+=1
                    rows.append({'offering_id':offering_id,'place_id':pid,'publication_id':pub_id,'source_item_id':item['sourceId'],'is_available':True})
                    baseline.append((offering_id,pid,item['name'],item.get('description',''),
                        Decimal(item['price']),item.get('dietary',''),True,menu['sourceName'],item['sourceId'],
                        menu['sourceUrl'],datetime.fromisoformat(menu['observedAt']).replace(tzinfo=None).isoformat(),True))
            conn.execute(offering.insert(),rows)
        actual=[(r['dish_id'],r['place_id'],r['dish_name'],r['description'],Decimal(str(r['effective_price'])),
            r['dietary_label'],bool(r['is_available']),r['source_name'],r['source_item_id'],r['source_url'],
            datetime.fromisoformat(str(r['observed_at'])).isoformat(),bool(r['is_reference']))
            for r in conn.execute(text(EFFECTIVE_MENU_SQL)).mappings()]
        check('Reconstruct all original offering rows with no spurious tuples',Counter(actual)==Counter(baseline),
            {'before':len(baseline),'after':len(actual),'fieldsCompared':['dish_id','place_id','dish_name','description',
                'effective_price','dietary_label','is_available','source_name','source_item_id','source_url','observed_at','is_reference']})
        check('Shared menu facts stored once',conn.scalar(select(func.count()).select_from(entry))==105,
            {'publications':2,'entries':105,'offeringRelationships':len(actual),'oldCopiedItemPayloads':len(baseline)})
        original_ids={row[0] for row in actual}
        # Local overrides preserve price zero and cannot modify another outlet.
        conn.execute(offering.update().where(offering.c.offering_id==1).values(price_override=0,name_override='Outlet-specific correction'))
        changed=list(conn.execute(text(EFFECTIVE_MENU_SQL)).mappings())
        check('Outlet override is local and zero remains a valid price',changed[0]['effective_price']==0 and
            changed[0]['dish_name']=='Outlet-specific correction' and changed[97]['dish_name']==baseline[97][2],
            {'firstPrice':changed[0]['effective_price'],'nextOutletPrice':changed[97]['effective_price']})
        # An edited edition is inserted as a new observation. Retargeting is atomic
        # and retains offering IDs, availability and outlet-specific overrides.
        first=menus[0]; new_rows=[]
        conn.execute(publication.insert().values(publication_id=3,source_name=first['sourceName'],source_url=first['sourceUrl'],
            observed_at=datetime(2026,10,6),payload_sha256=hashlib.sha256(b'explicit new synthetic observation for validation').hexdigest(),is_reference=True))
        for item in first['items']:
            new_rows.append({'publication_id':3,'source_item_id':item['sourceId'],'item_name':item['name'],
                'reference_price':Decimal(item['price'])+1,'description':item.get('description',''),'dietary_label':item.get('dietary','')})
        conn.execute(entry.insert(),new_rows)
        conn.execute(offering.update().where(offering.c.publication_id==1).values(publication_id=3))
        after=list(conn.execute(text(EFFECTIVE_MENU_SQL)).mappings())
        check('New publication retains old facts, IDs and overrides',
            {r['dish_id'] for r in after}==original_ids and after[0]['effective_price']==0 and
            conn.scalar(select(func.count()).select_from(entry).where(entry.c.publication_id==1))==97,
            {'stableOfferingIds':len(original_ids),'oldEntriesRetained':97,'overrideRetained':True})
        conn.execute(tag.insert(),[{'tag_id':1,'tag_name':'budget'},{'tag_id':2,'tag_name':'family-friendly'}])
        conn.execute(place_tag.insert(),[{'place_id':1,'tag_id':1},{'place_id':1,'tag_id':2}])
        check('Multivalued tags are separate relationship tuples',conn.scalar(select(func.count()).select_from(place_tag))==2,{'place':1,'tagRows':2})
    def rejected(name,statement):
        try:
            with engine.begin() as conn: conn.execute(statement)
        except IntegrityError:
            check(name,True,'Database rejected the invalid tuple; transaction rolled back')
        else: check(name,False,'Invalid tuple accepted')
    rejected('Entry needs a publication parent',entry.insert().values(publication_id=999,source_item_id='invalid',item_name='Invalid',reference_price=1))
    rejected('Composite FK rejects an item from a different edition',offering.insert().values(offering_id=999999,place_id=1,publication_id=2,source_item_id=menus[0]['items'][0]['sourceId'],is_available=True))
    rejected('One offering per outlet and entry',offering.insert().values(offering_id=999998,place_id=1,publication_id=3,source_item_id=menus[0]['items'][0]['sourceId'],is_available=True))
    rejected('Negative price override rejected',offering.update().where(offering.c.offering_id==2).values(price_override=-1))
    rejected('Referenced publication cannot be physically deleted',publication.delete().where(publication.c.publication_id==3))
    rejected('Duplicate tag relationship rejected',place_tag.insert().values(place_id=1,tag_id=1))
    rejected('Duplicate publication fingerprint rejected',publication.insert().values(publication_id=4,source_name='Duplicate',source_url='https://example.invalid',
        observed_at=datetime(2026,10,6),payload_sha256=hashlib.sha256(b'explicit new synthetic observation for validation').hexdigest(),is_reference=True))
    with engine.connect() as conn: result['sqlVersion']=conn.scalar(text('select sqlite_version()'))
    engine.dispose()
    # Emit a concrete MariaDB DDL proposal, not an auto-executed migration.
    ddl=['-- PROPOSED DESIGN ONLY. Not a migration and not applied to the live server.',
         '-- Requires the existing food_place(place_id) parent relation.',
         '-- Keep dish_id as offering_id during a separately reviewed migration.']
    for table in NEW_TABLES:
        ddl.append(str(CreateTable(table).compile(dialect=mysql.dialect()))+';')
        ddl.extend(str(CreateIndex(index).compile(dialect=mysql.dialect()))+';' for index in table.indexes)
    (ROOT/'database/design_v2_mariadb.sql').write_text('\n\n'.join(ddl)+'\n',encoding='utf-8')
    result['ddlSha256']=hashlib.sha256((ROOT/'database/design_v2_mariadb.sql').read_bytes()).hexdigest()
    uri=os.environ.get('MONGODB_TEST_URI')
    if uri:
        from pymongo import MongoClient
        from pymongo.errors import WriteError, DuplicateKeyError
        from backend.mongo import VALIDATORS
        client=MongoClient(uri,serverSelectionTimeoutMS=4000)
        name='makanwhere_design_'+uuid4().hex
        mongo=client[name]
        try:
            result['mongoVersion']=mongo.command('buildInfo')['version']
            mongo.create_collection('content',validator=copy.deepcopy(VALIDATORS['content']),validationLevel='strict',validationAction='error')
            mongo.create_collection('upvotes',validator=copy.deepcopy(VALIDATORS['upvotes']))
            mongo.upvotes.create_index([('user_id',1),('content_id',1)],unique=True)
            stamp=datetime.now(timezone.utc)
            base={'_id':1,'kind':'review','author_id':1,'place_id':1,'body':'Prototype','title':'Prototype','rating':4,
                'created_at':stamp,'updated_at':stamp,'removed_at':None,'removed_by_id':None,'dishes':[]}
            mongo.content.insert_one(base)
            for description,change in [('ISA subtype is disjoint',{'kind':'thread'}),('ISA subtype is covering',{'kind':'unknown'}),
                ('Embedded feedback is bounded',{'dishes':[{'dish_id':i+1,'feedback':None} for i in range(21)]})]:
                try: mongo.content.insert_one({**base,'_id':2,**change})
                except WriteError as error: check(description,error.code==121,{'mongoCode':error.code})
                else: check(description,False,'Unexpected insertion')
            vote={'user_id':1,'content_id':1,'voted_at':stamp}
            mongo.upvotes.insert_one(dict(vote))
            try: mongo.upvotes.insert_one(dict(vote))
            except DuplicateKeyError: check('Mongo vote relationship is unique',True,{'storedVotes':mongo.upvotes.count_documents({})})
            else: check('Mongo vote relationship is unique',False,'Unexpected duplicate')
        finally:
            assert name.startswith('makanwhere_design_') and len(name)==50
            client.drop_database(name); client.close()
    else:
        result['mongoStatus']='not run: no MONGODB_TEST_URI'
    result['passed']=all(c['passed'] for c in result['checks'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'checks':len(result['checks']),'passed':result['passed'],'sqlEngine':'SQLite','sqlVersion':result['sqlVersion'],
        'mongoVersion':result.get('mongoVersion'),'output':str(output),'liveDatabaseChanged':False},indent=2))


if __name__=='__main__': main()
