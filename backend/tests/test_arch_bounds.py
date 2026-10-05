import subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_check_bounds_passes_on_skeleton():
    r = subprocess.run(
        [sys.executable, "backend/scripts/check_bounds.py"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
