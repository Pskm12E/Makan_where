import re
from functools import wraps
from flask import abort, g, request
from sqlalchemy import func, select
from .models import db, FoodPlace, Favourite


def payload():
    data = request.get_json()
    if not isinstance(data, dict):
        abort(400, "Expected a JSON object.")
    return data


def field(data, name, maximum, required=True):
    value = data.get(name, "")
    if not isinstance(value, str):
        abort(400, f"{name} must be text.")
    value = value.strip()
    if (required and not value) or len(value) > maximum:
        abort(400, f"{name} must contain {'1' if required else '0'}–{maximum} characters.")
    return value


def integer(value, name, minimum=1, maximum=2147483647):
    if isinstance(value, bool) or len(str(value)) > 10 or not re.fullmatch(r"[0-9]+", str(value)):
        abort(400, f"Invalid {name}.")
    number = int(value)
    if not minimum <= number <= maximum:
        abort(400, f"Invalid {name}.")
    return number


def authenticated(admin=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                abort(401, "Please log in to continue.")
            if admin and g.user.role != "admin":
                abort(403, "Administrator access is required.")
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def user_json(user):
    return None if not user else {
        "id": user.user_id, "fullName": user.display_name,
        "username": user.username, "email": user.email, "phone": user.phone,
        "role": user.role, "createdAt": user.created_at.isoformat() + "Z",
    }


def lookup(model, attribute, value):
    obj = db.session.scalar(select(model).where(getattr(model, attribute) == value))
    if not obj:
        obj = model(**{attribute: value})
        db.session.add(obj)
        db.session.flush()
    return obj


def active_place(place_id):
    place = db.get_or_404(FoodPlace, place_id)
    if place.archived_at:
        abort(404, "This place is no longer listed.")
    return place


def places_json(places):
    from .listing_details import listing_details
    ids = [p.place_id for p in places]
    if not ids:
        return []
    from .mongo import ratings as mongo_ratings
    ratings = {row["_id"]: row["rating"] for row in mongo_ratings(ids)}
    saves = dict(db.session.execute(select(Favourite.place_id, func.count())
        .where(Favourite.place_id.in_(ids)).group_by(Favourite.place_id)).all())
    return [{
        "id": p.place_id, "name": p.place_name, "category": p.category.category_name,
        "area": p.area.area_name, "address": p.address or "Address not listed",
        "cuisine": ", ".join(c.cuisine_name for c in p.cuisines) or "Cuisine not listed",
        "cuisines": [c.cuisine_name for c in p.cuisines],
        "hygieneGrade": p.hygiene_grade or "Not provided",
        "rating": float(ratings.get(p.place_id, 0)),
        "price": min((float(d.price) for d in p.dishes if d.is_available), default=None),
        "hasReferenceMenu": any(d.is_reference for d in p.dishes if d.is_available),
        "favouriteCount": saves.get(p.place_id, 0),
        "image": p.image_url, "tags": p.tags, "description": p.description,
        **listing_details(p),
        "latitude": float(p.latitude) if p.latitude is not None else None,
        "longitude": float(p.longitude) if p.longitude is not None else None,
        "source": p.source_name, "sourceUrl": p.source_url,
        "sourceFetchedAt": p.source_fetched_at.isoformat() + "Z" if p.source_fetched_at else None,
        "openingHours": p.opening_hours, "isSample": p.is_sample,
        "menu": [{"id": d.dish_id, "name": d.dish_name, "price": float(d.price),
                  "dietary": d.dietary_label, "description": d.description, "availability": d.is_available,
                  "isReference": d.is_reference, "sourceName": d.source_name, "sourceUrl": d.source_url,
                  "sourceObservedAt": d.source_observed_at.isoformat() + "Z" if d.source_observed_at else None} for d in p.dishes
                 if d.is_available or (g.user and g.user.role == "admin")],
    } for p in places]

