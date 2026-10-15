"""Deploy Makan Where through the existing isolated VM and named tunnel.

Usage on 4bytedigi as root: python3 install_host.py prepare|publish
Artifacts must be alongside this script. DNS is configured separately.
"""
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

DOMAIN = 'makanwhere.4bytedigi.com'
SSH = ['ssh','-F','/etc/dbstudios-host/ssh_config']
HERE = Path(__file__).resolve().parent


def run(args, **kw): return subprocess.run(args,check=True,**kw)


def check_origin(host=DOMAIN,path='/api/health'):
    conn = http.client.HTTPConnection('127.0.0.1',3080,timeout=20)
    conn.request('GET',path,headers={'Host':host,'X-Forwarded-Proto':'https'})
    response = conn.getresponse()
    data = response.read()
    assert response.status == 200, (host,path,response.status)
    conn.close()
    return data


def prepare():
    for host in ['dbstudios.pyiesone.dev','hazrul-evite.pyiesone.dev']:
        check_origin(host)
    staging = run(SSH+['app','mktemp -d /tmp/makanwhere-release-XXXXXXXX'],capture_output=True,text=True).stdout.strip()
    assert staging.startswith('/tmp/makanwhere-release-') and len(staging.split('/')) == 3
    files = ['release.tar.gz','release.tar.gz.sha256','wheels.tar.gz','wheels.tar.gz.sha256',
             'install_guest.py','mongo_service.py','mongodb-linux-x86_64-ubuntu2404-8.0.19.tgz']
    run(['scp','-F','/etc/dbstudios-host/ssh_config']+[str(HERE/name) for name in files]+['app:'+staging+'/'])
    run(SSH+['app',f'sudo -n python3 {staging}/install_guest.py {staging}'])
    for host in [DOMAIN,'dbstudios.pyiesone.dev','hazrul-evite.pyiesone.dev']:
        check_origin(host)
    report = HERE/'prepared.json'
    report.write_text(json.dumps({'prepared':True,'domain':DOMAIN,'guestStaging':staging,'checkedAt':time.time()},indent=2))
    os.chown(report,1000,1000)
    print('Makan Where updated; existing neighbouring origins still healthy.')


def publish():
    assert (HERE/'prepared.json').exists(), 'Prepare and verify the app first.'
    check_origin()
    config = Path('/etc/cloudflared/config.yml')
    old = config.read_text()
    rule = f'  - hostname: {DOMAIN}\n    service: http://127.0.0.1:3080\n'
    if DOMAIN in old:
        assert rule in old, 'Existing domain has a different route; review it first.'
        print('Domain route already configured.')
        return
    anchor = '  - service: http_status:404'
    assert old.count(anchor) == 1, 'Unexpected tunnel configuration.'
    backup = Path('/var/backups/makanwhere')/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    backup.mkdir(parents=True,mode=0o700)
    backup.parent.chmod(0o700)
    shutil.copy2(config,backup/'cloudflared.yml')
    try:
        config.write_text(old.replace(anchor,rule+anchor))
        run(['cloudflared','--config',str(config),'tunnel','ingress','validate'])
        run(['systemctl','restart','dbstudios-tunnel'])
        run(['systemctl','is-active','--quiet','dbstudios-tunnel'])
        for host in [DOMAIN,'dbstudios.pyiesone.dev','hazrul-evite.pyiesone.dev']:
            check_origin(host)
    except BaseException:
        shutil.copy2(backup/'cloudflared.yml',config)
        run(['systemctl','restart','dbstudios-tunnel'])
        raise
    print('Domain route published. Existing routes retained; backup: '+str(backup))


if __name__ == '__main__':
    assert os.geteuid() == 0 and socket.gethostname() == '4bytedigi'
    {'prepare':prepare,'publish':publish}[sys.argv[1]]()
