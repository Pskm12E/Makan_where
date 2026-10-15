"""Capture real SQL and plans for the same fixed SELECTs used by the app."""
from datetime import datetime, timezone
from importlib.metadata import version
from sqlalchemy import func, select
from .analytics import insight_queries, json_value
from .models import db


def collect_query_evidence():
    with db.engine.connect() as connection:
        dialect = connection.dialect
        if dialect.name not in {"mysql", "mariadb", "sqlite"}:
            raise ValueError("Query evidence supports MariaDB/MySQL and SQLite only.")
        sqlite = dialect.name == "sqlite"
        database_version = connection.exec_driver_sql(
            "SELECT sqlite_version()" if sqlite else "SELECT VERSION()"
        ).scalar_one()
        evidence = {
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "engine": "MariaDB" if getattr(dialect, "is_mariadb", False) else dialect.name,
            "databaseVersion": database_version,
            "sqlalchemyVersion": version("SQLAlchemy"),
            "scope": "Read-only SQL plans and results; not a performance benchmark. Live review ratings are aggregated in MongoDB; see Database evidence for the pipeline.",
            "rowCounts": {name: connection.execute(select(func.count()).select_from(table)).scalar_one()
                          for name, table in sorted(db.metadata.tables.items())},
            "queries": [],
        }
        for name, query in insight_queries().items():
            # All literals come from our fixed query definitions, never user input.
            sql = str(query.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
            prefix = "EXPLAIN QUERY PLAN " if sqlite else "EXPLAIN "
            plan = [dict(row) for row in connection.exec_driver_sql(prefix + sql).mappings()]
            result = [{key: json_value(value) for key, value in row.items()}
                      for row in connection.execute(query).mappings()]
            evidence["queries"].append({"name": name, "sql": sql, "plan": plan, "result": result})
        return evidence
