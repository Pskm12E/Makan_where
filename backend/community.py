"""Live MongoDB CRUD, with SQL reference checks and bounded embedded feedback."""
import hashlib
import json
import re
from flask import abort, g, jsonify, request
from pymongo.errors import DuplicateKeyError
from sqlalchemy import select
from .models import db, User, FoodPlace, Dish, now
from .mongo import community_db, next_id
from .services import authenticated, active_place, field, integer, payload


def visible(content_id):
    item = community_db().content.find_one({"_id": content_id, "removed_at": None})
    if not item:
        abort(404, "Content not found.")
    active_place(item["place_id"])
    if item["kind"] == "comment" and not community_db().content.find_one(
            {"_id": item["thread_id"], "kind": "thread", "removed_at": None}):
        abort(404, "This discussion has been removed.")
    return item


def dish_feedback(data, place_id):
    links = data.get("dishes", [])
    if not isinstance(links, list) or len(links) > 20:
        abort(400, "Choose at most 20 dishes.")
    result, seen = [], set()
    for link in links:
        if not isinstance(link, dict):
            abort(400, "Invalid dish feedback.")
        dish_id = integer(link.get("id"), "dish id")
        dish = db.get_or_404(Dish, dish_id)
        if not dish.is_available or dish.place_id != place_id or dish_id in seen:
            abort(400, "Dishes must be available, unique and belong to this place.")
        seen.add(dish_id)
        result.append({"dish_id": dish_id, "feedback": field(link, "feedback", 1000, False) or None})
    return result


def serialize(items):
    """Batch both-engine lookups, avoiding one query per author/dish/vote."""
    if not items:
        return []
    ids = [c["_id"] for c in items]
    users = dict(db.session.execute(select(User.user_id, User.display_name).where(
        User.user_id.in_({c["author_id"] for c in items}))).all())
    dish_ids = {d["dish_id"] for c in items for d in c["dishes"]}
    dishes = dict(db.session.execute(select(Dish.dish_id, Dish.dish_name).where(Dish.dish_id.in_(dish_ids))).all()) if dish_ids else {}
    votes = {v["_id"]: v["count"] for v in community_db().upvotes.aggregate([
        {"$match": {"content_id": {"$in": ids}}}, {"$group": {"_id": "$content_id", "count": {"$sum": 1}}}])}
    own = {v["content_id"] for v in community_db().upvotes.find(
        {"content_id": {"$in": ids}, "user_id": g.user.user_id}, {"content_id": 1})} if g.user else set()
    return [{"id": c["_id"], "kind": c["kind"], "authorId": c["author_id"], "establishmentId": c["place_id"],
        "reviewer": users.get(c["author_id"], "Unavailable account"), "text": c["body"], "title": c.get("title", ""),
        "rating": c.get("rating"), "threadId": c.get("thread_id"), "createdAt": c["created_at"].isoformat() + "Z",
        "revision": c.get('revision', 1),
        "isDemo": c.get("is_demo", False), "isExample": c.get("is_example", False), "tags": [], "upvoteCount": votes.get(c["_id"], 0), "upvoted": c["_id"] in own,
        "dishes": [{"id": d["dish_id"], "name": dishes.get(d["dish_id"], "Unavailable dish"), "feedback": d["feedback"]} for d in c["dishes"]]
    } for c in items]


