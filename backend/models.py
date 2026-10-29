"""14 live SQL tables plus 7 retained legacy community migration tables.
Derived prices and ratings are queried, never stored. Live community is MongoDB.
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import select, case, func
import sqlite3

db = SQLAlchemy(metadata=MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}))


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, _):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


class Area(db.Model):
    __tablename__ = "area"
    area_id = db.Column(db.Integer, primary_key=True)
    area_name = db.Column(db.String(100), nullable=False, unique=True)


class Category(db.Model):
    __tablename__ = "category"
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False, unique=True)


class Cuisine(db.Model):
    __tablename__ = "cuisine"
    cuisine_id = db.Column(db.Integer, primary_key=True)
    cuisine_name = db.Column(db.String(100), nullable=False, unique=True)


class PlaceCuisine(db.Model):
    __tablename__ = "place_cuisine"
    place_id = db.Column(db.Integer, db.ForeignKey("food_place.place_id"), primary_key=True)
    cuisine_id = db.Column(db.Integer, db.ForeignKey("cuisine.cuisine_id"), primary_key=True)


class FoodPlace(db.Model):
    __tablename__ = "food_place"
    place_id = db.Column(db.Integer, primary_key=True)
    area_id = db.Column(db.Integer, db.ForeignKey("area.area_id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.category_id"), nullable=False)
    place_name = db.Column(db.String(150), nullable=False, index=True)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Numeric(9, 6))
    longitude = db.Column(db.Numeric(9, 6))
    google_place_id = db.Column(db.String(255), unique=True)
    description = db.Column(db.Text, nullable=False, default="")
    image_url = db.Column(db.String(1000), nullable=False, default="")
    enrichment = db.Column(db.JSON, nullable=True)
    hygiene_grade = db.Column(db.String(1))
    legacy_tags = db.Column('tags', db.JSON, nullable=False, default=list)
    archived_at = db.Column(db.DateTime)
    source_name = db.Column(db.String(40))
    source_id = db.Column(db.String(80))
    source_url = db.Column(db.String(500))
    source_fetched_at = db.Column(db.DateTime)
    opening_hours = db.Column(db.String(1000))
    is_sample = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    __table_args__ = (
        db.UniqueConstraint("source_name", "source_id", name="uq_food_place_source"),
        db.CheckConstraint('latitude IS NULL OR latitude BETWEEN -90 AND 90', name='ck_place_latitude'),
        db.CheckConstraint('longitude IS NULL OR longitude BETWEEN -180 AND 180', name='ck_place_longitude'),
        db.CheckConstraint("hygiene_grade IS NULL OR hygiene_grade IN ('A','B','C','D')", name='ck_place_hygiene'),
    )
    area = db.relationship(Area)
    category = db.relationship(Category)
    cuisines = db.relationship(Cuisine, secondary="place_cuisine", lazy="selectin")
    dishes = db.relationship("Dish", lazy="selectin")
    tag_records = db.relationship('Tag', secondary='place_tag', lazy='selectin', order_by='Tag.tag_name')

    @property
    def tags(self):
        return [tag.tag_name for tag in self.tag_records] or self.legacy_tags or []

    @tags.setter
    def tags(self, names):
        if not isinstance(names, list) or any(not isinstance(n, str) or not n.strip() or len(n.strip()) > 80 for n in names):
            raise ValueError('Tags must be a list of nonempty names up to 80 characters.')
        records = []
        with db.session.no_autoflush:
            for name in sorted(set(n.strip() for n in names)):
                tag = next((t for t in db.session.new if isinstance(t, Tag) and t.tag_name == name), None)
                tag = tag or db.session.scalar(select(Tag).where(Tag.tag_name == name))
                if tag is None:
                    tag = Tag(tag_name=name)
                    db.session.add(tag)
                records.append(tag)
        self.tag_records = records
        self.legacy_tags = []


class Tag(db.Model):
    tag_id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(80), nullable=False, unique=True)


class PlaceTag(db.Model):
    place_id = db.Column(db.Integer, db.ForeignKey('food_place.place_id'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.tag_id'), primary_key=True)


class MenuPublication(db.Model):
    publication_id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(80), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    observed_at = db.Column(db.DateTime, nullable=False)
    payload_sha256 = db.Column(db.String(64), nullable=False, unique=True)
    is_reference = db.Column(db.Boolean, nullable=False)


class MenuEntry(db.Model):
    publication_id = db.Column(db.Integer, db.ForeignKey('menu_publication.publication_id'), primary_key=True)
    source_item_id = db.Column(db.String(100), primary_key=True)
    item_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    # A published item can be reviewable even when its source omits a price.
    reference_price = db.Column(db.Numeric(10, 2), nullable=True)
    dietary_label = db.Column(db.String(80), nullable=False, default='')
    publication = db.relationship(MenuPublication, lazy='joined')
    __table_args__ = (db.CheckConstraint('reference_price >= 0', name='ck_entry_price'),)


def menu_value(name, entry_name):
    """Effective attribute: shared source fact plus optional outlet override."""
    def get(self):
        if self.menu_entry is None:
            return getattr(self, 'legacy_' + name)
        override = getattr(self, name + '_override')
        return override if override is not None else getattr(self.menu_entry, entry_name)

    def set_value(self, value):
        if self.menu_entry is None:
            setattr(self, 'legacy_' + name, value)
        else:
            setattr(self, name + '_override', value if value != getattr(self.menu_entry, entry_name) else None)

    def expression(cls):
        shared = select(getattr(MenuEntry, entry_name)).where(
            MenuEntry.publication_id == cls.publication_id,
            MenuEntry.source_item_id == cls.source_item_id).correlate(cls).scalar_subquery()
        return case((cls.publication_id.is_not(None), func.coalesce(getattr(cls, name + '_override'), shared)),
                    else_=getattr(cls, 'legacy_' + name)).label(name)
    return hybrid_property(get, set_value, expr=expression)


def publication_value(name, publication_name):
    def get(self):
        if name == 'source_observed_at' and self.menu_edited_at:
            return None
        return getattr(self.menu_entry.publication, publication_name) if self.menu_entry else getattr(self, 'legacy_' + name)

    def set_value(self, value):
        setattr(self, 'legacy_' + name, value)
        if self.menu_entry and name == 'source_observed_at':
            self.menu_edited_at = now()

    def expression(cls):
        shared = select(getattr(MenuPublication, publication_name)).where(
            MenuPublication.publication_id == cls.publication_id).correlate(cls).scalar_subquery()
        clauses = [(cls.publication_id.is_not(None), shared)]
        if name == 'source_observed_at':
            clauses.insert(0, (cls.menu_edited_at.is_not(None), None))
        return case(*clauses, else_=getattr(cls, 'legacy_' + name)).label(name)
    return hybrid_property(get, set_value, expr=expression)


class Dish(db.Model):
    __tablename__ = "dish"
    dish_id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(db.Integer, db.ForeignKey("food_place.place_id"), nullable=False, index=True)
    legacy_dish_name = db.Column('dish_name', db.String(150), nullable=False, default='')
    legacy_description = db.Column('description', db.Text, nullable=False, default="")
    legacy_price = db.Column('price', db.Numeric(10, 2), nullable=False, default=0)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    legacy_dietary_label = db.Column('dietary_label', db.String(80), nullable=False, default="")
    legacy_source_name = db.Column('source_name', db.String(80))
    source_item_id = db.Column(db.String(100))
    legacy_source_url = db.Column('source_url', db.String(500))
    legacy_source_observed_at = db.Column('source_observed_at', db.DateTime)
    legacy_is_reference = db.Column('is_reference', db.Boolean, nullable=False, default=False, server_default="0")
    publication_id = db.Column(db.Integer)
    dish_name_override = db.Column(db.String(150))
    description_override = db.Column(db.Text)
    price_override = db.Column(db.Numeric(10, 2))
    dietary_label_override = db.Column(db.String(80))
    menu_edited_at = db.Column(db.DateTime)
    menu_entry = db.relationship(MenuEntry, lazy='joined')
    dish_name = menu_value('dish_name', 'item_name')
    description = menu_value('description', 'description')
    price = menu_value('price', 'reference_price')
    dietary_label = menu_value('dietary_label', 'dietary_label')
    source_name = publication_value('source_name', 'source_name')
    source_url = publication_value('source_url', 'source_url')
    source_observed_at = publication_value('source_observed_at', 'observed_at')
    is_reference = publication_value('is_reference', 'is_reference')
    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_dish_price"),
        db.UniqueConstraint("place_id", "source_name", "source_item_id", name="uq_dish_source"),
        db.ForeignKeyConstraint(['publication_id', 'source_item_id'], ['menu_entry.publication_id', 'menu_entry.source_item_id'], name='fk_dish_menu_entry'),
        db.UniqueConstraint('place_id', 'publication_id', 'source_item_id', name='uq_dish_offering'),
        db.CheckConstraint('price_override IS NULL OR price_override >= 0', name='ck_dish_override_price'),
        db.CheckConstraint('publication_id IS NULL OR source_item_id IS NOT NULL', name='ck_dish_entry_identity'),
        db.CheckConstraint("publication_id IS NULL OR (dish_name = '' AND price = 0 AND description = '' AND dietary_label = '' AND source_name IS NULL AND source_url IS NULL AND source_observed_at IS NULL)", name='ck_dish_shared_payload'),
    )


class User(db.Model):
    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    username = db.Column(db.String(50), nullable=False, unique=True)
    phone = db.Column(db.String(25), nullable=False, default="")
    __table_args__ = (db.CheckConstraint("role IN ('user', 'admin')", name="ck_user_role"),)


class Favourite(db.Model):
    __tablename__ = "favourite"
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), primary_key=True)
    place_id = db.Column(db.Integer, db.ForeignKey("food_place.place_id"), primary_key=True)
    saved_at = db.Column(db.DateTime, nullable=False, default=now)


class Content(db.Model):
    __tablename__ = "content"
    content_id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False, index=True)
    place_id = db.Column(db.Integer, db.ForeignKey("food_place.place_id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)
    removed_by_id = db.Column(db.Integer, db.ForeignKey("user.user_id"))
    removed_at = db.Column(db.DateTime)
    kind = db.Column(db.String(10), nullable=False)
    author = db.relationship(User, foreign_keys=[author_id])
    __table_args__ = (
        db.CheckConstraint("kind IN ('review','thread','comment')", name="ck_content_kind"),
        db.CheckConstraint("(removed_at IS NULL AND removed_by_id IS NULL) OR (removed_at IS NOT NULL AND removed_by_id IS NOT NULL)", name="ck_content_removal"),
        db.UniqueConstraint("content_id", "kind"),
    )


# Retained legacy SQL subtype model, used only for migration of existing data.
# Live subtype validation and bounded dish feedback are in mongo.py/community.py.
class Review(db.Model):
    __tablename__ = "review"
    content_id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False, default="review")
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(150), nullable=False, default="")
    __table_args__ = (
        db.ForeignKeyConstraint(["content_id", "kind"], ["content.content_id", "content.kind"]),
        db.CheckConstraint("kind = 'review'", name="ck_review_kind"),
        db.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
    )


class Thread(db.Model):
    __tablename__ = "thread"
    content_id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False, default="thread")
    title = db.Column(db.String(150), nullable=False)
    __table_args__ = (
        db.ForeignKeyConstraint(["content_id", "kind"], ["content.content_id", "content.kind"]),
        db.CheckConstraint("kind = 'thread'", name="ck_thread_kind"),
    )


class Comment(db.Model):
    __tablename__ = "comment"
    content_id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False, default="comment")
    thread_id = db.Column(db.Integer, db.ForeignKey("thread.content_id"), nullable=False, index=True)
    __table_args__ = (
        db.ForeignKeyConstraint(["content_id", "kind"], ["content.content_id", "content.kind"]),
        db.CheckConstraint("kind = 'comment'", name="ck_comment_kind"),
    )


class ContentDish(db.Model):
    __tablename__ = "content_dish"
    content_id = db.Column(db.Integer, db.ForeignKey("content.content_id"), primary_key=True)
    dish_id = db.Column(db.Integer, db.ForeignKey("dish.dish_id"), primary_key=True)
    dish_feedback = db.Column(db.Text)


class Upvote(db.Model):
    __tablename__ = "upvote"
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey("content.content_id"), primary_key=True)
    voted_at = db.Column(db.DateTime, nullable=False, default=now)


class Report(db.Model):
    __tablename__ = "report"
    report_id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey("content.content_id"), nullable=False, index=True)
    reason = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    status = db.Column(db.String(20), nullable=False, default="open")
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("user.user_id"))
    resolved_at = db.Column(db.DateTime)
    resolution_note = db.Column(db.String(1000))
    __table_args__ = (db.CheckConstraint("status IN ('open','resolved','dismissed')", name="ck_report_status"),)


class DiscoveryEvent(db.Model):
    __tablename__ = "discovery_event"
    event_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"))
    place_id = db.Column(db.Integer, db.ForeignKey("food_place.place_id"))
    event_type = db.Column(db.String(20), nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=False, default=now, index=True)
    __table_args__ = (
        db.CheckConstraint("event_type IN ('search','place_view')", name="ck_discovery_type"),
        db.CheckConstraint("event_type != 'place_view' OR place_id IS NOT NULL", name="ck_discovery_place"),
    )


class PopulationRun(db.Model):
    """Receipts and restart markers; no passwords or database URLs."""
    __tablename__ = "population_run"
    run_key = db.Column(db.String(100), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    details = db.Column(db.JSON, nullable=False)
