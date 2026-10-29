"""Read recorded experiments; never run load/failure tests against live data."""
import hashlib
import json
from pathlib import Path
from flask import current_app
from .config import BASE_DIR


def source_fingerprint():
    digest = hashlib.sha256()
    paths = [*BASE_DIR.joinpath('backend').glob('*.py'), *BASE_DIR.joinpath('tests').glob('*.py'),
             *BASE_DIR.joinpath('scripts').glob('*.py'), *BASE_DIR.joinpath('js').glob('*.js'),
             BASE_DIR / 'Dockerfile', BASE_DIR / 'compose.laptop.yaml', BASE_DIR / '.dockerignore',
             BASE_DIR / 'backend/requirements.txt']
    for path in sorted(paths, key=lambda p: p.relative_to(BASE_DIR).as_posix()):
        digest.update(path.relative_to(BASE_DIR).as_posix().encode() + b'\0')
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def recorded_evaluation():
    path = Path(current_app.config.get('DATABASE_EVALUATION_FILE') or
                BASE_DIR / 'docs/evidence/database-evaluation.json')
    if not path.is_file():
        return {'status': 'not_run', 'message': 'No recorded evaluation for this installation. Run the isolated evaluation command first.'}
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        if result.get('formatVersion') != 1 or not isinstance(result.get('experiments'), list):
            raise ValueError('Unsupported evaluation format')
    except (ValueError, OSError):
        return {'status': 'unavailable', 'message': 'The recorded evaluation could not be read.'}
    result['currentSource'] = result.get('sourceSha256') == source_fingerprint()
    result['status'] = 'recorded' if result['currentSource'] else 'stale'
    return result
