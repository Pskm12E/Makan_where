"""Run repeatable experiments in the test fixture's disposable databases.

No production URI is used as a test database. SQL schemas/Mongo databases get
unique makanwhere_test_* names and are cleaned by tests/test_api.py.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from importlib.metadata import version
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class EvidenceCollector:
    def __init__(self):
        self.results = {}

    def pytest_runtest_logreport(self, report):
        row = self.results.setdefault(report.nodeid, {'test': report.nodeid, 'outcome': 'passed', 'seconds': 0, 'evidence': {}})
        row['seconds'] += report.duration
        if report.failed or report.skipped:
            row['outcome'] = 'failed' if report.failed else 'skipped'
        for key, value in report.user_properties:
            row['evidence'][key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, help='Private local config; omit on a configured server.')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/evidence/database-evaluation.json')
    parser.add_argument('--full-suite', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.env:
        from scripts.run_demo import load_env
        load_env(args.env)
    if not os.environ.get('MONGODB_TEST_URI'):
        raise SystemExit('MONGODB_TEST_URI is required. Missing-engine skips are not evidence of success.')
    import pytest
    from backend.evaluation import source_fingerprint
    collector = EvidenceCollector()
    fingerprint = source_fingerprint()
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    code = pytest.main(['tests' if args.full_suite else 'tests/test_database_evaluation.py', '-q', '--tb=short', '-rs'], plugins=[collector])
    outcomes = Counter(row['outcome'] for row in collector.results.values())
    experiments = [row for row in collector.results.values() if row['test'].startswith('tests/test_database_evaluation.py::')]
    result = {'formatVersion': 1, 'startedAt': started, 'finishedAt': datetime.now(timezone.utc).isoformat(),
        'sourceSha256': fingerprint, 'sourceUnchangedDuringRun': fingerprint == source_fingerprint(),
        'fullSuite': args.full_suite, 'exitCode': int(code),
        'passed': int(code) == 0 and bool(experiments) and not outcomes['skipped'] and fingerprint == source_fingerprint(),
        'seconds': round(time.perf_counter() - clock, 3), 'summary': dict(outcomes),
        'environment': {'os': platform.system(), 'python': platform.python_version(), 'cpuCount': os.cpu_count(),
            'packages': {name: version(name) for name in ['Flask', 'SQLAlchemy', 'PyMySQL', 'pymongo', 'pytest']},
            'sqlTarget': 'MariaDB' if os.environ.get('MARIADB_TEST_ADMIN_URL') else 'SQLite'},
        'scope': 'Independent Flask test clients and real database drivers in disposable databases. Not an HTTP/network load test.',
        'experiments': experiments,
        'limits': ['No distributed ACID transaction across SQL and MongoDB.',
            'Injected failures test application recovery; they are not power-loss, replica failover or backup-restore tests.',
            'Benchmarks use a deterministic synthetic workload, warm caches and one host; timings are not a production capacity guarantee.',
            'Content edits use last-write-wins; simultaneous edit conflict detection is not implemented.',
            'A content POST interrupted after its MongoDB commit can have an ambiguous response; blindly retrying it may duplicate the post.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    temp.replace(args.output)
    print(f'Evaluation saved: {args.output}; passed={result["passed"]}; {dict(outcomes)}', flush=True)
    return int(code) if code else (0 if result['passed'] else 1)


if __name__ == '__main__':
    raise SystemExit(main())
