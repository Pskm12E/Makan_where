"""Isolated logical backup/restore and restart probe; never targets app databases.

prepare creates unique proof databases and an exclusive backup directory.
After the operator restarts the dedicated test engines, verify checks persisted
data, restores into NEW databases, compares complete snapshots and audits links.
This is a graceful-restart/logical-restore experiment, not a power-loss test.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
from bson import json_util
from pymongo import MongoClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def encode(value):
    if isinstance(value, datetime):
        return {'$probe_datetime': value.isoformat()}
    if isinstance(value, Decimal):
        return {'$probe_decimal': str(value)}
    raise TypeError(type(value).__name__)


def decode(value):
    if set(value) == {'$probe_datetime'}:
        return datetime.fromisoformat(value['$probe_datetime'])
    if set(value) == {'$probe_decimal'}:
        return Decimal(value['$probe_decimal'])
    return value


def proof_app(name):
    from backend.app import create_app
    return create_app({'SECRET_KEY': 'isolated-recovery-proof-' * 3, 'PASSWORD_PEPPER': 'isolated-recovery-pepper-' * 3,
        'SQLALCHEMY_DATABASE_URI': make_url(os.environ['MARIADB_TEST_ADMIN_URL']).set(database=name).render_as_string(hide_password=False),
        'MONGODB_URI': os.environ['MONGODB_TEST_URI'], 'MONGODB_DATABASE': name,
        'TESTING': True, 'RATELIMIT_ENABLED': False, 'SESSION_COOKIE_SECURE': False})


def snapshot():
    from backend.models import db
    from backend.mongo import community_db
    sql = {t.name: [dict(r) for r in db.session.execute(select(t).order_by(*t.primary_key.columns)).mappings()]
           for t in db.metadata.sorted_tables}
    mongo = {name: list(community_db()[name].find().sort('_id', 1))
             for name in sorted(community_db().list_collection_names()) if not name.startswith('system.')}
    return {'sql': json.dumps(sql, default=encode, sort_keys=True),
            'mongo': json_util.dumps(mongo, sort_keys=True)}


def checksum(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def create_database(engine, name):
    if not name.startswith('makanwhere_recovery_') or not name.replace('_', '').isalnum():
        raise ValueError('Invalid isolated proof database name')
    with engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))


def prepare(folder, admin):
    folder.mkdir(parents=True, exist_ok=False)
    name = 'makanwhere_recovery_' + uuid.uuid4().hex
    create_database(admin, name)
    app = proof_app(name)
    runner = app.test_cli_runner()
    for command in ('init-db', 'init-mongo', 'seed-demo'):
        result = runner.invoke(args=[command])
        if result.exit_code:
            raise RuntimeError(f'{command} failed') from result.exception
    with app.app_context():
        from backend.models import db, User, Favourite, Dish, now
        from backend.mongo import community_db, next_id
        from backend.evaluation import source_fingerprint
        from backend.database_lab import integrity_audit
        user = User(username='recovery_probe', email='probe@recovery.invalid', display_name='Synthetic recovery proof',
                    password_hash='synthetic-no-login', role='user')
        db.session.add(user)
        db.session.flush()
        db.session.add(Favourite(user_id=user.user_id, place_id=1))
        from backend.catalogue_design import publication_for, bind_offering
        publication = publication_for({'sourceName': 'Synthetic recovery source', 'sourceUrl': 'https://example.invalid/recovery-menu',
            'observedAt': '2026-01-01T00:00:00+00:00', 'isReference': True,
            'items': [{'sourceId': 'recovery-item', 'name': 'Synthetic shared item', 'price': '6.25', 'description': '', 'dietary': ''}]})
        for pid in (1, 2):
            dish = Dish(place_id=pid, source_item_id='recovery-item', is_available=True)
            bind_offering(dish, publication, 'recovery-item')
            db.session.add(dish)
        db.session.commit()
        content_id = next_id('content')
        community_db().content.insert_one({'_id': content_id, 'kind': 'review', 'author_id': user.user_id,
            'place_id': 1, 'title': 'Recovery proof', 'body': 'Synthetic committed record', 'rating': 4,
            'created_at': now(), 'updated_at': now(), 'removed_at': None, 'removed_by_id': None, 'revision': 1,
            'dishes': [{'dish_id': 1, 'feedback': 'Retain this SQL reference'}]})
        community_db().upvotes.insert_one({'user_id': user.user_id, 'content_id': content_id, 'voted_at': now()})
        community_db().reports.insert_one({'_id': next_id('reports'), 'reporter_id': user.user_id, 'content_id': content_id,
            'reason': 'Synthetic recovery proof', 'status': 'resolved', 'created_at': now(),
            'resolved_by_id': user.user_id, 'resolved_at': now(), 'resolution_note': 'Synthetic decision'})
        data = snapshot()
        (folder/'backup.json').write_text(json.dumps(data), encoding='utf-8')
        state = {'database': name, 'sourceSha256': source_fingerprint(), 'snapshotSha256': checksum(data),
                 'sqlUptime': sql_uptime(admin), 'mongoUptime': community_db().command('serverStatus')['uptime'],
                 'preparedAt': datetime.now(timezone.utc).isoformat(), 'auditBefore': integrity_audit()}
        (folder/'state.json').write_text(json.dumps(state, default=str), encoding='utf-8')
    return {'status': 'prepared', 'next': 'Restart only the dedicated test engines, then run verify with the same directory.'}


def sql_uptime(admin):
    with admin.connect() as c:
        return int(c.execute(text("SHOW GLOBAL STATUS LIKE 'Uptime'")).one()[1])


def verify(folder, admin):
    from backend.models import db
    from backend.mongo import community_db, init_collections
    from backend.database_lab import integrity_audit, install_views
    from backend.evaluation import source_fingerprint
    state = json.loads((folder/'state.json').read_text())
    if not state['database'].startswith('makanwhere_recovery_') or not state['database'].replace('_', '').isalnum():
        raise ValueError('State does not identify an isolated proof database')
    if state['sourceSha256'] != source_fingerprint():
        raise RuntimeError('Code changed after prepare; create a new proof directory.')
    data = json.loads((folder/'backup.json').read_text())
    if checksum(data) != state['snapshotSha256']:
        raise RuntimeError('Backup checksum mismatch')
    app = proof_app(state['database'])
    with app.app_context():
        if snapshot() != data:
            raise RuntimeError('Committed data differs after reconnect/restart')
        mongo_uptime = community_db().command('serverStatus')['uptime']
        sql_version = db.session.scalar(text('SELECT VERSION()'))
        mongo_version = community_db().command('buildInfo')['version']
    restored = 'makanwhere_recovery_' + uuid.uuid4().hex
    create_database(admin, restored)
    restored_app = proof_app(restored)
    with restored_app.app_context():
        db.create_all()
        install_views()
        init_collections()
        sql = json.loads(data['sql'], object_hook=decode)
        for table in db.metadata.sorted_tables:
            if sql[table.name]:
                db.session.execute(table.insert(), sql[table.name])
        db.session.commit()
        for name, documents in json_util.loads(data['mongo']).items():
            if documents:
                community_db()[name].insert_many(documents)
        if snapshot() != data:
            raise RuntimeError('Restored data differs from the complete backup')
        audit = integrity_audit()
        if any(audit['mongoReferences'].values()) or any(r['orphans'] for r in audit['sqlForeignKeys']):
            raise RuntimeError('Restored cross-database references are invalid')
    sql_now = sql_uptime(admin)
    restarted = sql_now < state['sqlUptime'] and mongo_uptime < state['mongoUptime']
    result = {'passed': restarted, 'sourceSha256': state['sourceSha256'], 'sqlVersion': sql_version,
        'mongoVersion': mongo_version, 'snapshotSha256': state['snapshotSha256'],
        'persistedAfterReconnect': True, 'completeLogicalRestoreEqual': True, 'restoredReferenceErrors': 0,
        'sqlUptimeBefore': state['sqlUptime'], 'sqlUptimeAfter': sql_now,
        'mongoUptimeBefore': state['mongoUptime'], 'mongoUptimeAfter': mongo_uptime,
        'restartObserved': restarted, 'verifiedAt': datetime.now(timezone.utc).isoformat(),
        'limits': ['Graceful restart, not power-loss or forced crash recovery.',
                   'Known application schema and quiescent synthetic data; not a concurrent production backup.',
                   'SQL/Mongo consistency requires stopped writes and a matching backup pair.']}
    (folder/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'verify'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--env', type=Path)
    args = parser.parse_args()
    if args.env:
        from scripts.run_demo import load_env
        load_env(args.env)
    admin = create_engine(os.environ['MARIADB_TEST_ADMIN_URL'])
    try:
        result = prepare(args.directory, admin) if args.phase == 'prepare' else verify(args.directory, admin)
        print(json.dumps(result, indent=2))
        if result.get('passed') is False:
            raise SystemExit('Complete restoration passed, but engine restart was not corroborated; do not claim restart evidence.')
    finally:
        admin.dispose()


if __name__ == '__main__':
    main()
