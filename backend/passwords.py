"""Versioned salted scrypt plus a secret kept outside the database.

Work factor: OWASP Password Storage Cheat Sheet (N=2^15,r=8,p=3).
"""
import hashlib
import hmac
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash

PREFIX = "pepper-v1$"
METHOD = "scrypt:32768:8:3"


def peppered(password):
    pepper = current_app.config.get("PASSWORD_PEPPER", "")
    if len(pepper) < 32:
        raise RuntimeError("PASSWORD_PEPPER needs at least 32 random characters, stored outside the database.")
    return hmac.new(pepper.encode(), password.encode(), hashlib.sha256).hexdigest()


def hash_password(password):
    return PREFIX + generate_password_hash(peppered(password), method=METHOD, salt_length=16)


def verify_password(encoded, password):
    try:
        if encoded.startswith(PREFIX):
            return check_password_hash(encoded[len(PREFIX):], peppered(password))
        return check_password_hash(encoded, password)
    except (ValueError, TypeError):
        return False


def needs_upgrade(encoded):
    return not encoded.startswith(PREFIX + METHOD + "$")
