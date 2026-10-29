"""MongoDB owns community documents; SQL owns users/catalogue/favourites.

References across engines are checked by the application, not foreign keys.
Soft deletion retains referenced identities. No silent SQL fallback is used.
"""
from flask import current_app
from pymongo import MongoClient, ReturnDocument

ID = {"bsonType": ["int", "long"], "minimum": 1}
DATE = {"bsonType": "date"}
TEXT = {"bsonType": "string", "minLength": 1, "maxLength": 5000}
CONTENT_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "kind", "author_id", "place_id", "body", "created_at", "updated_at", "removed_at", "dishes"],
    "properties": {
        "_id": ID, "author_id": ID, "place_id": ID,
        "kind": {"enum": ["review", "thread", "comment"]}, "body": TEXT,
        "title": {"bsonType": "string", "maxLength": 150},
        "rating": {"bsonType": "int", "minimum": 1, "maximum": 5}, "thread_id": ID,
        "created_at": DATE, "updated_at": DATE,
        "removed_at": {"bsonType": ["date", "null"]},
        "removed_by_id": {"bsonType": ["int", "long", "null"]},
        "is_demo": {"bsonType": "bool"},
        "is_example": {"bsonType": "bool"},
        "revision": {"bsonType": "int", "minimum": 1},
        "request_key": {"bsonType": "string", "minLength": 16, "maxLength": 128},
        "request_hash": {"bsonType": "string", "minLength": 64, "maxLength": 64},
        "dishes": {"bsonType": "array", "maxItems": 20, "items": {
            "bsonType": "object", "required": ["dish_id", "feedback"],
            "properties": {"dish_id": ID, "feedback": {"bsonType": ["string", "null"], "maxLength": 1000}}}},
    },
    "oneOf": [
        {"properties": {"kind": {"enum": ["review"]}}, "required": ["rating", "title"], "not": {"required": ["thread_id"]}},
        {"properties": {"kind": {"enum": ["thread"]}}, "required": ["title"], "not": {"anyOf": [{"required": ["rating"]}, {"required": ["thread_id"]}]}},
        {"properties": {"kind": {"enum": ["comment"]}}, "required": ["thread_id"], "not": {"required": ["rating"]}},
    ],
}
VALIDATORS = {
    "content": {"$and": [{"$jsonSchema": CONTENT_SCHEMA}, {"$or": [
        {"removed_at": None, "removed_by_id": None},
        {"removed_at": {"$type": "date"}, "removed_by_id": {"$type": ["int", "long"]}},
    ]}]},
    "upvotes": {"$jsonSchema": {"bsonType": "object", "required": ["user_id", "content_id", "voted_at"],
        "properties": {"user_id": ID, "content_id": ID, "voted_at": DATE}}},
    "reports": {"$jsonSchema": {"bsonType": "object", "required": ["_id", "reporter_id", "content_id", "reason", "status", "created_at"],
        "properties": {"_id": ID, "reporter_id": ID, "content_id": ID,
                       "reason": {"bsonType": "string", "minLength": 1, "maxLength": 1000},
                       "status": {"enum": ["open", "resolved", "dismissed"]}, "created_at": DATE,
                       "resolved_by_id": ID, "resolved_at": DATE,
                       "resolution_note": {"bsonType": "string", "minLength": 1, "maxLength": 1000}},
        "oneOf": [
            {"properties": {"status": {"enum": ["open"]}},
             "not": {"anyOf": [{"required": ["resolved_by_id"]}, {"required": ["resolved_at"]}, {"required": ["resolution_note"]}]}},
            {"properties": {"status": {"enum": ["resolved", "dismissed"]}},
             "required": ["resolved_by_id", "resolved_at", "resolution_note"]},
        ]}},
}


def init_client(app):
    uri = app.config.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("Set MONGODB_URI; SQL and MongoDB are both required.")
    client = MongoClient(uri, serverSelectionTimeoutMS=4000, connectTimeoutMS=4000, appname="MakanWhere")
    app.extensions["community_client"] = client
    app.extensions["community_db"] = client[app.config["MONGODB_DATABASE"]]


def community_db():
    return current_app.extensions["community_db"]


def init_collections():
    mongo = community_db()
    existing = mongo.list_collection_names()
    if 'reports' in existing:
        mongo.reports.update_many({'status': 'open', 'resolved_by_id': None, 'resolved_at': None, 'resolution_note': None},
            {'$unset': {'resolved_by_id': '', 'resolved_at': '', 'resolution_note': ''}})
    # Refuse to silently approve malformed history when tightening validators.
    if 'reports' in existing and mongo.reports.count_documents({'$nor': [VALIDATORS['reports']]}):
        raise ValueError('Existing moderation records violate the resolution contract. Audit and repair them before init-mongo.')
    if 'content' in existing:
        mongo.content.update_many({'revision': {'$exists': False}}, {'$set': {'revision': 1}})
    for name, validator in VALIDATORS.items():
        if name in existing:
            mongo.command("collMod", name, validator=validator, validationLevel="strict", validationAction="error")
        else:
            mongo.create_collection(name, validator=validator, validationLevel="strict", validationAction="error")
    mongo.content.create_index([("place_id", 1), ("removed_at", 1), ("kind", 1), ("_id", 1)], name="place_feed")
    mongo.content.create_index([("thread_id", 1), ("removed_at", 1)], name="thread_replies")
    mongo.content.create_index("seed_key", unique=True, partialFilterExpression={"seed_key": {"$type": "string"}})
    mongo.content.create_index([('author_id', 1), ('request_key', 1)], unique=True,
        name='one_content_per_request', partialFilterExpression={'request_key': {'$type': 'string'}})
    mongo.upvotes.create_index([("user_id", 1), ("content_id", 1)], unique=True, name="one_vote_per_user")
    mongo.upvotes.create_index("content_id")
    mongo.reports.create_index([("status", 1), ("created_at", 1)])
    mongo.reports.create_index("seed_key", unique=True, partialFilterExpression={"seed_key": {"$type": "string"}})


def next_id(name):
    return community_db().counters.find_one_and_update(
        {"_id": name}, {"$inc": {"value": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER)["value"]


def rating_pipeline(place_ids):
    return [
        {"$match": {"kind": "review", "removed_at": None, "is_example": {"$ne": True}, "place_id": {"$in": place_ids}}},
        {"$group": {"_id": "$place_id", "rating": {"$avg": "$rating"}, "reviewCount": {"$sum": 1}}},
        {"$sort": {"rating": -1, "reviewCount": -1, "_id": 1}},
    ]


def ratings(place_ids):
    return list(community_db().content.aggregate(rating_pipeline(place_ids))) if place_ids else []
