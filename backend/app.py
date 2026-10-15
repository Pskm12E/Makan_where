"""Same-origin Flask API. Run from the repository root with --app backend.app."""
import hmac
import secrets
from flask import Flask, abort, g, jsonify, request, send_from_directory, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import BASE_DIR, Config
from .models import db, User, FoodPlace
from pymongo.errors import PyMongoError, DuplicateKeyError
from .mongo import init_client, community_db


def create_app(overrides=None):
    app = Flask(__name__, static_folder=None)
    # Mongo compound index and $sort field order has meaning. Preserve it in
    # exported evidence instead of alphabetically reordering JSON object keys.
    app.json.sort_keys = False
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Set SECRET_KEY to a random secret of at least 32 characters.")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("Set DATABASE_URL to the private MariaDB connection URL.")
    if app.config.get("MENU_IMPORT_API_KEY") and len(app.config["MENU_IMPORT_API_KEY"]) < 32:
        raise RuntimeError("MENU_IMPORT_API_KEY must contain at least 32 characters or be unset.")
    db.init_app(app)
    init_client(app)
    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    limiter = Limiter(get_remote_address, app=app, default_limits=["180 per minute"])
    app.extensions["makanwhere_limiter"] = limiter

    @app.before_request
    def protect_api():
        g.user = None
        if not request.path.startswith("/api/"):
            return
        # The single integration endpoint authenticates a server-held bearer
        # key. All browser/admin mutations still require session + CSRF.
        if request.endpoint in {"integration_menu_import", "integration_menu_targets"}:
            from .menu_imports import require_import_key
            require_import_key()
            return
        g.user = db.session.get(User, session["user_id"]) if session.get("user_id") else None
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected, supplied = session.get("csrf", ""), request.headers.get("X-CSRF-Token", "")
            if not expected or not hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
                abort(403, "Session expired. Refresh the page and try again.")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' https://images.unsplash.com https://upload.wikimedia.org data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error="That record already exists or references unavailable data."), 409

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error("Database operation failed: %s", type(error).__name__)
        return jsonify(error="The database is temporarily unavailable. Please try again."), 503

    @app.errorhandler(DuplicateKeyError)
    def mongo_conflict(error):
        return jsonify(error="That community record already exists. Refresh and try again."), 409

    @app.errorhandler(PyMongoError)
    def mongo_error(error):
        app.logger.error("Community database operation failed: %s", type(error).__name__)
        return jsonify(error="The community database is temporarily unavailable. Please try again."), 503

    @app.get("/api/health")
    @limiter.exempt
    def health():
        db.session.execute(text("SELECT 1"))
        db.session.execute(select(FoodPlace.place_id).limit(1))
        community_db().command("ping")
        return jsonify(status="ok", service="Makan Where", database="connected", mongoDB="connected")

    @app.get("/")
    @app.get("/<path:path>")
    @limiter.exempt
    def frontend(path="index.html"):
        pages = {"index.html", "browse.html", "restaurant.html", "favourites.html", "auth.html", "settings.html", "admin.html", "analytics.html"}
        pages.add("database-lab.html")
        if path not in pages and not (path.startswith(("js/", "css/", "assets/")) and ".." not in path.split("/")):
            abort(404)
        return send_from_directory(BASE_DIR, path)

    from .routes import register_routes
    from .commands import register_commands
    register_routes(app, limiter)
    from .community import register_community
    register_community(app, limiter)
    from .database_lab import register_lab
    register_lab(app, limiter)
    from .menu_imports import register_menu_imports
    register_menu_imports(app, limiter)
    register_commands(app)
    return app
