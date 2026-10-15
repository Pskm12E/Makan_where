"""Collect and enforce evidence under the actual application OS/DB identity."""
import grp
import json
import os
from pathlib import Path
import pwd
import sys
from install_guest import CONFIG, read_environment


def main():
    release = Path(sys.argv[1]).resolve()
    os.environ.update(read_environment(CONFIG))
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    user = pwd.getpwnam('makanwhere')
    group = grp.getgrnam('www-data')
    os.initgroups('makanwhere', group.gr_gid)
    os.setgid(group.gr_gid)
    os.setuid(user.pw_uid)
    os.chdir(release)
    sys.path.insert(0, str(release))
    from backend.app import create_app
    from backend.database_lab import lab_snapshot, constraint_probes, security_evidence
    app = create_app()
    with app.app_context():
        snapshot, probes = lab_snapshot(), constraint_probes()
        evaluation = snapshot['evaluation']
        if (evaluation.get('status') != 'recorded' or not evaluation.get('passed') or
                not evaluation.get('currentSource') or not evaluation.get('fullSuite') or
                evaluation.get('environment', {}).get('sqlTarget') != 'MariaDB'):
            raise RuntimeError('Current-source MariaDB/MongoDB evaluation is missing or failed.')
        audit = snapshot['audit']
        if not all(check['passed'] for check in probes['checks']):
            raise RuntimeError('A constraint demonstration failed with deployed permissions.')
        if (any(item['orphans'] for item in audit['sqlForeignKeys']) or
                any(audit['mongoReferences'].values()) or audit['duplicateSourceIdentities'] or audit['duplicateVoteGroups']):
            raise RuntimeError('Integrity audit found duplicate identities or broken references.')
        print(json.dumps({'snapshot':snapshot, 'probes':probes, 'security':security_evidence()}, default=str))


if __name__ == '__main__':
    main()
