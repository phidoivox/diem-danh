"""Fail khi module import sâu module khác không qua public.py,
hoặc khi domain/application import package cấm."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "detect_ai" / "modules"
FORBIDDEN = {
    "domain": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
    "application": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
}
CROSS_FROM_RE = re.compile(r"from\s+detect_ai\.modules\.([a-z_]+)\.([a-z_]+)")
CROSS_IMPORT_RE = re.compile(r"import\s+detect_ai\.modules\.([a-z_]+)\.([a-z_]+)")
CROSS_FROM_MOD_RE = re.compile(r"from\s+detect_ai\.modules\.([a-z_]+)\s+import\s+([^\n#]+)")


def main() -> int:
    violations: list[str] = []
    if not ROOT.exists():
        print("modules/ chưa tồn tại")
        return 1
    for py in sorted(ROOT.rglob("*.py")):
        rel = py.relative_to(ROOT)
        owner = rel.parts[0]
        layer = rel.parts[1] if len(rel.parts) > 2 else ""
        text = py.read_text(encoding="utf-8")
        hits = CROSS_FROM_RE.findall(text) + CROSS_IMPORT_RE.findall(text)
        for target, sub in hits:
            if target != owner and sub not in ("public", "__init__"):
                violations.append(f"{rel}: import sâu modules.{target}.{sub} (phải qua public)")
        for target, names in CROSS_FROM_MOD_RE.findall(text):
            if target == owner:
                continue
            for name in re.split(r"[,\s]+", names.strip().strip("()")):
                base = name.split(" as ")[0].strip()
                if base and base != "public" and not base.startswith("__"):
                    violations.append(f"{rel}: import sâu modules.{target}.{base} (phải qua public)")
        for pkg in FORBIDDEN.get(layer, ()):
            if re.search(rf"^\s*(from|import)\s+{pkg}\b", text, re.M):
                violations.append(f"{rel}: layer {layer} cấm import {pkg}")
    for v in violations:
        print("VIOLATION:", v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
