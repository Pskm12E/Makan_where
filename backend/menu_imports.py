"""Previewed, source-attributed SQL menu imports for admins and integrations.

No arbitrary URL fetching and no credentials in browser code. A narrow bearer
key permits only this importer; it grants no account/moderation/schema access.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from flask import abort, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select

from .models import db, Dish, FoodPlace, PopulationRun
from .services import authenticated, field, integer, payload
from .config import BASE_DIR


def require_import_key():
    expected = current_app.config.get("MENU_IMPORT_API_KEY", "")
    if not expected:
        abort(503, "Menu API imports are not configured. Use administrator sign-in.")
    supplied = request.headers.get("Authorization", "")
    if not supplied.startswith("Bearer ") or not hmac.compare_digest(
            supplied[7:].encode("utf-8"), expected.encode("utf-8")):
        abort(401, "A valid menu import API key is required.")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def normalise_menu(data):
    if not isinstance(data, dict):
        abort(400, "menu must be a JSON object.")
    source = field(data, "sourceName", 80)
    url = field(data, "sourceUrl", 500)
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in url):
            raise ValueError()
        observed = datetime.fromisoformat(field(data, "observedAt", 40).replace("Z", "+00:00"))
        if observed.tzinfo is None or observed > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError()
    except ValueError:
        abort(400, "Use a public HTTPS source URL and a past observedAt timestamp with a timezone.")
    if data.get("currency") != "SGD":
        abort(400, "Menu prices must be in SGD; currency conversion is not automatic.")
    reference = data.get("isReference", False)
    if not isinstance(reference, bool):
        abort(400, "isReference must be true or false.")
    targets, items = data.get("places"), data.get("items")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 100:
        abort(400, "Choose between 1 and 100 establishments.")
    if len(targets) > 1 and not reference:
        abort(400, "A shared chain menu must be labelled isReference. Outlet menus target one venue.")
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        abort(400, "Supply between 1 and 100 menu items.")
    places, entries, seen_places, seen_ids, seen_names = [], [], set(), set(), set()
    for target in targets:
        if not isinstance(target, dict):
            abort(400, "Each establishment must include its id, name and catalogue sourceId.")
        pid = integer(target.get("id"), "place id")
        if pid in seen_places:
            abort(400, "An establishment appears more than once.")
        seen_places.add(pid)
        places.append({"id": pid, "name": field(target, "name", 150),
                       "sourceId": field(target, "sourceId", 80, False)})
    for item in items:
        if not isinstance(item, dict):
            abort(400, "Each menu item must be an object.")
        identifier, name = field(item, "sourceId", 100), field(item, "name", 150)
        if identifier.casefold() in seen_ids or name.casefold() in seen_names:
            abort(400, "Menu item source IDs and names must be unique within an import.")
        seen_ids.add(identifier.casefold())
        seen_names.add(name.casefold())
        try:
            price = Decimal(str(item.get("price")))
            if not price.is_finite() or not 0 <= price <= 99999999 or price.as_tuple().exponent < -2:
                raise ValueError()
        except (InvalidOperation, ValueError):
            abort(400, "Every item needs a valid nonnegative SGD price with at most two decimal places.")
        entries.append({"sourceId": identifier, "name": name, "price": format(price, ".2f"),
                        "description": field(item, "description", 1000, False),
                        "dietary": field(item, "dietary", 80, False)})
    return {"sourceName": source, "sourceUrl": url,
            "observedAt": observed.astimezone(timezone.utc).isoformat(), "currency": "SGD",
            "isReference": reference, "places": sorted(places, key=lambda p: p["id"]), "items": entries}


def inspect_import(menu, *, lock=False):
    ids = [p["id"] for p in menu["places"]]
    query = select(FoodPlace).where(FoodPlace.place_id.in_(ids)).order_by(FoodPlace.place_id)
    if lock:
        query = query.with_for_update()
    places = {p.place_id: p for p in db.session.scalars(query)}
    dishes = list(db.session.scalars(select(Dish).where(Dish.place_id.in_(ids)).order_by(Dish.dish_id)))
    existing = {(d.place_id, (d.source_name or "").casefold(), (d.source_item_id or "").casefold()) for d in dishes}
    names = {(d.place_id, d.dish_name.casefold()) for d in dishes}
    new, skipped, conflicts = [], 0, []
    summary = []
    for target in menu["places"]:
        place = places.get(target["id"])
        if not place or place.archived_at:
            abort(400, f"Establishment {target['id']} is missing or archived.")
        if place.place_name != target["name"] or (place.source_id or "") != target["sourceId"]:
            abort(409, f"Establishment {target['id']} does not match the supplied name/sourceId. Reload its import template.")
        added_here = 0
        for item in menu["items"]:
            key = (place.place_id, menu["sourceName"].casefold(), item["sourceId"].casefold())
            if key in existing:
                skipped += 1
            elif (place.place_id, item["name"].casefold()) in names:
                conflicts.append({"placeId": place.place_id, "name": item["name"]})
            else:
                new.append((place.place_id, item))
                added_here += 1
        summary.append({"id": place.place_id, "name": place.place_name, "address": place.address,
                        "newItems": added_here})
    state = {"places": [(p.place_id, p.place_name, p.source_id, p.archived_at) for p in places.values()],
             "dishes": [(d.dish_id, d.place_id, d.dish_name, d.price, d.is_available,
                          d.source_name, d.source_item_id, d.source_observed_at,
                          d.description, d.dietary_label, d.is_reference) for d in dishes]}
    return {"added": len(new), "skipped": skipped, "conflicts": conflicts, "places": summary}, new, digest(state)


def import_request(actor):
    data = payload()
    menu = normalise_menu(data.get("menu"))
    apply = data.get("apply", False)
    if not isinstance(apply, bool):
        abort(400, "apply must be true or false.")
    signer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="menu-import-preview-v1")
    summary, new, state = inspect_import(menu, lock=apply)
    fingerprint = {"menu": digest(menu), "state": state, "actor": actor}
    if not apply:
        return jsonify(**summary, menu=menu, previewToken=signer.dumps(fingerprint), applied=False)
    token = data.get("previewToken")
    if not isinstance(token, str):
        abort(400, "Preview this menu before importing it.")
    try:
        checked = signer.loads(token, max_age=900)
    except (BadSignature, SignatureExpired):
        abort(409, "The import preview expired or is invalid. Preview again.")
    if checked != fingerprint:
        abort(409, "The menu or catalogue changed after preview. Preview again.")
    if summary["conflicts"]:
        abort(409, "Existing dishes have matching names from another source. Resolve those in Manage menu first.")
    observed = datetime.fromisoformat(menu["observedAt"]).replace(tzinfo=None)
    for place_id, item in new:
        db.session.add(Dish(place_id=place_id, dish_name=item["name"], price=Decimal(item["price"]),
            description=item["description"], dietary_label=item["dietary"], is_available=True,
            source_name=menu["sourceName"], source_item_id=item["sourceId"], source_url=menu["sourceUrl"],
            source_observed_at=observed, is_reference=menu["isReference"]))
    if new:
        db.session.add(PopulationRun(run_key="menu:" + fingerprint["menu"], details={
            "operation": "menu_import", "sourceName": menu["sourceName"], "sourceUrl": menu["sourceUrl"],
            "observedAt": menu["observedAt"], "isReference": menu["isReference"], "actor": actor,
            "added": len(new), "placeIds": [p["id"] for p in menu["places"]]}))
    db.session.commit()  # all menu rows and receipt commit together
    return jsonify(**summary, applied=True)


def register_menu_imports(app, limiter):
    @app.get("/api/admin/menu-imports/kfc-reference")
    @authenticated(admin=True)
    def kfc_reference_menu():
        menu = json.loads((BASE_DIR / "data/menus/kfc_sg_reference_20261004.json").read_text(encoding="utf-8"))
        menu.pop("matchNames")
        places = list(db.session.scalars(select(FoodPlace).where(
            FoodPlace.place_name == "KFC", FoodPlace.archived_at.is_(None), FoodPlace.is_sample.is_(False))
            .order_by(FoodPlace.place_id)))
        menu["places"] = [{"id": p.place_id, "name": p.place_name, "sourceId": p.source_id or ""}
                          for p in places if p.place_name == "KFC"]
        if not menu["places"]:
            abort(404, "No imported KFC establishments are available in this catalogue.")
        return jsonify(menu)

    @app.get("/api/integrations/menu-targets")
    @limiter.limit("30 per hour")
    def integration_menu_targets():
        name = field(request.args, "name", 150)
        places = list(db.session.scalars(select(FoodPlace).where(
            FoodPlace.place_name == name, FoodPlace.archived_at.is_(None), FoodPlace.is_sample.is_(False))
            .order_by(FoodPlace.place_id).limit(101)))
        # Python equality avoids silently broadening a chain match on a
        # case/accent-insensitive SQL collation.
        places = [p for p in places if p.place_name == name]
        if len(places) > 100:
            abort(400, "More than 100 establishments match. Supply an explicit reviewed places list.")
        return jsonify(places=[{"id": p.place_id, "name": p.place_name, "sourceId": p.source_id or "",
                                "address": p.address} for p in places])

    @app.post("/api/integrations/menu-imports")
    @limiter.limit("30 per hour")
    def integration_menu_import():
        return import_request("integration")

    @app.post("/api/admin/menu-imports")
    @authenticated(admin=True)
    @limiter.limit("30 per hour")
    def admin_menu_import():
        return import_request(f"admin:{g.user.user_id}")

    @app.get("/api/admin/menu-imports")
    @authenticated(admin=True)
    def menu_import_status():
        venues = db.session.scalar(select(func.count()).select_from(FoodPlace).where(FoodPlace.archived_at.is_(None)))
        covered = db.session.scalar(select(func.count(func.distinct(Dish.place_id))).join(
            FoodPlace, FoodPlace.place_id == Dish.place_id).where(FoodPlace.archived_at.is_(None), Dish.is_available.is_(True)))
        history = list(db.session.scalars(select(PopulationRun).where(PopulationRun.run_key.like("menu:%"))
                                         .order_by(PopulationRun.created_at.desc()).limit(20)))
        return jsonify(apiConfigured=bool(app.config.get("MENU_IMPORT_API_KEY")),
                       venues=venues, withMenu=covered, missingMenu=venues-covered,
                       history=[{"createdAt": r.created_at.isoformat() + "Z", **r.details} for r in history])

    @app.get("/api/admin/establishments/<int:place_id>/menu-template")
    @authenticated(admin=True)
    def menu_template(place_id):
        from .services import active_place
        place = active_place(place_id)
        return jsonify(sourceName="", sourceUrl="", observedAt=datetime.now(timezone.utc).isoformat(),
                       currency="SGD", isReference=False,
                       places=[{"id": place.place_id, "name": place.place_name, "sourceId": place.source_id or ""}],
                       items=[])
