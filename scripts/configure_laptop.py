"""Create private laptop-only settings once; never replace existing credentials.

Only the Python standard library is needed, including when run in a container.
"""
import argparse
import os
from pathlib import Path
import secrets


def configure(path):
    values = {name: secrets.token_hex(32) for name in (
        'SECRET_KEY', 'PASSWORD_PEPPER', 'MARIADB_APP_PASSWORD', 'MARIADB_ROOT_PASSWORD',
        'MONGODB_APP_PASSWORD', 'MONGODB_ROOT_PASSWORD', 'TEST_SQL_PASSWORD', 'TEST_MONGO_PASSWORD')}
    values.update(APP_PORT='5056', LECTURER_ADMIN_USERNAME='lecturer_admin',
        LECTURER_ADMIN_PASSWORD=secrets.token_hex(12), LECTURER_USER_USERNAME='lecturer_user',
        LECTURER_USER_PASSWORD=secrets.token_hex(12))
    # Exclusive create is intentional: changing pepper/passwords breaks retained volumes.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
        output.write('# Private laptop configuration. Keep with this installation; do not commit.\n')
        for key, value in values.items():
            output.write(f'{key}={value}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.env.laptop'))
    args = parser.parse_args()
    try:
        configure(args.output)
    except FileExistsError:
        print(f'{args.output} already exists; credentials and pepper retained.')
    else:
        print(f'Created {args.output}. The two LECTURER_* account passwords are stored there.')
