"""Fail khi module import sâu module khác không qua public.py,
hoặc khi domain/application/presentation import package cấm."""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "detect_ai"
ROOT = SRC / "modules"
SCAN_EXTRA = [SRC / "main.py"]
SCAN_DIRS = [SRC / "api", SRC / "shared"]
FORBIDDEN = {
    # Spec chỉ cấm domain/application; presentation query DB trực tiếp trong strangler.
    "domain": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
    "application": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
}
CROSS_FROM_RE = re.compile(r"from\s+detect_ai\.modules\.([a-z_]+)\.([a-z_]+)")
CROSS_IMPORT_RE = re.compile(r"import\s+detect_ai\.modules\.([a-z_]+)\.([a-z_]+)")
CROSS_FROM_MOD_RE = re.compile(r"from\s+detect_ai\.modules\.([a-z_]+)\s+import\s+([^\n#]+)")
REL_FROM_RE = re.compile(r"from\s+\.+modules\.([a-z_]+)\.([a-z_]+)")
REL_IMPORT_RE = re.compile(r"import\s+\.+modules\.([a-z_]+)\.([a-z_]+)")
REL_FROM_MOD_RE = re.compile(r"from\s+\.+modules\.([a-z_]+)\s+import\s+([^\n#]+)")


def _layer_of(parts) -> str:
    for p in parts:
        if p in FORBIDDEN:
            return p
    return ""


def _check(text: str, owner: str, display: str, violations: list[str]) -> None:
    hits = (
        CROSS_FROM_RE.findall(text)
        + CROSS_IMPORT_RE.findall(text)
        + REL_FROM_RE.findall(text)
        + REL_IMPORT_RE.findall(text)
    )
    for target, sub in hits:
        if target != owner and sub not in ("public", "__init__"):
            violations.append(f"{display}: import sâu modules.{target}.{sub} (phải qua public)")
    mods = CROSS_FROM_MOD_RE.findall(text) + REL_FROM_MOD_RE.findall(text)
    for target, names in mods:
        if target == owner:
            continue
        for chunk in names.strip().strip("()").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            base = chunk.split(" as ")[0].strip().split()[0] if chunk else ""
            if base and base != "public" and base != "*" and not base.startswith("__"):
                violations.append(f"{display}: import sâu modules.{target}.{base} (phải qua public)")


def _iter_files():
    if ROOT.exists():
        yield from sorted(ROOT.rglob("*.py"))
    for extra in SCAN_EXTRA:
        if extra.exists():
            yield extra
    for d in SCAN_DIRS:
        if d.exists():
            yield from sorted(d.rglob("*.py"))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    violations: list[str] = []
    if not ROOT.exists():
        print("modules/ chưa tồn tại")
        return 1
    for py in _iter_files():
        text = py.read_text(encoding="utf-8")
        try:
            rel = py.relative_to(ROOT)
            owner = rel.parts[0]
            display = rel.as_posix()
            parts = rel.parts
        except ValueError:
            rel = py.relative_to(SRC)
            owner = ""
            display = rel.as_posix()
            parts = rel.parts
        _check(text, owner, display, violations)
        layer = _layer_of(parts)
        for pkg in FORBIDDEN.get(layer, ()):
            if re.search(rf"^\s*(from|import)\s+{pkg}\b", text, re.M):
                violations.append(f"{display}: layer {layer} cấm import {pkg}")
    for v in violations:
        print("VIOLATION:", v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
