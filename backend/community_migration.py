"""Insert-only legacy SQL -> Mongo migration. Run with the web app stopped.

Leaves all SQL rows intact. Conflicting destination IDs abort; never overwrite
new community activity. Reruns recognise the exact original migration payload.
"""
import hashlib
import json
from sqlalchemy import select
from .models import db, Content, Review, Thread, Comment, ContentDish, Upvote, Report
from .mongo import community_db, init_collections


def migrate_community():
    init_collections()
    mongo = community_db()
    prepared = {'content': [], 'upvotes': [], 'reports': []}
    for c in db.session.scalars(select(Content).order_by(Content.content_id)):
        item = {'_id': c.content_id, 'kind': c.kind, 'author_id': c.author_id, 'place_id': c.place_id,
                'body': c.body, 'created_at': c.created_at, 'updated_at': c.updated_at,
                'removed_at': c.removed_at, 'removed_by_id': c.removed_by_id, 'is_demo': False,
                'dishes': [{'dish_id': d.dish_id, 'feedback': d.dish_feedback} for d in db.session.scalars(
                    select(ContentDish).where(ContentDish.content_id == c.content_id).order_by(ContentDish.dish_id))]}
        subtype = db.session.get({'review': Review, 'thread': Thread, 'comment': Comment}[c.kind], c.content_id)
        if not subtype:
            raise ValueError(f'Legacy content {c.content_id} is missing its subtype; repair before migration.')
        if c.kind == 'review':
            item.update(rating=subtype.rating, title=subtype.title)
        elif c.kind == 'thread':
            item['title'] = subtype.title
        else:
            item['thread_id'] = subtype.thread_id
        prepared['content'].append(item)
    for v in db.session.scalars(select(Upvote)):
        prepared['upvotes'].append({'user_id': v.user_id, 'content_id': v.content_id, 'voted_at': v.voted_at})
    for r in db.session.scalars(select(Report)):
        prepared['reports'].append({'_id': r.report_id, 'reporter_id': r.reporter_id, 'content_id': r.content_id,
            'reason': r.reason, 'created_at': r.created_at, 'status': r.status,
            'resolved_by_id': r.resolved_by_id, 'resolved_at': r.resolved_at, 'resolution_note': r.resolution_note})
    pending = []
    for collection, rows in prepared.items():
        for item in rows:
            identity = {'_id': item['_id']} if '_id' in item else {k: item[k] for k in ('user_id', 'content_id')}
            checksum = hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()
            old = mongo[collection].find_one(identity)
            if old and old.get('legacy_checksum') != checksum:
                raise ValueError(f'Migration conflict in {collection}; destination data preserved.')
            if not old:
                pending.append((collection, {**item, 'legacy_checksum': checksum}))
    for collection, item in pending:
        mongo[collection].insert_one(item)
    for collection in ('content', 'reports'):
        last = mongo[collection].find_one({}, sort=[('_id', -1)])
        if last:
            mongo.counters.update_one({'_id': collection}, {'$max': {'value': last['_id']}}, upsert=True)
    return {'inserted': len(pending), 'legacyRows': {k: len(v) for k, v in prepared.items()}, 'sqlPreserved': True}
