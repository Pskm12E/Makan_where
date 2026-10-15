"""Local Python launcher; .env.demo holds private, persistent demo credentials.

Usage: python scripts/run_demo.py --setup | --serve | --test
Start MongoDB (and MariaDB when configured) before running setup. Reads only
this project config, never modifies system services or existing deployment.
"""
import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_env(path=None):
    path = path or ROOT / '.env.demo'
    if not path.exists():
        raise SystemExit('Create .env.demo using .env.example and configure both database connections first.')
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--setup', action='store_true')
    group.add_argument('--serve', action='store_true')
    group.add_argument('--test', action='store_true')
    group.add_argument('--migrate-menus', action='store_true')
    group.add_argument('--enrich-listings', action='store_true')
    parser.add_argument('--apply', action='store_true', help='Apply the reviewed listing enrichment after preview.')
    parser.add_argument('--port', default=5055, type=int)
    parser.add_argument('--env', type=Path, default=ROOT / '.env.demo')
    args = parser.parse_args()
    os.chdir(ROOT)
    load_env(args.env)
    if args.test:
        import pytest
        raise SystemExit(pytest.main(['tests', '-q']))
    from backend.app import create_app
    from backend.models import db, User
    from backend.passwords import hash_password
    from sqlalchemy import select
    app = create_app()
    if args.enrich_listings:
        runner = app.test_cli_runner()
        migration = runner.invoke(args=['migrate-details'])
        if migration.exit_code:
            raise SystemExit(migration.output)
        result = runner.invoke(args=['enrich-listings'] + (['--apply'] if args.apply else []))
        print(result.output)
        if result.exit_code:
            raise SystemExit('Listing enrichment failed; inspect the source before retrying.')
        return
    if args.migrate_menus:
        result = app.test_cli_runner().invoke(args=['migrate-menus'])
        print(result.output)
        if result.exit_code:
            raise SystemExit('Menu migration failed. Existing dishes were not reset.')
        return
    if args.setup:
        runner = app.test_cli_runner()
        for command in ['migrate-menus', 'migrate-details', 'init-db', 'init-mongo', 'migrate-community', 'seed-coursework', 'enrich-listings --apply']:
            result = runner.invoke(args=command.split())
            if result.exit_code:
                print(result.output)
                raise SystemExit(f'{command} failed: {type(result.exception).__name__}. Existing data was not reset.')
            print(f'{command}: completed')
        with app.app_context():
            username = os.environ.get('DEMO_ADMIN_USERNAME', 'demo_lecturer')
            password = os.environ.get('DEMO_ADMIN_PASSWORD')
            if not password or len(password) < 12:
                raise SystemExit('Set DEMO_ADMIN_PASSWORD to at least 12 characters in .env.demo.')
            user = db.session.scalar(select(User).where(User.username == username))
            if user:
                if user.role != 'admin' or user.email != username + '@demo.invalid':
                    raise SystemExit('Demo admin name conflicts with an existing account; not changed.')
            else:
                db.session.add(User(username=username, email=username + '@demo.invalid', display_name='Demonstration Lecturer',
                    role='admin', password_hash=hash_password(password)))
                db.session.commit()
        print('Setup complete. Credentials stay in .env.demo; seed accounts are fictional.')
    else:
        from waitress import serve
        print(f'Local application: http://127.0.0.1:{args.port}/database-lab.html', flush=True)
        serve(app, host='127.0.0.1', port=args.port, threads=6)


if __name__ == '__main__':
    main()
