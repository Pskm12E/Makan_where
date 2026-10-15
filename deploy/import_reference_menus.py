"""Preview/apply packaged reference menus through the running VM's scoped API.

Run as root in the existing app VM. --apply enables a private integration key
if needed and imports only the reviewed packaged KFC and Suki-Ya snapshots.
No credential is printed, sent to another host, or passed as a CLI argument.
"""
import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode


class LocalAPI(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/run/makanwhere/web.sock')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root in the existing application VM.')
    os.umask(0o077)
    release = Path('/srv/makanwhere/current').resolve(strict=True)
    if release.parent != Path('/srv/makanwhere/releases'):
        raise SystemExit('Expected a managed application release.')
    sys.path.insert(0, str(release / 'deploy'))
    from install_guest import CONFIG, read_environment, write_environment, healthy
    config = read_environment(CONFIG)
    key = config.get('MENU_IMPORT_API_KEY', '')
    if not key:
        if not args.apply:
            raise SystemExit('No server integration key exists. --apply creates it privately before preview/import.')
        backup = Path('/var/backups/makanwhere') / time.strftime('menu-import-%Y%m%dT%H%M%SZ', time.gmtime())
        backup.mkdir(mode=0o700)
        shutil.copy2(CONFIG, backup / 'app.env')
        (backup / 'app.env').chmod(0o600)
        key = secrets.token_urlsafe(48)
        config['MENU_IMPORT_API_KEY'] = key
        write_environment(config)
        subprocess.run(['systemctl', 'restart', 'makanwhere'], check=True)
        healthy()
    if len(key) < 32:
        raise SystemExit('The existing integration key is too short; it was preserved for review.')

    def api(path, body=None):
        conn = LocalAPI('makanwhere.4bytedigi.com', timeout=60)
        try:
            conn.request('POST' if body is not None else 'GET', '/api/integrations/' + path,
                body=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                         'X-Forwarded-Proto': 'https'})
            response = conn.getresponse()
            result = json.loads(response.read())
            if response.status != 200:
                raise RuntimeError(f'Import API returned HTTP {response.status}: {result.get("error", "request failed")}')
            return result
        finally:
            conn.close()

    results = []
    for name in ['kfc_sg_reference_20261004.json', 'sukiya_sg_reference_20261004.json']:
        menu = json.loads((release / 'data/menus' / name).read_text())
        if not menu.get('isReference') or menu.get('places'):
            raise RuntimeError('Expected a shared reference snapshot without preselected server IDs.')
        targets = {}
        for chain in menu.pop('matchNames'):
            for place in api('menu-targets?' + urlencode({'name': chain}))['places']:
                targets[place['id']] = {k: place[k] for k in ('id', 'name', 'sourceId')}
        if not targets:
            raise RuntimeError(f'No exact matching establishments for {name}; nothing was guessed.')
        menu['places'] = sorted(targets.values(), key=lambda p: p['id'])
        preview = api('menu-imports', {'menu': menu})
        summary = {'source': name, 'venues': len(targets), 'added': preview['added'],
                   'skipped': preview['skipped'], 'conflicts': len(preview['conflicts'])}
        print(json.dumps({'preview': summary}), flush=True)
        if preview['conflicts']:
            raise RuntimeError('Existing menu names conflict; resolve them in the administrator menu editor.')
        if args.apply:
            result = api('menu-imports', {'menu': preview['menu'], 'apply': True,
                                         'previewToken': preview['previewToken']})
            assert result['applied'] and result['added'] == preview['added']
            repeated = api('menu-imports', {'menu': preview['menu']})
            assert repeated['added'] == 0 and not repeated['conflicts']
            summary.update(applied=True, repeatPreviewAdded=repeated['added'])
        results.append(summary)
    healthy()
    print(json.dumps({'menuImports': results, 'healthy': True}), flush=True)


if __name__ == '__main__':
    main()
