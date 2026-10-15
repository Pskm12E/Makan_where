"""Small, labelled fictional conversations on explicitly selected source listings.

Insert-only stable keys preserve edited/removed examples on repeats. SQL account
creation commits before MongoDB writes; retries resume, not a distributed commit.
"""
import hashlib
import json
import secrets
from sqlalchemy import select
from .models import db, FoodPlace, User, PopulationRun, now
from .mongo import community_db, next_id
from .passwords import hash_password

VERSION = 'listing-examples-v1'
TARGETS = [
    {'id': 9, 'name': 'KFC', 'sourceUrl': 'https://www.openstreetmap.org/node/369123954'},
    {'id': 10, 'name': "McDonald's", 'sourceUrl': 'https://www.openstreetmap.org/node/369125094'},
    {'id': 14, 'name': "McDonald's", 'sourceUrl': 'https://www.openstreetmap.org/node/369548445'},
    {'id': 15, 'name': 'Suki-ya', 'sourceUrl': 'https://www.openstreetmap.org/node/380582666'},
]
REVIEWS = [
    ('A quick lunch visit', 4, 'In this fictional lunch scenario, the diner finds choosing a main and a drink straightforward. They would check the current menu before ordering again.'),
    ('Ordering for a group', 3, 'In this fictional group-order scenario, everyone compares meal choices before deciding. The imagined feedback asks for clearer portion and dietary information.'),
    ('Planning the next meal', 5, 'In this fictional scenario, the diner enjoys planning a meal from the menu and saves the listing for later. This demonstrates a positive review and star rating.'),
]
THREADS = [
    ('What would you choose for lunch?', 'Example discussion: imagine planning a quick lunch here. Which menu information would help you choose?', [
        'Example reply: I would compare the mains and drinks on the linked official menu before deciding.',
        'Example reply: I would check the outlet selection and current prices first, especially for a chain reference menu.',
    ]),
    ('Planning a meal with friends', 'Example discussion: imagine organising a group meal. What would you check before meeting up?', [
        'Example reply: I would confirm the location, opening hours and dietary options with the business.',
        'Example reply: I would share the official menu with the group so everyone can compare their choices.',
    ]),
]


def seed_listing_examples(targets=None, *, apply=False):
    targets = TARGETS if targets is None else targets
    if not targets or len({p['id'] for p in targets}) != len(targets):
        raise ValueError('Choose distinct, explicit source listings.')
    for target in targets:
        place = db.session.get(FoodPlace, target['id'])
        if (not place or place.archived_at or place.is_sample or place.place_name != target['name']
                or place.source_url != target['sourceUrl'] or place.source_name != 'OpenStreetMap'):
            raise ValueError(f"Listing {target['id']} no longer matches its reviewed source identity.")
    accounts = []
    for index in range(1, 4):
        username = f'example_guest_{index:02d}'
        user = db.session.scalar(select(User).where(User.username == username))
        identity = {'username': username, 'email': f'{username}@demo.invalid', 'display_name': f'Example Guest {index}'}
        if user and any(getattr(user, k) != v for k, v in identity.items()):
            raise ValueError('A reserved example account conflicts with an existing account.')
        accounts.append((user, identity))
    mongo = community_db()
    specs = []
    for target in targets:
        prefix = f"{VERSION}:{target['id']}"
        for index, (title, rating, body) in enumerate(REVIEWS):
            specs.append({'seed_key': f'{prefix}:review:{index}', 'kind': 'review', 'place_id': target['id'],
                'author_index': index, 'title': '[Example] ' + title, 'rating': rating,
                'body': 'FICTIONAL EXAMPLE - not a customer review or a claim about this outlet. ' + body})
        for index, (title, body, replies) in enumerate(THREADS):
            key = f'{prefix}:thread:{index}'
            specs.append({'seed_key': key, 'kind': 'thread', 'place_id': target['id'], 'author_index': index,
                'title': '[Example] ' + title, 'body': body + ' This is a fictional conversation for the project.'})
            for offset, reply in enumerate(replies):
                specs.append({'seed_key': f'{key}:reply:{offset}', 'kind': 'comment', 'place_id': target['id'],
                    'author_index': (index + offset + 1) % 3, 'parent_key': key,
                    'body': reply + ' This is a fictional example, not a report of a visit.'})
    existing = {c['seed_key']: c for c in mongo.content.find({'seed_key': {'$in': [s['seed_key'] for s in specs]}})}
    for spec in specs:
        old = existing.get(spec['seed_key'])
        user = accounts[spec['author_index']][0]
        if old and (not user or old['author_id'] != user.user_id or old['place_id'] != spec['place_id']
                    or old['kind'] != spec['kind'] or not old.get('is_example') or not old.get('is_demo')):
            raise ValueError('Existing example identities conflict; no records were replaced.')
    summary = {'version': VERSION, 'applied': apply, 'targets': targets, 'added': 0, 'skipped': len(existing),
               'reviews': 0, 'threads': 0, 'replies': 0}
    if apply:
        for index, (user, identity) in enumerate(accounts):
            if not user:
                user = User(**identity, role='user', password_hash=hash_password(secrets.token_urlsafe(48)))
                db.session.add(user)
                accounts[index] = (user, identity)
        db.session.commit()
    ids = {key: c['_id'] for key, c in existing.items()}
    labels = {'review': 'reviews', 'thread': 'threads', 'comment': 'replies'}
    for spec in specs:
        if spec['seed_key'] in existing:
            continue
        if apply:
            item = {k: v for k, v in spec.items() if k not in {'author_index', 'parent_key'}}
            stamp = now()
            item.update(_id=next_id('content'), author_id=accounts[spec['author_index']][0].user_id,
                is_demo=True, is_example=True, created_at=stamp, updated_at=stamp,
                removed_at=None, removed_by_id=None, dishes=[])
            if spec['kind'] == 'comment':
                item['thread_id'] = ids[spec['parent_key']]
            result = mongo.content.update_one({'seed_key': spec['seed_key']}, {'$setOnInsert': item}, upsert=True)
            ids[spec['seed_key']] = result.upserted_id or mongo.content.find_one({'seed_key': spec['seed_key']})['_id']
            if result.upserted_id is None:
                summary['skipped'] += 1
                continue
        summary['added'] += 1
        summary[labels[spec['kind']]] += 1
    if apply:
        key = VERSION + ':' + hashlib.sha256(json.dumps(targets, sort_keys=True).encode()).hexdigest()
        if not db.session.get(PopulationRun, key):
            db.session.add(PopulationRun(run_key=key, details={**summary, 'synthetic': True,
                'note': 'Clearly labelled fictional examples; excluded from venue ratings and rankings.'}))
            db.session.commit()
    return summary
