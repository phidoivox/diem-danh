"""Pull dataset tu Roboflow + sinh uniform_data.yaml.
Chay: python -m detect_ai.training.prepare_dataset --workspace WS --project PJ --version N --api-key KEY
"""
from __future__ import annotations
import argparse
from pathlib import Path
from ..core.config import UNIFORM_CLASSES, DATA_DIR

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(DATA_DIR / "uniform"))
    p.add_argument("--workspace", default="")
    p.add_argument("--project", default="")
    p.add_argument("--version", default="1")
    p.add_argument("--api-key", default="")
    a = p.parse_args()
    root = Path(a.root)
    if a.workspace and a.project and a.api_key:
        from roboflow import Roboflow
        rf = Roboflow(api_key=a.api_key)
        ds = rf.workspace(a.workspace).project(a.project).version(a.version).download("yolov8", location=str(root))
        print("pulled roboflow ->", ds.location)
    for d in ("images/train", "images/val", "labels/train", "labels/val"):
        (root / d).mkdir(parents=True, exist_ok=True)
    yaml = f"path: {root.resolve()}\ntrain: images/train\nval: images/val\nnames:\n"
    yaml += "".join(f"  {i}: {n}\n" for i, n in enumerate(UNIFORM_CLASSES))
    (root / "uniform_data.yaml").write_text(yaml, encoding="utf-8")
    print("wrote", root / "uniform_data.yaml")

if __name__ == "__main__":
    main()
