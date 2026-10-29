import re
import gzip
import secrets
from decimal import Decimal, InvalidOperation
from flask import abort, g, jsonify, request, session
from sqlalchemy import delete, or_, select
from .passwords import hash_password, verify_password, needs_upgrade
from .models import (db, Area, Category, Cuisine, FoodPlace, Dish, User, Favourite,
                     DiscoveryEvent, now)
from .services import (payload, field, integer, authenticated, user_json, lookup,
                       active_place, places_json)


def save_place(place, data):
    place.place_name = field(data, "name", 150)
    place.address = field(data, "address", 255, False)
    place.area = lookup(Area, "area_name", field(data, "area", 100))
    place.category = lookup(Category, "category_name", field(data, "category", 100))
    cuisines = [c.strip() for c in field(data, "cuisine", 500, False).split(",") if c.strip()]
    if len(cuisines) > 10 or any(len(c) > 100 for c in cuisines):
        abort(400, "Choose up to 10 cuisines with names up to 100 characters.")
    place.cuisines = [lookup(Cuisine, "cuisine_name", name) for name in dict.fromkeys(cuisines)]
    if 'tags' in data:
        try:
            place.tags = data['tags']
        except ValueError as error:
            abort(400, str(error))
    for field_name, bound in [('latitude', 90), ('longitude', 180)]:
        if field_name in data:
            try:
                value = None if data[field_name] is None else Decimal(str(data[field_name]))
                if value is not None and (not value.is_finite() or not -bound <= value <= bound):
                    raise ValueError()
            except (InvalidOperation, ValueError):
                abort(400, f'Invalid {field_name}.')
            setattr(place, field_name, value)
    if 'hygieneGrade' in data:
        grade = data['hygieneGrade'] or None
        if grade is not None and grade not in ('A', 'B', 'C', 'D'):
            abort(400, 'Hygiene grade must be A, B, C, D or unknown.')
        place.hygiene_grade = grade
    from .listing_details import save_details
    save_details(place, data)


def profile_fields(data):
    email = field(data, "email", 254).lower()
    username = field(data, "username", 50).lower()
    phone = field(data, "phone", 25, False)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        abort(400, "Enter a valid email address.")
    if not re.fullmatch(r"[a-z0-9_.-]{3,50}", username):
        abort(400, "Username needs 3–50 letters, numbers, dots, dashes or underscores.")
    if phone and not re.fullmatch(r"\+?[0-9 ()-]{8,25}", phone):
        abort(400, "Enter a valid phone number or leave it blank.")
    return dict(display_name=field(data, "fullName", 100), username=username, email=email, phone=phone)


def save_dish(dish, data):
    # Blank keeps the source's unknown price on an existing unpriced reference.
    if dish.menu_entry and dish.menu_entry.reference_price is None and data.get('price') in (None, ''):
        price = None
    else:
        try:
            price = Decimal(str(data.get("price")))
            if not price.is_finite() or not 0 <= price <= 99999999 or price.as_tuple().exponent < -2:
                raise ValueError()
        except (InvalidOperation, ValueError):
            abort(400, "Enter a price with at most two decimal places.")
    availability = data.get("availability", True if dish.is_available is None else dish.is_available)
    if not isinstance(availability, bool):
        abort(400, "Availability must be true or false.")
    dish.dish_name = field(data, "name", 150)
    dish.price = price
    dish.dietary_label = field(data, "dietary", 80, False)
    if "description" in data:
        dish.description = field(data, "description", 1000, False)
    dish.is_available = availability


