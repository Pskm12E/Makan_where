"""Offline update for the existing private app VM; preserves accounts and data.

Community migration is insert-only. Both engines use local Unix sockets,
retaining the web service's network sandbox. Run through install_host.py.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

SCHEMA = 'ws_93ec3577bd28665adb32bdf1'
DOMAIN = 'makanwhere.4bytedigi.com'
ROOT_URL = f'mysql+pymysql://root@localhost/{SCHEMA}?unix_socket=/run/mysqld/mysqld.sock&charset=utf8mb4'
ROOT = Path('/srv/makanwhere')
CONFIG = Path('/etc/makanwhere/app.env')
BASE_TABLES = ['area','category','cuisine','food_place','place_cuisine','dish','user','favourite','content','review','thread','comment','content_dish','upvote','report','discovery_event','population_run']
SERVICE = Path('/etc/systemd/system/makanwhere.service')
SITE = Path('/etc/nginx/sites-available/makanwhere')
LINK = Path('/etc/nginx/sites-enabled/makanwhere')


def run(args, **kw):
    return subprocess.run(args, check=True, **kw)


def sql(query):
    return run(['mariadb','-N','-B'], input=query, text=True, capture_output=True).stdout


def unpack(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source) as archive:
        for item in archive.getmembers():
            path = destination / item.name
            if not item.isfile() or not path.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError('Unexpected release archive entry')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as target, archive.extractfile(item) as stream:
                shutil.copyfileobj(stream, target)
            path.chmod(0o644)


def read_environment(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        tokens = shlex.split(value, comments=False)
        if len(tokens) != 1:
            raise RuntimeError('Review environment file formatting before deployment.')
        values[key] = tokens[0]
    return values


def write_environment(values):
    temporary = CONFIG.with_suffix('.env.new')
    with temporary.open('w') as stream:
        for key, value in values.items():
            if '\n' in value or '\r' in value:
                raise RuntimeError('Multiline environment values are not supported.')
            stream.write(f'{key}=' + json.dumps(value) + '\n')
    temporary.chmod(0o600)
    temporary.replace(CONFIG)


def set_current(release):
    current = ROOT / 'current'
    if current.exists() and not current.is_symlink():
        raise RuntimeError('Current release is not a managed symlink.')
    temporary = ROOT / 'current.next'
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(current)


def healthy():
    for _ in range(30):
        response = subprocess.run(['curl','--fail','--silent','--max-time','5','--unix-socket',
            '/run/makanwhere/web.sock',f'http://{DOMAIN}/api/health'], capture_output=True)
        if response.returncode == 0:
            data = json.loads(response.stdout)
            if data.get('database') == 'connected' and data.get('mongoDB') == 'connected':
                return
        time.sleep(1)
    raise RuntimeError('Both databases did not become healthy under the application service permissions.')


UNIT = '''# Managed by Makan Where
[Unit]
Description=Makan Where food discovery
After=mariadb.service makanwhere-mongo.service
Requires=mariadb.service makanwhere-mongo.service

[Service]
User=makanwhere
Group=www-data
WorkingDirectory=/srv/makanwhere/current
EnvironmentFile=/etc/makanwhere/app.env
Environment=PYTHONPATH=/srv/makanwhere/current/vendor
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -m gunicorn --workers 1 --threads 4 --bind unix:/run/makanwhere/web.sock --umask 007 --access-logfile - --error-logfile - backend.app:create_app()
RuntimeDirectory=makanwhere
RuntimeDirectoryMode=0750
UMask=0007
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
PrivateNetwork=yes
RestrictAddressFamilies=AF_UNIX
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
LockPersonality=yes
ReadWritePaths=/run/makanwhere
MemoryMax=512M
TasksMax=128
CPUQuota=100%

[Install]
WantedBy=multi-user.target
'''


def nginx_config():
    return f'''# Managed by Makan Where
server {{
    listen 172.30.12.2:3080;
    server_name {DOMAIN};
    server_tokens off;
    client_max_body_size 64k;
    set_real_ip_from 172.30.12.1;
    real_ip_header CF-Connecting-IP;
    location / {{
        proxy_pass http://unix:/run/makanwhere/web.sock:;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
    }}
}}
'''


def main():
    os.umask(0o077)
    if os.geteuid() != 0 or sys.version_info[:2] != (3,12):
        raise RuntimeError('Requires root and the reviewed Python 3.12 VM.')
    staging = Path(sys.argv[1]).resolve()
    if sql(f"SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='{SCHEMA}'").strip() != SCHEMA:
        raise RuntimeError('Expected project schema is absent. No replacement database was created.')
    current = ROOT / 'current'
    if not current.is_symlink() or not CONFIG.exists() or not SERVICE.exists():
        raise RuntimeError('Expected existing deployment is absent; inspect server first.')
    previous = current.resolve()
    config = read_environment(CONFIG)
    if not config.get('SECRET_KEY') or not config.get('DATABASE_URL'):
        raise RuntimeError('Existing deployment configuration is incomplete.')
    for filename in ['release.tar.gz','wheels.tar.gz']:
        digest = hashlib.sha256((staging / filename).read_bytes()).hexdigest()
        if digest != (staging / (filename + '.sha256')).read_text().strip():
            raise RuntimeError(f'Checksum mismatch: {filename}')
    digest = hashlib.sha256((staging / 'release.tar.gz').read_bytes()).hexdigest()
    release = ROOT / 'releases' / digest[:16]
    if release.exists():
        raise RuntimeError('Release exists; inspect its previous deployment receipt before retrying.')
    from mongo_service import preflight, ensure, backup_data, PRIVATE
    preflight(staging)
    unpack(staging / 'release.tar.gz', release)
    for directory in [release] + [p for p in release.rglob('*') if p.is_dir()]:
        directory.chmod(0o755)
    wheels = staging / 'wheels'
    unpack(staging / 'wheels.tar.gz', wheels)
    vendor = release / 'vendor'
    pipwheel = next(wheels.glob('pip-*.whl'))
    run(['python3','-m','pip','install','--no-index','--no-compile','--root-user-action=ignore',
         '--find-links',str(wheels),'--target',str(vendor),'-r',str(release/'backend/requirements.txt'),'pytest'],
        env=dict(os.environ, PYTHONPATH=str(pipwheel), PIP_DISABLE_PIP_VERSION_CHECK='1'))
    for path in vendor.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    vendor.chmod(0o755)
    sys.path.insert(0, str(vendor))
    mongo_uri, mongo_root_uri = ensure(staging)
    if config.get('MONGODB_URI') and config['MONGODB_URI'] != mongo_uri:
        raise RuntimeError('Existing MongoDB connection differs; review before changing it.')
    if config.get('MONGODB_DATABASE', 'makanwhere') != 'makanwhere':
        raise RuntimeError('Existing MongoDB database differs; review before changing it.')
    config.setdefault('PASSWORD_PEPPER', secrets.token_urlsafe(48))
    config.update(MONGODB_URI=mongo_uri, MONGODB_DATABASE='makanwhere')
    env = dict(os.environ)
    env.update(config, PYTHONPATH=str(vendor), PYTHONDONTWRITEBYTECODE='1')
    admin_env = dict(env, DATABASE_URL=ROOT_URL)
    test_env = dict(admin_env, MONGODB_TEST_URI=mongo_root_uri,
        MARIADB_TEST_ADMIN_URL='mysql+pymysql://root@localhost/?unix_socket=/run/mysqld/mysqld.sock')
    evaluation_dir = release / 'docs/evidence'
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.chmod(0o755)
    evaluation_file = evaluation_dir / 'database-evaluation.json'
    run(['python3','scripts/run_database_evaluation.py','--full-suite',
         '--output',str(evaluation_file)], cwd=release, env=test_env)
    # This sanitized artifact contains synthetic observations, never DB URLs or
    # passwords. The isolated application user must be able to read it.
    evaluation_file.chmod(0o644)
    backup = Path('/var/backups/makanwhere') / time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    backup.mkdir(parents=True, mode=0o700)
    backup.parent.chmod(0o700)
    for path in [CONFIG, SERVICE, SITE, PRIVATE]:
        if path.exists():
            shutil.copy2(path, backup / path.name)
            (backup / path.name).chmod(0o600)
    (backup / 'release.json').write_text(json.dumps({'previous':str(previous),'new':str(release)}))
    run(['systemctl','stop','makanwhere'])
    try:
        with (backup / 'project.sql').open('wb') as target:
            run(['mariadb-dump','--single-transaction','--databases',SCHEMA], stdout=target)
        backup_data(backup / 'mongo-data')
        for command in ['migrate-catalogue','migrate-menus','migrate-details','init-db','init-mongo','migrate-community','seed-coursework','enrich-listings --apply']:
            result = subprocess.run(['python3','-m','flask','--app','backend.app',*command.split()], cwd=release,
                         env=admin_env, capture_output=True, text=True)
            (backup / (command + '.log')).write_text(result.stdout + result.stderr)
            result.check_returncode()
            print(command + ': completed', flush=True)
        for table in BASE_TABLES:
            sql(f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{SCHEMA}`.`{table}` TO 'makanwhere'@'localhost';")
        sql(f"GRANT SELECT ON `{SCHEMA}`.`catalogue_menu_summary` TO 'makanwhere'@'localhost';")
        write_environment(config)
        result = run(['python3',str(release / 'deploy/verify_release.py'),str(release)],
                     env=dict(os.environ, PYTHONPATH=str(vendor)), capture_output=True, text=True)
        evidence = json.loads(result.stdout)
        (backup / 'database-evidence.json').write_text(json.dumps(evidence, indent=2))
        set_current(release)
        SERVICE.write_text(UNIT)
        SITE.write_text(nginx_config())
        if not LINK.exists():
            LINK.symlink_to(SITE)
        SERVICE.chmod(0o644)
        SITE.chmod(0o644)
        run(['nginx','-t'])
        run(['systemctl','daemon-reload'])
        run(['systemctl','restart','makanwhere'])
        healthy()
        run(['systemctl','restart','makanwhere'])
        healthy()
        run(['systemctl','reload','nginx'])
    except BaseException:
        subprocess.run(['systemctl','stop','makanwhere'])
        set_current(previous)
        for path in [CONFIG, SERVICE, SITE]:
            if (backup / path.name).exists():
                shutil.copy2(backup / path.name, path)
                path.chmod(0o600 if path == CONFIG else 0o644)
        subprocess.run(['systemctl','daemon-reload'])
        subprocess.run(['systemctl','start','makanwhere'])
        print('Previous application/config restored. Additive data and backups retained at ' + str(backup), flush=True)
        raise
    print(json.dumps({'installed':True, 'release':str(release), 'backup':str(backup),
        'schema':SCHEMA, 'tables':len(BASE_TABLES), 'databases':['MariaDB','MongoDB']}))


if __name__ == '__main__':
    main()
