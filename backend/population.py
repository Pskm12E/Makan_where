"""Deterministic, insert-only fixtures and persistent population receipts.

SQL commits before MongoDB. These are NOT one distributed transaction.
Stable keys and phase receipts make a failed run resumable without duplication.
All invented community records are labelled and refer only to sample venues.
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import func, select
from .config import BASE_DIR
from .models import db, FoodPlace, Dish, User, Favourite, DiscoveryEvent, PopulationRun, now
from .mongo import community_db, init_collections, next_id
from .passwords import hash_password

CSV = BASE_DIR / 'data/scraped/singapore_food_places_20260922T094048Z.csv'
VERSION = 'coursework-demo-v1'


def counts():
    sql = {name: db.session.scalar(select(func.count()).select_from(table)) for name, table in db.metadata.tables.items()}
    mongo = {name: community_db()[name].count_documents({}) for name in ('content', 'upvotes', 'reports')}
    return {'sql': sql, 'mongo': mongo}


def seed_coursework(csv_path=CSV):
    from .imports import import_csv
    from .routes import save_place
    init_collections()
    before = counts()
    # Add missing sample fixtures even if a real catalogue has already been imported.
    samples = json.loads((BASE_DIR / 'database/demo_places.json').read_text(encoding='utf-8'))
    places = []
    for index, record in enumerate(samples, 1):
        source_id = f'{VERSION}-place-{index}'
        place = db.session.scalar(select(FoodPlace).where(FoodPlace.source_name == 'synthetic', FoodPlace.source_id == source_id))
        if not place:
            # Recognise the original seed-demo records instead of copying them.
            place = db.session.scalar(select(FoodPlace).where(FoodPlace.is_sample.is_(True),
                FoodPlace.place_name == record['name'], FoodPlace.address == record['address'], FoodPlace.source_id.is_(None)))
        if not place:
            place = FoodPlace(description=record['description'], image_url=record['image'], tags=record['tags'], is_sample=True)
            with db.session.no_autoflush:
                save_place(place, {**record, 'photoKind': 'illustrative', 'photoCredit': 'Unsplash', 'photoSourceUrl': 'https://unsplash.com/license'})
            db.session.add(place)
            db.session.flush()
            for dish in record['menu']:
                db.session.add(Dish(place_id=place.place_id, dish_name=dish['name'], price=dish['price'],
                    dietary_label=dish['dietary'], is_available=dish['availability']))
        place.source_name, place.source_id = 'synthetic', source_id
        places.append(place.place_id)
    db.session.commit()
    imported = import_csv(str(csv_path), apply=True)
    digest = hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()
    receipt_key = 'csv:' + digest
    if not db.session.get(PopulationRun, receipt_key):
        db.session.add(PopulationRun(run_key=receipt_key, details={
            'source': Path(csv_path).name, 'sha256': digest, 'rows': imported['rows'],
            'inserted': imported['new'], 'existingSkipped': imported['existing_skipped'],
            'licence': 'ODbL 1.0; OpenStreetMap contributors', 'synthetic': False}))
        db.session.commit()
    users = []
    for index in range(60):
        username = f'demo_student_{index:03d}'
        user = db.session.scalar(select(User).where(User.username == username))
        email = f'{username}@demo.invalid'
        if user and (user.email != email or user.display_name != f'DEMO Student {index:03d}'):
            raise ValueError(f'Reserved demo identity conflicts with an existing account: {username}')
        if not user:
            # Every account has its own salt and an unknown random password.
            user = User(username=username, display_name=f'DEMO Student {index:03d}', email=email,
                        password_hash=hash_password(secrets.token_urlsafe(32)), role='user')
            db.session.add(user)
            db.session.flush()
        users.append(user.user_id)
    marker = db.session.get(PopulationRun, VERSION + ':sql')
    if not marker:
        for index, uid in enumerate(users):
            for offset in range(2):
                pid = places[(index + offset) % len(places)]
                if not db.session.get(Favourite, (uid, pid)):
                    db.session.add(Favourite(user_id=uid, place_id=pid))
            for offset in range(5):
                kind = 'search' if offset % 2 == 0 else 'place_view'
                db.session.add(DiscoveryEvent(user_id=uid, place_id=places[index % len(places)] if kind == 'place_view' else None,
                    event_type=kind, occurred_at=datetime(2026, 9, 1) + timedelta(hours=index * 5 + offset)))
        db.session.add(PopulationRun(run_key=VERSION + ':sql', details={
            'synthetic': True, 'users': len(users), 'favourites': 120, 'discoveryEvents': 300,
            'note': 'Fictional exercise data; community content only on sample listings.'}))
    db.session.commit()
    mongo = community_db()
    content_ids, thread_ids = [], []
    dishes = {pid: list(db.session.scalars(select(Dish.dish_id).where(Dish.place_id == pid).order_by(Dish.dish_id))) for pid in places}

    def add_content(kind, index, place_id, **extra):
        key = f'{VERSION}:{kind}:{index}'
        existing = mongo.content.find_one({'seed_key': key}, {'_id': 1, 'author_id': 1, 'place_id': 1})
        if existing:
            if existing['author_id'] != users[index % len(users)] or existing['place_id'] != place_id:
                raise ValueError('Demo SQL identities differ from existing Mongo fixtures. Use a matching pair of databases; existing documents were preserved.')
            return existing['_id']
        stamp = datetime(2026, 9, 1) + timedelta(minutes=index * 17)
        item = {'_id': next_id('content'), 'seed_key': key, 'is_demo': True, 'kind': kind,
            'author_id': users[index % len(users)], 'place_id': place_id,
            'body': f'DEMONSTRATION DATA {index + 1}: generated {kind} for testing database operations, not a customer opinion.',
            'created_at': stamp, 'updated_at': stamp, 'removed_at': None, 'removed_by_id': None, 'dishes': [], **extra}
        mongo.content.insert_one(item)
        return item['_id']

    for index in range(600):
        pid = places[index % len(places)]
        feedback = [{'dish_id': dishes[pid][index % len(dishes[pid])], 'feedback': 'DEMO: embedded dish feedback.'}] if dishes[pid] else []
        content_ids.append(add_content('review', index, pid, title=f'DEMO review {index + 1}', rating=1 + ((index * 7 + index // 6) % 5), dishes=feedback))
    for index in range(30):
        pid = places[index % len(places)]
        tid = add_content('thread', index, pid, title=f'DEMO discussion {index + 1}')
        thread_ids.append(tid)
        for offset in range(3):
            add_content('comment', index * 3 + offset, pid, thread_id=tid)
    for index, cid in enumerate(content_ids):
        mongo.upvotes.update_one({'user_id': users[(index + 1) % len(users)], 'content_id': cid},
            {'$setOnInsert': {'voted_at': datetime(2026, 9, 15), 'is_demo': True}}, upsert=True)
    for index in range(20):
        key = f'{VERSION}:report:{index}'
        if not mongo.reports.find_one({'seed_key': key}):
            mongo.reports.insert_one({'_id': next_id('reports'), 'seed_key': key, 'is_demo': True,
                'reporter_id': users[(index + 2) % len(users)], 'content_id': content_ids[index],
                'reason': 'DEMO moderation exercise; no allegation about a real person.',
                'status': 'open', 'created_at': datetime(2026, 9, 16)})
    after = counts()
    summary = {'version': VERSION, 'synthetic': True, 'before': before, 'after': after,
        'added': {engine: {name: count - before[engine].get(name, 0) for name, count in rows.items()} for engine, rows in after.items()},
        'csvSha256': digest, 'completedAt': now().isoformat() + 'Z'}
    mongo.population_runs.insert_one({'completed_at': now(), 'summary': summary})
    return summary
