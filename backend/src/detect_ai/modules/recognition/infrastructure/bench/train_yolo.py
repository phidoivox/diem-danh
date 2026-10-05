"""Fine-tune YOLO26 dong phuc. Khuyen dung: yolo train data=data/uniform/uniform_data.yaml model=yolo26n.pt epochs=100 imgsz=640
Wrapper nay giu de khoa class dung UNIFORM_CLASSES, tranh train nham class.
"""
from __future__ import annotations
import argparse
from ultralytics import YOLO
from detect_ai.shared.kernel.config import UNIFORM_CLASSES

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--model", default="yolo26n.pt")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    a = p.parse_args()
    YOLO(a.model).train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, classes=list(range(len(UNIFORM_CLASSES))))

if __name__ == "__main__":
    main()
