"""Private, authenticated MongoDB for the existing Ubuntu 24.04 app VM.

Called by install_guest with its vendored PyMongo. No network download, no
host port, no changes to another MongoDB installation, no password rotation.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import tarfile
import time
from urllib.parse import quote

ARCHIVE = 'mongodb-linux-x86_64-ubuntu2404-8.0.19.tgz'
SHA256 = '343c7a725beff28b546ff77633603441ec2bd67cb5c1d55f3129cf0a70dd2981'
SERVICE = 'makanwhere-mongo.service'
UNIT = Path('/etc/systemd/system') / SERVICE
STATE = Path('/var/lib/makanwhere-mongo')
PRIVATE = Path('/etc/makanwhere/mongo-private.json')
SOCKET = '/run/makanwhere-mongo/mongodb-27017.sock'
BINARY = Path('/opt/makanwhere-mongodb-8.0.19/bin/mongod')


def run(args, **kw):
    return subprocess.run(args, check=True, **kw)


def preflight(staging):
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') != '24.04':
        raise RuntimeError('MongoDB artifact requires Ubuntu 24.04; inspect the VM before choosing another artifact.')
    if platform.machine() != 'x86_64' or ' avx ' not in Path('/proc/cpuinfo').read_text():
        raise RuntimeError('MongoDB requires the reviewed x86_64/AVX platform.')
    if shutil.disk_usage('/var/lib').free < 2 * 1024**3:
        raise RuntimeError('Keep at least 2 GiB free for MongoDB and deployment backups.')
    memory = next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    if int(memory.split()[1]) < 2_000_000:
        raise RuntimeError('Review VM capacity: this deployment requires at least 2 GB RAM for both databases and tests.')
    if hashlib.sha256((staging / ARCHIVE).read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('MongoDB official artifact checksum mismatch.')
    if UNIT.exists() and '# Managed by Makan Where' not in UNIT.read_text():
        raise RuntimeError('Unrecognized MongoDB service; refusing to replace it.')
    if STATE.exists() and any(STATE.iterdir()) and not PRIVATE.exists():
        raise RuntimeError('Existing MongoDB data has no saved credentials; inspect it without resetting it.')


def uri(credentials, admin=False):
    username = 'makanwhere_root' if admin else 'makanwhere_app'
    password = credentials['root_password' if admin else 'app_password']
    database = 'admin' if admin else 'makanwhere'
    return f'mongodb://{username}:{quote(password, safe="")}@{quote(SOCKET, safe="")}/{database}?authSource={database}&directConnection=true'


def ensure(staging):
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure
    preflight(staging)
    if not BINARY.exists():
        with tarfile.open(staging / ARCHIVE) as archive:
            member = archive.getmember(ARCHIVE.removesuffix('.tgz') + '/bin/mongod')
            if not member.isfile():
                raise RuntimeError('Unexpected mongod archive entry.')
            BINARY.parent.mkdir(parents=True, exist_ok=True)
            with BINARY.open('xb') as target, archive.extractfile(member) as source:
                shutil.copyfileobj(source, target)
            BINARY.chmod(0o755)
    BINARY.parent.parent.chmod(0o755)
    BINARY.parent.chmod(0o755)
    dependencies = run(['ldd', str(BINARY)], capture_output=True, text=True).stdout
    if 'not found' in dependencies:
        raise RuntimeError('MongoDB shared libraries are missing; install the vendor-listed Ubuntu prerequisites before continuing.')
    run([str(BINARY), '--version'], stdout=subprocess.DEVNULL)
    if subprocess.run(['id', 'makanwhere-mongo'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run(['useradd', '--system', '--home-dir', '/nonexistent', '--shell', '/usr/sbin/nologin', 'makanwhere-mongo'])
    STATE.mkdir(mode=0o700, exist_ok=True)
    shutil.chown(STATE, user='makanwhere-mongo', group='www-data')
    STATE.chmod(0o700)
    PRIVATE.parent.mkdir(mode=0o700, exist_ok=True)
    if not PRIVATE.exists():
        credentials = {'root_password': secrets.token_urlsafe(48), 'app_password': secrets.token_urlsafe(48)}
        with PRIVATE.open('x') as stream:
            json.dump(credentials, stream)
        PRIVATE.chmod(0o600)
    credentials = json.loads(PRIVATE.read_text())
    unit = f'''# Managed by Makan Where
[Unit]
Description=Makan Where private community database
After=local-fs.target

[Service]
User=makanwhere-mongo
Group=www-data
ExecStart={BINARY} --dbpath {STATE} --auth --bind_ip 127.0.0.1 --port 27017 --unixSocketPrefix /run/makanwhere-mongo --filePermissions 0770 --wiredTigerCacheSizeGB 0.25
RuntimeDirectory=makanwhere-mongo
RuntimeDirectoryMode=0750
UMask=0007
Restart=on-failure
RestartSec=3
TimeoutStopSec=120
NoNewPrivileges=yes
PrivateNetwork=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
ReadWritePaths={STATE} /run/makanwhere-mongo
MemoryMax=768M
TasksMax=256
LimitNOFILE=64000

[Install]
WantedBy=multi-user.target
'''
    if not UNIT.exists():
        UNIT.write_text(unit)
        run(['systemctl', 'daemon-reload'])
    elif UNIT.read_text() != unit:
        raise RuntimeError('Existing MongoDB unit differs; review it before replacing it.')
    run(['systemctl', 'enable', '--now', SERVICE])
    for _ in range(30):
        if Path(SOCKET).exists():
            break
        time.sleep(1)
    else:
        raise RuntimeError('MongoDB socket did not appear; inspect its service journal.')
    root_uri = uri(credentials, admin=True)
    root = MongoClient(root_uri, serverSelectionTimeoutMS=10000)
    try:
        root.admin.command('ping')
    except OperationFailure as error:
        if error.code != 18:
            raise
        # MongoDB's localhost exception permits creating the FIRST user only.
        # Authentication stays enabled throughout; existing users are not reset.
        bootstrap_uri = f'mongodb://{quote(SOCKET, safe="")}/?directConnection=true'
        with MongoClient(bootstrap_uri, serverSelectionTimeoutMS=10000) as bootstrap:
            bootstrap.admin.command('createUser', 'makanwhere_root', pwd=credentials['root_password'], roles=['root'])
        root.close()
        root = MongoClient(root_uri, serverSelectionTimeoutMS=10000)
        root.admin.command('ping')
    if not root.makanwhere.command('usersInfo', 'makanwhere_app')['users']:
        root.makanwhere.command('createUser', 'makanwhere_app', pwd=credentials['app_password'], roles=[
            {'role': 'readWrite', 'db': 'makanwhere'}, {'role': 'dbAdmin', 'db': 'makanwhere'}])
    root.close()
    with MongoClient(uri(credentials), serverSelectionTimeoutMS=10000) as app:
        app.makanwhere.command('listCollections', nameOnly=True)
    return uri(credentials), root_uri


def backup_data(destination):
    """Cold filesystem backup: clean stop, copy, restart; caller stops web writes."""
    if shutil.disk_usage(destination.parent).free < sum(p.stat().st_size for p in STATE.rglob('*') if p.is_file()) + 1024**3:
        raise RuntimeError('Insufficient free space for a complete MongoDB backup.')
    run(['systemctl', 'stop', SERVICE])
    try:
        shutil.copytree(STATE, destination)
        destination.chmod(0o700)
    finally:
        run(['systemctl', 'start', SERVICE])
