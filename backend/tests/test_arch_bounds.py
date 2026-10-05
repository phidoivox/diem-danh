import subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_check_bounds_passes_on_skeleton():
    r = subprocess.run(
        [sys.executable, "backend/scripts/check_bounds.py"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_bounds_flags_violations():
    probe = REPO_ROOT / "backend" / "src" / "detect_ai" / "modules" / "identity" / "_tmp_arch_probe.py"
    probe.write_text("from detect_ai.modules.academic.infrastructure import x\n", encoding="utf-8")
    try:
        r = subprocess.run(
            [sys.executable, "backend/scripts/check_bounds.py"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 1, r.stdout + r.stderr
    finally:
        probe.unlink(missing_ok=True)
