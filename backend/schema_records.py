"""Bounded, read-only record projections for the administrator's live diagram."""
from datetime import date, datetime
from decimal import Decimal
import re
from flask import abort
from sqlalchemy import select, func
from .models import db, Dish, now
from .mongo import community_db

# Explicit projections: never return passwords, contact details, search text,
# import receipt JSON, or newly added columns without reviewing them first.
SQL_FIELDS = {
    'area': ('area_id', 'area_name'),
    'category': ('category_id', 'category_name'),
    'cuisine': ('cuisine_id', 'cuisine_name'),
    'tag': ('tag_id', 'tag_name'),
    'place_tag': ('place_id', 'tag_id'),
    'menu_publication': ('publication_id', 'source_name', 'source_url', 'observed_at', 'is_reference'),
    'menu_entry': ('publication_id', 'source_item_id', 'item_name', 'reference_price'),
    'food_place': ('place_id', 'place_name', 'area_id', 'category_id', 'address', 'archived_at'),
    'dish': ('dish_id', 'place_id', 'dish_name', 'price', 'publication_id', 'source_item_id', 'price_override', 'is_available'),
    'place_cuisine': ('place_id', 'cuisine_id'),
    'favourite': ('user_id', 'place_id', 'saved_at'),
    'user': ('user_id', 'display_name', 'role'),
    'discovery_event': ('event_id', 'user_id', 'place_id', 'event_type'),
    'population_run': ('run_key', 'created_at'),
}
MONGO_FIELDS = {
    'content': ('_id', 'kind', 'author_id', 'place_id', 'title', 'body', 'rating', 'thread_id', 'dishes', 'updated_at', 'removed_at'),
    'upvotes': ('user_id', 'content_id', 'voted_at'),
    'reports': ('_id', 'reporter_id', 'content_id', 'reason', 'status'),
    'counters': ('_id', 'value'),
}
MONGO_KEYS = {'upvotes': ('user_id', 'content_id')}


def clean(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat() + ('Z' if isinstance(value, datetime) and value.tzinfo is None else '')
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def record_snapshot(store, name, key=''):
    fields = (SQL_FIELDS if store == 'sql' else MONGO_FIELDS if store == 'mongo' else {}).get(name)
    if fields is None:
        abort(400, 'Choose an active application table or collection.')
    table = db.metadata.tables[name] if store == 'sql' else None
    keys = tuple(c.name for c in table.primary_key) if table is not None else MONGO_KEYS.get(name, ('_id',))
    filters = {}
    if key:
        values = [value.strip() for value in key.split(',')]
        if len(values) != len(keys) or any(not value or len(value) > 150 for value in values):
            abort(400, 'Enter one value for each key, separated by commas.')
        for column, value in zip(keys, values):
            if column not in ('run_key', '_id', 'source_item_id') or (column == '_id' and name != 'counters'):
                if not re.fullmatch(r'[1-9][0-9]{0,9}', value) or int(value) > 2147483647:
                    abort(400, 'Record IDs must be positive integers.')
                value = int(value)
            filters[column] = value
    if table is not None:
        columns = [getattr(Dish, field) if name == 'dish' and field in ('dish_name', 'price') else table.c[field] for field in fields]
        query = select(*columns).order_by(*(table.c[field].desc() for field in keys)).limit(20)
        for column, value in filters.items():
            query = query.where(table.c[column] == value)
        rows = [dict(row) for row in db.session.execute(query).mappings()]
    else:
        projection = {field: 1 for field in fields}
        if '_id' not in fields:
            projection['_id'] = 0
        rows = list(community_db()[name].find(filters, projection).sort([(field, -1) for field in keys]).limit(20))
    sql_counts = {name: db.session.scalar(select(func.count()).select_from(db.metadata.tables[name])) for name in SQL_FIELDS}
    mongo_counts = {name: community_db()[name].count_documents({}) for name in MONGO_FIELDS}
    return {'capturedAt': now().isoformat() + 'Z', 'readOnly': True,
            'sqlCounts': sql_counts, 'mongoCounts': mongo_counts,
            'selection': {'store': store, 'name': name, 'keys': list(keys), 'columns': list(fields), 'rows': clean(rows),
                          'total': (sql_counts if store == 'sql' else mongo_counts)[name], 'limit': 20, 'key': key}}
