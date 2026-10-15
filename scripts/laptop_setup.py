"""Populate a fresh laptop installation through the application's Python code.

Reruns preserve accounts, manual edits, stable source identities and seed keys.
No production server, SQL GUI, external API or credentials file is needed.
"""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ensure_accounts():
    from sqlalchemy import select
    from backend.models import db, User
    from backend.passwords import hash_password, verify_password
    for role, prefix, display in [('admin', 'LECTURER_ADMIN', 'Lecturer Administrator'),
                                  ('user', 'LECTURER_USER', 'Lecturer Reviewer')]:
        username = os.environ.get(prefix + '_USERNAME', '')
        password = os.environ.get(prefix + '_PASSWORD', '')
        if not username or len(password) < 12:
            raise RuntimeError(f'Configure {prefix}_USERNAME and a password of at least 12 characters.')
        email = username + '@laptop.invalid'
        user = db.session.scalar(select(User).where(User.username == username))
        if user:
            if user.email != email or user.role != role:
                raise RuntimeError('Laptop account conflicts with an existing account; no account was replaced.')
            if not verify_password(user.password_hash, password):
                raise RuntimeError('Retained account password does not match configuration; restore the original .env.laptop.')
        else:
            db.session.add(User(username=username, email=email, display_name=display,
                role=role, password_hash=hash_password(password)))
    db.session.commit()


def import_reference_menus(app):
    from sqlalchemy import select
    from backend.models import db, FoodPlace
    from backend.menu_imports import import_request
    for filename in ('kfc_sg_reference_20261004.json', 'sukiya_sg_reference_20261004.json'):
        menu = json.loads((ROOT / 'data/menus' / filename).read_text(encoding='utf-8'))
        names = menu.pop('matchNames')
        places = db.session.scalars(select(FoodPlace).where(FoodPlace.archived_at.is_(None),
            FoodPlace.is_sample.is_(False), FoodPlace.place_name.in_(names)).order_by(FoodPlace.place_id)).all()
        menu['places'] = [{'id': p.place_id, 'name': p.place_name, 'sourceId': p.source_id or ''} for p in places]
        if not menu['places']:
            raise RuntimeError(f'No imported venue matches the retained menu: {filename}')
        # Use the same validation, preview token and atomic write path as admin imports.
        with app.test_request_context(json={'menu': menu}):
            preview = import_request('laptop-setup').get_json()
        with app.test_request_context(json={'menu': preview['menu'], 'apply': True, 'previewToken': preview['previewToken']}):
            result = import_request('laptop-setup').get_json()
        print(f"{filename}: {result['added']} added, {result['skipped']} retained", flush=True)


def main():
    from backend.app import create_app
    app = create_app()
    runner = app.test_cli_runner()
    for command in ('migrate-menus', 'migrate-details', 'init-db', 'init-mongo',
                    'migrate-community', 'seed-coursework', 'enrich-listings --apply'):
        result = runner.invoke(args=command.split())
        if result.exit_code:
            raise RuntimeError(f'{command} failed; existing data retained. {result.output}') from result.exception
        print(f'{command}: complete', flush=True)
    with app.app_context():
        ensure_accounts()
        import_reference_menus(app)
    print('Laptop setup complete. Read the LECTURER_* entries in .env.laptop to sign in.', flush=True)


if __name__ == '__main__':
    main()
