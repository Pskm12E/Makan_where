import json
import click
from pathlib import Path
from sqlalchemy import func, inspect, select
from .config import BASE_DIR
from .models import db, FoodPlace, Dish, User
from .routes import save_place


def register_commands(app):
    @app.cli.command('seed-listing-examples')
    @click.option('--apply', is_flag=True, help='Insert labelled examples; default is preview only.')
    def seed_listing_examples_command(apply):
        from .example_community import seed_listing_examples
        try:
            click.echo(json.dumps(seed_listing_examples(apply=apply)))
        except ValueError as error:
            raise click.ClickException(str(error)) from error

    @app.cli.command('migrate-details')
    def migrate_details():
        from .migrations import add_listing_details
        click.echo(json.dumps(add_listing_details()))

    @app.cli.command('enrich-listings')
    @click.option('--apply', is_flag=True, help='Fill only missing sourced fields; default is preview.')
    def enrich_listings_command(apply):
        from .listing_details import enrich_listings
        click.echo(json.dumps(enrich_listings(apply=apply)))

    @app.cli.command("migrate-menus")
    def migrate_menus():
        """Add menu source identity and provenance; preserves every existing dish."""
        from .migrations import add_menu_provenance
        click.echo(json.dumps(add_menu_provenance()))

    @app.cli.command("init-mongo")
    def init_mongo():
        from .mongo import init_collections
        init_collections()
        click.echo("MongoDB validators and indexes are ready.")

    @app.cli.command("migrate-community")
    def migrate_community_command():
        from .community_migration import migrate_community
        try:
            click.echo(json.dumps(migrate_community()))
        except ValueError as error:
            raise click.ClickException(str(error)) from error

    @app.cli.command("seed-coursework")
    def seed_coursework_command():
        from .population import seed_coursework
        try:
            click.echo(json.dumps(seed_coursework(), default=str))
        except ValueError as error:
            raise click.ClickException(str(error)) from error

    @app.cli.command("lab-evidence")
    @click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
    def lab_evidence(output):
        from .database_lab import lab_snapshot, constraint_probes, security_evidence
        with output.open("x", encoding="utf-8") as stream:
            json.dump({"snapshot": lab_snapshot(), "probes": constraint_probes(), "security": security_evidence()}, stream, indent=2, default=str)
        click.echo("Evidence saved; no private credentials or real password hashes included.")

    @app.cli.command("query-evidence")
    @click.option("--output", type=click.Path(dir_okay=False, path_type=Path),
                  help="Write JSON to a new file; refuses to overwrite existing evidence.")
    def query_evidence(output):
        """Print actual insight SELECTs, EXPLAIN plans, results and row counts."""
        from .query_evidence import collect_query_evidence
        try:
            evidence = json.dumps(collect_query_evidence(), ensure_ascii=False, indent=2, default=str)
            if output:
                with output.open("x", encoding="utf-8") as stream:
                    stream.write(evidence + "\n")
                click.echo(f"Read-only query evidence written to {output}")
            else:
                click.echo(evidence)
        except (OSError, ValueError) as error:
            raise click.ClickException(str(error)) from error

    @app.cli.command("migrate-catalogue")
    def migrate_catalogue():
        """Add provenance columns and mark exact original sample records."""
        from .migrations import add_catalogue_provenance
        click.echo(json.dumps(add_catalogue_provenance()))

    @app.cli.command("init-db")
    def init_db():
        """Add missing ER tables; refuse incompatible existing tables."""
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        for table in db.metadata.sorted_tables:
            if table.name in existing:
                actual = {c["name"] for c in inspector.get_columns(table.name)}
                if not set(table.columns.keys()).issubset(actual):
                    raise click.ClickException(f"Existing table {table.name} needs a reviewed migration; no changes made.")
        db.create_all()
        from .database_lab import install_views
        install_views()
        click.echo("17 SQL tables and the catalogue view are ready, including 7 retained legacy community tables. Existing data was preserved.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Insert the original six sample venues only into an empty catalogue."""
        if db.session.scalar(select(func.count()).select_from(FoodPlace)):
            raise click.ClickException("Catalogue is not empty; seed skipped to preserve existing data.")
        records = json.loads((BASE_DIR / "database" / "demo_places.json").read_text(encoding="utf-8"))
        for record in records:
            place = FoodPlace(description=record["description"], image_url=record["image"], tags=record["tags"], is_sample=True)
            with db.session.no_autoflush:
                save_place(place, {**record, 'photoKind': 'illustrative', 'photoCredit': 'Unsplash', 'photoSourceUrl': 'https://unsplash.com/license'})
            db.session.add(place)
            db.session.flush()
            for dish in record["menu"]:
                db.session.add(Dish(place_id=place.place_id, dish_name=dish["name"], price=dish["price"],
                                    dietary_label=dish["dietary"], is_available=dish["availability"]))
        db.session.commit()
        click.echo("Seeded six sample venues and 18 dishes; no fake users or reviews.")

    @app.cli.command("set-admin")
    @click.argument("email")
    def set_admin(email):
        """Promote an explicitly chosen existing account."""
        user = db.session.scalar(select(User).where(User.email == email.lower()))
        if not user:
            raise click.ClickException("Register this account first.")
        user.role = "admin"
        db.session.commit()
        click.echo("Administrator role assigned.")

    @app.cli.command("import-places")
    @click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--apply", is_flag=True, help="Commit the validated import; otherwise only preview.")
    def import_places(csv_path, apply):
        """Import the saved attributed CSV; skip existing source identities."""
        from .imports import import_csv
        try:
            result = import_csv(csv_path, apply=apply)
        except ValueError as error:
            db.session.rollback()
            raise click.ClickException(str(error)) from error
        click.echo(json.dumps(result, ensure_ascii=False))
