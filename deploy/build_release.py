"""Package only application sources and explicitly downloaded Linux wheels."""
from pathlib import Path
import hashlib
import tarfile
import re
import shutil

root = Path(__file__).resolve().parent.parent
out = root / "work"
out.mkdir(exist_ok=True)
# Content fingerprints prevent CDN/browser caches mixing old UI code with a
# new API/data release. Only known local JS/CSS references are rewritten.
for page in root.glob('*.html'):
    original = page.read_text(encoding='utf-8')
    def fingerprint(match):
        path = root / match.group(2)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        return f'{match.group(1)}="{match.group(2)}?v={digest}"'
    updated = re.sub(r'(src|href)="((?:js|css)/[\w.-]+\.(?:js|css))(?:\?v=[^"\s]+)?"', fingerprint, original)
    if updated != original: page.write_text(updated,encoding='utf-8')
files = list(root.glob("*.html")) + [root/'pytest.ini', root/'README.md', root/'.env.example', root/'compose.yaml',
    root/'Dockerfile', root/'compose.laptop.yaml', root/'.dockerignore']
for directory in ["backend", "js", "css", "assets", "database", "tests", "deploy", "scripts"]:
    files.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
# The real source path is used by population and studio evidence on the server.
# Package only the reviewed source/provenance, never local secrets/runtime DBs.
files.extend([root/'data/README.md', root/'data/scraped/singapore_food_places_20260922T094048Z.csv'])
files.extend((root/'data/menus').glob('*.json'))
files.extend((root/'data/enrichment').glob('*.json'))
files.extend(p for p in (root/'docs').rglob('*') if p.is_file() and p.suffix in {'.md', '.svg'})
for filename, members, relative in [
    ("release.tar.gz", files, root),
    ("wheels.tar.gz", sorted((out / "wheels").glob("*.whl")), out / "wheels"),
]:
    assert members, f"No files for {filename}"
    with tarfile.open(out / filename, "w:gz") as archive:
        for path in members:
            archive.add(path, arcname=path.relative_to(relative).as_posix(), recursive=False)
    digest = hashlib.sha256((out / filename).read_bytes()).hexdigest()
    (out / (filename + ".sha256")).write_text(digest + "\n")
    print(filename, digest)

# Host entrypoints accompany the archives. Copy only these named files over SSH.
for name in ['install_host.py', 'install_guest.py', 'mongo_service.py']:
    shutil.copy2(root / 'deploy' / name, out / name)
from mongo_service import ARCHIVE, SHA256
if not (out / ARCHIVE).exists() or hashlib.sha256((out / ARCHIVE).read_bytes()).hexdigest() != SHA256:
    raise SystemExit('Download the pinned official MongoDB artifact described in deploy/README.md before transfer.')
print('Server artifacts prepared in work/. No local secrets or database files included.')
