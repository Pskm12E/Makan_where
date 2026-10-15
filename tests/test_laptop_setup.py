"""Verify portable setup protects credentials and existing application accounts."""
import pytest
from sqlalchemy import func, select
from test_api import app
from backend.models import db, User
from scripts.configure_laptop import configure
from scripts.laptop_setup import ensure_accounts


def test_laptop_credentials_are_private_unique_and_never_replaced(tmp_path):
    first, second = tmp_path/'first.env', tmp_path/'second.env'
    configure(first); configure(second)
    original = first.read_bytes()
    with pytest.raises(FileExistsError): configure(first)
    assert first.read_bytes() == original
    values = dict(line.split('=', 1) for line in first.read_text().splitlines() if line and not line.startswith('#'))
    other = dict(line.split('=', 1) for line in second.read_text().splitlines() if line and not line.startswith('#'))
    keys = [key for key in values if 'PASSWORD' in key or key == 'SECRET_KEY']
    assert len({values[key] for key in keys}) == len(keys)
    assert all(values[key] != other[key] for key in keys)
    assert all(len(values[key]) >= 24 for key in keys)


def test_laptop_accounts_rerun_retains_hashes_and_rejects_conflicts(app, monkeypatch):
    for role in ['ADMIN', 'USER']:
        monkeypatch.setenv(f'LECTURER_{role}_USERNAME', f'lecturer_{role.lower()}')
        monkeypatch.setenv(f'LECTURER_{role}_PASSWORD', f'Test-only-{role}-password-2026')
    with app.app_context():
        ensure_accounts()
        rows = list(db.session.scalars(select(User).order_by(User.user_id)))
        old = [(u.user_id, u.role, u.password_hash) for u in rows]
        ensure_accounts()
        assert [(u.user_id, u.role, u.password_hash) for u in db.session.scalars(select(User).order_by(User.user_id))] == old
        assert {u.role for u in rows} == {'admin', 'user'}
        monkeypatch.setenv('LECTURER_ADMIN_PASSWORD', 'changed-password-must-not-reset-account')
        with pytest.raises(RuntimeError, match='Retained account'): ensure_accounts()
        assert db.session.scalar(select(func.count()).select_from(User)) == 2
        assert rows[0].password_hash == old[0][2]