def register_routes(app, limiter):
    @app.get("/api/session")
    def current_session():
        session.setdefault("csrf", secrets.token_urlsafe(32))
        favourites = list(db.session.scalars(select(Favourite.place_id).where(Favourite.user_id == g.user.user_id))) if g.user else []
        return jsonify(user=user_json(g.user), csrfToken=session["csrf"], favourites=favourites, sampleCatalogue=app.config["SAMPLE_CATALOGUE"])

    def establish_session(user):
        session.clear()
        session["user_id"] = user.user_id
        session["csrf"] = secrets.token_urlsafe(32)
        session.permanent = True
        return jsonify(user=user_json(user), csrfToken=session["csrf"])

    @app.post("/api/register")
    @limiter.limit("5 per hour")
    def register():
        data = payload()
        values = profile_fields(data)
        password = data.get("password")
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            abort(400, "Password must be 8–128 characters.")
        user = User(**values, password_hash=hash_password(password), role="user")
        db.session.add(user)
        db.session.commit()
        return establish_session(user), 201

    with app.app_context():
        dummy_hash = hash_password(secrets.token_urlsafe(32))

    @app.post("/api/login")
    @limiter.limit("10 per minute")
    def login():
        data = payload()
        identity = field(data, "identity", 254).lower()
        password = data.get("password")
        if not isinstance(password, str) or len(password) > 128:
            abort(400, "Invalid login details.")
        user = db.session.scalar(select(User).where(or_(User.username == identity, User.email == identity)))
        valid = verify_password(user.password_hash if user else dummy_hash, password)
        if not user or not valid:
            abort(401, "Email, username or password is incorrect.")
        if data.get("adminOnly") is True and user.role != "admin":
            abort(403, "This account does not have administrator access.")
        if needs_upgrade(user.password_hash):
            user.password_hash = hash_password(password)
            db.session.commit()
        return establish_session(user)

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.patch("/api/profile")
    @authenticated()
    def profile():
        for key, value in profile_fields(payload()).items():
            setattr(g.user, key, value)
        db.session.commit()
        return jsonify(user=user_json(g.user))

    @app.get("/api/establishments")
    def list_places():
        cursor = integer(request.args.get("cursor", 0), "cursor", 0)
        limit = integer(request.args.get("limit", 100), "limit", 1, 200)
        places = list(db.session.scalars(select(FoodPlace).where(FoodPlace.archived_at.is_(None), FoodPlace.place_id > cursor).order_by(FoodPlace.place_id).limit(limit + 1)))
        return jsonify(establishments=places_json(places[:limit]), nextCursor=places[limit - 1].place_id if len(places) > limit else None)

    @app.get("/api/catalogue")
    def catalogue():
        # Compact public catalogue for client-side filters. Keep detail-only
        # provenance out of this payload; compress this public response only.
        places = list(db.session.scalars(select(FoodPlace).where(FoodPlace.archived_at.is_(None)).order_by(FoodPlace.place_id).limit(20001)))
        if len(places) > 20000:
            abort(503, "The catalogue needs server-side search before expanding further.")
        items = places_json(places)
        for item in items:
            for key in ['description','latitude','longitude','source','sourceUrl','sourceFetchedAt','openingHours']:
                item.pop(key, None)
        response = jsonify(establishments=items)
        if request.accept_encodings['gzip'] > 0:
            response.set_data(gzip.compress(response.get_data(), compresslevel=5, mtime=0))
            response.headers['Content-Encoding'] = 'gzip'
        response.vary.add('Accept-Encoding')
        return response

    @app.get("/api/establishments/<int:place_id>")
    def get_place(place_id):
        return jsonify(establishment=places_json([active_place(place_id)])[0])

    @app.route("/api/favourites/<int:place_id>", methods=["PUT", "DELETE"])
    @authenticated()
    def favourite(place_id):
        active_place(place_id)
        if request.method == "PUT":
            # One database statement arbitrates concurrent saves. A prior SELECT
            # races with another request and turns an idempotent PUT into a 409.
            values = dict(user_id=g.user.user_id, place_id=place_id)
            if db.engine.dialect.name == 'sqlite':
                from sqlalchemy.dialects.sqlite import insert
                statement = insert(Favourite).values(**values).on_conflict_do_nothing(index_elements=['user_id','place_id'])
            else:
                from sqlalchemy.dialects.mysql import insert
                statement = insert(Favourite).values(**values)
                statement = statement.on_duplicate_key_update(place_id=statement.inserted.place_id)
            db.session.execute(statement)
        else:
            db.session.execute(delete(Favourite).where(Favourite.user_id == g.user.user_id, Favourite.place_id == place_id))
        db.session.commit()
        return jsonify(favourites=list(db.session.scalars(select(Favourite.place_id).where(Favourite.user_id == g.user.user_id))))

    @app.post("/api/events")
    @limiter.limit("30 per minute")
    def discovery_event():
        data = payload()
        kind = data.get("type")
        if not isinstance(kind, str) or kind not in {"search", "place_view"}:
            abort(400, "Invalid discovery event.")
        place_id = integer(data["placeId"], "placeId") if data.get("placeId") is not None else None
        if kind == "place_view" and place_id is None:
            abort(400, "A place view needs a place.")
        if place_id:
            active_place(place_id)
        db.session.add(DiscoveryEvent(event_type=kind, place_id=place_id, user_id=g.user.user_id if g.user else None))
        db.session.commit()
        return jsonify(ok=True), 201

    @app.get("/api/analytics")
    def analytics():
        from .analytics import food_insights
        return jsonify(food_insights())

    @app.post("/api/admin/establishments")
    @authenticated(admin=True)
    def add_place():
        place = FoodPlace()
        with db.session.no_autoflush:
            save_place(place, payload())
        db.session.add(place)
        db.session.commit()
        return jsonify(establishment=places_json([place])[0]), 201

    @app.get("/api/admin/schema")
    @authenticated(admin=True)
    @limiter.limit("20 per minute")
    def schema():
        from .schema import application_schema
        return jsonify(application_schema())

    @app.get("/api/admin/schema-records")
    @authenticated(admin=True)
    @limiter.limit("20 per minute")
    def schema_records():
        from .schema_records import record_snapshot
        return jsonify(record_snapshot(request.args.get('store', 'sql'), request.args.get('table', 'dish'), request.args.get('key', '').strip()))

    @app.post("/api/admin/schema/preview")
    @authenticated(admin=True)
    @limiter.limit("10 per minute")
    def schema_preview():
        from .schema_editor import preview
        return jsonify(preview(payload().get('change')))

    @app.post("/api/admin/schema/apply")
    @authenticated(admin=True)
    @limiter.limit("10 per minute")
    def schema_apply():
        from .schema_editor import apply
        data = payload()
        return jsonify(apply(data.get('change'), data.get('previewToken')))

    @app.route("/api/admin/establishments/<int:place_id>", methods=["PATCH", "DELETE"])
    @authenticated(admin=True)
    def update_place(place_id):
        place = active_place(place_id)
        if request.method == "DELETE":
            place.archived_at = now()
        else:
            with db.session.no_autoflush:
                save_place(place, payload())
        db.session.commit()
        return jsonify(ok=True)

    @app.post("/api/admin/establishments/<int:place_id>/dishes")
    @authenticated(admin=True)
    def add_dish(place_id):
        active_place(place_id)
        dish = Dish(place_id=place_id)
        save_dish(dish, payload())
        db.session.add(dish)
        db.session.commit()
        return jsonify(id=dish.dish_id), 201

    @app.route("/api/admin/establishments/<int:place_id>/dishes/<int:dish_id>", methods=["PATCH", "DELETE"])
    @authenticated(admin=True)
    def change_dish(place_id, dish_id):
        active_place(place_id)
        dish = db.get_or_404(Dish, dish_id)
        if dish.place_id != place_id:
            abort(404, "Dish not found at this establishment.")
        if request.method == "DELETE":
            dish.is_available = False
        else:
            previous = (dish.dish_name, dish.price, dish.dietary_label, dish.description)
            save_dish(dish, payload())
            if previous != (dish.dish_name, dish.price, dish.dietary_label, dish.description):
                # Keep import identity (re-imports preserve edits), but do not
                # present an edited price as freshly verified against its source.
                dish.source_observed_at = None
        db.session.commit()
        return jsonify(ok=True)
