"""Read-only metadata for application tables in the connected SQL database."""
from sqlalchemy import inspect
from .models import db
from .mongo import community_db


def application_schema():
    with db.engine.connect() as connection:
        inspector = inspect(connection)
        expected = set(db.metadata.tables)
        present = expected.intersection(inspector.get_table_names())
        tables = []
        for name in sorted(present):
            primary = inspector.get_pk_constraint(name).get("constrained_columns", [])
            tables.append({
                "name": name,
                "columns": [{"name": c["name"], "type": str(c["type"]),
                             "nullable": bool(c["nullable"]), "primaryKey": c["name"] in primary,
                             "default": None if c.get("default") is None else str(c["default"])}
                            for c in inspector.get_columns(name)],
                "primaryKey": primary,
                "foreignKeys": [{"columns": fk["constrained_columns"],
                                 "table": fk["referred_table"], "targetColumns": fk["referred_columns"]}
                                for fk in inspector.get_foreign_keys(name)
                                if fk["referred_table"] in expected],
                "uniqueConstraints": [{"name": item.get("name"), "columns": item["column_names"]}
                                      for item in inspector.get_unique_constraints(name)],
                "indexes": [{"name": item["name"], "columns": item["column_names"],
                             "unique": bool(item["unique"])} for item in inspector.get_indexes(name)],
                "checks": [{"name": item.get("name"), "expression": item["sqltext"]}
                           for item in inspector.get_check_constraints(name)],
            })
        dialect = connection.dialect
        engine = "MariaDB" if getattr(dialect, "is_mariadb", False) else dialect.name
    return {"engine": engine, "source": "live database metadata", "readOnly": True,
            "tables": tables, "missingTables": sorted(expected - present),
            "mongoDB": {"status": "active; community documents, votes and moderation", "connected": bool(community_db().command('ping')['ok'])}}
