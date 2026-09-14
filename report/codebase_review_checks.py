"""Run current repair regressions. Historical observations remain in codebase-review-checks.json."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-q',
                                     'tests/test_review_repairs.py'], cwd=root))