def register_community(app, limiter):
    @app.get('/api/content/<int:content_id>')
    def get_content(content_id):
        item = visible(content_id)
        response = jsonify(content=serialize([item])[0])
        response.set_etag(str(item.get('revision', 1)))
        return response

    @app.get("/api/reviews")
    @app.get("/api/content")
    def list_content():
        cursor = integer(request.args.get("cursor", 0), "cursor", 0)
        query = {"removed_at": None, "_id": {"$gt": cursor}}
        if request.path.endswith("reviews"):
            query["kind"] = "review"
        if request.args.get("place_id"):
            place_id = integer(request.args["place_id"], "place_id")
            active_place(place_id)
            query["place_id"] = place_id
        else:
            query["place_id"] = {"$in": list(db.session.scalars(select(FoodPlace.place_id).where(FoodPlace.archived_at.is_(None))))}
        # A self lookup hides comments whose parent has been soft-removed.
        items = list(community_db().content.aggregate([
            {"$match": query}, {"$sort": {"_id": 1}},
            {"$lookup": {"from": "content", "localField": "thread_id", "foreignField": "_id", "as": "parent"}},
            {"$match": {"$or": [{"kind": {"$ne": "comment"}}, {"parent": {"$elemMatch": {"kind": "thread", "removed_at": None}}}]}},
            {"$limit": 101}, {"$unset": "parent"},
        ]))
        return jsonify(content=serialize(items[:100]), nextCursor=items[99]["_id"] if len(items) > 100 else None)

    @app.post("/api/content")
    @app.post("/api/reviews")
    @authenticated()
    @limiter.limit("20 per hour")
    def create_content():
        data = payload()
        key = request.headers.get('Idempotency-Key', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', key):
            abort(400, 'Supply an Idempotency-Key of 16–128 letters, digits, dashes or underscores. Reuse it only when retrying this post.')
        request_hash = hashlib.sha256(json.dumps({'route': request.path, 'body': data}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        identity = {'author_id': g.user.user_id, 'request_key': key}
        existing = community_db().content.find_one(identity)
        if existing:
            if existing.get('request_hash') != request_hash:
                abort(409, 'That request key was already used for different content.')
            return jsonify(content=serialize([existing])[0], replayed=True), 200
        kind = "review" if request.path.endswith("reviews") else data.get("kind")
        if not isinstance(kind, str) or kind not in {"review", "thread", "comment"}:
            abort(400, "Choose review, thread or comment.")
        place_id = integer(data.get("placeId"), "placeId")
        active_place(place_id)
        item = {"kind": kind, "place_id": place_id, "author_id": g.user.user_id,
                "body": field(data, "text", 5000), "created_at": now(), "updated_at": now(),
                "removed_at": None, "removed_by_id": None, "is_demo": False,
                "dishes": dish_feedback(data, place_id)}
        item.update(revision=1, request_key=key, request_hash=request_hash)
        if kind in {"review", "thread"}:
            item["title"] = field(data, "title", 150)
        if kind == "review":
            item["rating"] = integer(data.get("rating"), "rating", 1, 5)
        if kind == "comment":
            item["thread_id"] = integer(data.get("threadId"), "threadId")
            parent = visible(item["thread_id"])
            if parent["kind"] != "thread" or parent["place_id"] != place_id:
                abort(400, "A reply must belong to a discussion at this same place.")
        item["_id"] = next_id("content")
        try:
            community_db().content.insert_one(item)  # document and request receipt are atomic together
        except DuplicateKeyError:
            existing = community_db().content.find_one(identity)
            if existing is None:
                raise
            if existing.get('request_hash') != request_hash:
                abort(409, 'That request key was already used for different content.')
            return jsonify(content=serialize([existing])[0], replayed=True), 200
        return jsonify(content=serialize([item])[0], replayed=False), 201

    @app.route("/api/content/<int:content_id>", methods=["PATCH", "DELETE"])
    @authenticated()
    def change_content(content_id):
        item = visible(content_id)
        revision = request.headers.get('If-Match', '').strip('"')
        if not revision:
            abort(428, 'Reload this post and supply its revision using If-Match.')
        expected = integer(revision, 'revision')
        if request.method == "DELETE":
            if item["author_id"] != g.user.user_id and g.user.role != "admin":
                abort(403, "Only the author or an administrator can remove this content.")
            changes = {"removed_at": now(), "removed_by_id": g.user.user_id}
        else:
            if item["author_id"] != g.user.user_id:
                abort(403, "Only the author can edit this content.")
            data = payload()
            changes = {"body": field(data, "text", 5000), "updated_at": now()}
            if item["kind"] != "comment":
                changes["title"] = field(data, "title", 150)
            if item["kind"] == "review":
                changes["rating"] = integer(data.get("rating"), "rating", 1, 5)
            if "dishes" in data:
                changes["dishes"] = dish_feedback(data, item["place_id"])
        revision_match = {'revision': expected} if 'revision' in item else {'revision': {'$exists': False}}
        if expected != item.get('revision', 1):
            abort(409, 'This post changed since you loaded it. Reload before editing.')
        result = community_db().content.update_one({"_id": content_id, "removed_at": None, **revision_match},
            {"$set": {**changes, 'revision': expected + 1}})
        if not result.matched_count:
            abort(409, "Content changed. Refresh and try again.")
        return jsonify(ok=True, revision=expected + 1)

    @app.route("/api/content/<int:content_id>/upvote", methods=["PUT", "DELETE"])
    @authenticated()
    def upvote(content_id):
        item = visible(content_id)
        identity = {"user_id": g.user.user_id, "content_id": content_id}
        if request.method == "PUT":
            community_db().upvotes.update_one(identity, {"$setOnInsert": {"voted_at": now()}}, upsert=True)
        else:
            community_db().upvotes.delete_one(identity)
        return jsonify(content=serialize([item])[0])

    @app.post("/api/content/<int:content_id>/reports")
    @authenticated()
    @limiter.limit("10 per hour")
    def report_content(content_id):
        visible(content_id)
        reason = field(payload(), "reason", 1000)
        identifier = next_id("reports")
        community_db().reports.insert_one({"_id": identifier, "reporter_id": g.user.user_id,
            "content_id": content_id, "reason": reason, "status": "open", "created_at": now()})
        return jsonify(id=identifier), 201

    @app.get("/api/admin/reports")
    @authenticated(admin=True)
    def reports():
        items = list(community_db().reports.find({"status": "open"}).sort("created_at", 1).limit(200))
        content = {c["_id"]: c["body"] for c in community_db().content.find(
            {"_id": {"$in": [r["content_id"] for r in items]}}, {"body": 1})}
        return jsonify(reports=[{"id": r["_id"], "contentId": r["content_id"], "reason": r["reason"],
            "status": r["status"], "text": content.get(r["content_id"], "Unavailable content")} for r in items])

    @app.patch("/api/admin/reports/<int:report_id>")
    @authenticated(admin=True)
    def resolve_report(report_id):
        data = payload()
        if not isinstance(data.get("status"), str) or data["status"] not in {"resolved", "dismissed"}:
            abort(400, "Choose resolved or dismissed.")
        note = field(data, "note", 1000)
        result = community_db().reports.update_one({"_id": report_id, "status": "open"}, {"$set": {
            "status": data["status"], "resolution_note": note, "resolved_at": now(), "resolved_by_id": g.user.user_id}})
        if not result.matched_count:
            abort(409, "Report missing or already resolved.")
        return jsonify(ok=True)
