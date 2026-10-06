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


def test_bounds_catches_main_deep_import():
    main_py = REPO_ROOT / "backend" / "src" / "detect_ai" / "main.py"
    original = main_py.read_text(encoding="utf-8")
    main_py.write_text(
        original + "\nfrom detect_ai.modules.academic.presentation import routes  # _tmp_arch_probe\n",
        encoding="utf-8",
    )
    try:
        r = subprocess.run(
            [sys.executable, "backend/scripts/check_bounds.py"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 1, r.stdout + r.stderr
        assert "main.py" in r.stdout, r.stdout
        assert "modules.academic.presentation" in r.stdout, r.stdout
    finally:
        main_py.write_text(original, encoding="utf-8")


def test_no_temp_allow():
    src = (REPO_ROOT / "backend" / "scripts" / "check_bounds.py").read_text(encoding="utf-8")
    assert "TEMP_ALLOW" not in src
    for snippet in (
        "leave/application/review",
        "evaluation/application/nightly",
        "reporting/application/build",
    ):
        assert snippet not in src, snippet
