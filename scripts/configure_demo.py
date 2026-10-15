"""Generate private Docker/local Python settings once; never overwrite secrets."""
import argparse
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / '.env.demo')
args = parser.parse_args()
passwords = {name: secrets.token_hex(24) for name in ('sql_root', 'sql_app', 'mongo_root', 'mongo_app', 'admin')}
lines = [
    '# Private local coursework configuration. Do not commit or share.',
    'SECRET_KEY=' + secrets.token_hex(32), 'PASSWORD_PEPPER=' + secrets.token_hex(32),
    'MARIADB_ROOT_PASSWORD=' + passwords['sql_root'], 'MARIADB_APP_PASSWORD=' + passwords['sql_app'],
    'MONGODB_ROOT_PASSWORD=' + passwords['mongo_root'], 'MONGODB_APP_PASSWORD=' + passwords['mongo_app'],
    f"DATABASE_URL=mysql+pymysql://makanwhere:{passwords['sql_app']}@127.0.0.1:3308/makanwhere_demo?charset=utf8mb4",
    f"MONGODB_URI=mongodb://makanwhere:{passwords['mongo_app']}@127.0.0.1:27018/makanwhere_demo?authSource=makanwhere_demo",
    'MONGODB_DATABASE=makanwhere_demo',
    f"MARIADB_TEST_ADMIN_URL=mysql+pymysql://root:{passwords['sql_root']}@127.0.0.1:3308/?charset=utf8mb4",
    f"MONGODB_TEST_URI=mongodb://demo_bootstrap:{passwords['mongo_root']}@127.0.0.1:27018/admin",
    'DEMO_ADMIN_USERNAME=demo_lecturer', 'DEMO_ADMIN_PASSWORD=' + passwords['admin'],
    'COOKIE_SECURE=false', 'TRUSTED_HOSTS=localhost,127.0.0.1', 'SAMPLE_CATALOGUE=true', '',
]
with args.output.open('x', encoding='utf-8') as stream:
    stream.write('\n'.join(lines))
print(f'Private settings saved to {args.output}. Keep this file, especially PASSWORD_PEPPER.')
