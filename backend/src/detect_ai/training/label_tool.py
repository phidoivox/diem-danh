"""GUI train dong phuc: video -> cat frame -> auto-label -> duyet tay -> train -> export.

Chay: cd backend && uv run python -m detect_ai.training.label_tool
Chi 1 buoc tay: tab "Duyet" (A=duyet, X=loai, chuot ve box, 0/1/2 doi class, Del xoa).
"""
from __future__ import annotations

import queue
import random
import shutil
import tempfile
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np

from ..shared.kernel.config import DATA_DIR, UNIFORM_CLASSES

WORK = DATA_DIR / "uniform" / "gui_work"
IMGS, LBL = WORK / "images", WORK / "labels"
COLORS = {0: "lime", 1: "deepskyblue", 2: "red"}


@dataclass
class Item:
    path: Path
    boxes: list = field(default_factory=list)  # (cls, x1, y1, x2, y2) pixel
    status: str = "pending"  # pending | ok | bad


def read_txt(p: Path, w: int, h: int) -> list:
    out = []
    if p.exists():
        for ln in p.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split()
            if len(parts) != 5:
                continue
            c, cx, cy, bw, bh = parts
            c = int(float(c))
            if 0 <= c < len(UNIFORM_CLASSES):
                out.append((c, (float(cx) - float(bw) / 2) * w, (float(cy) - float(bh) / 2) * h,
                            (float(cx) + float(bw) / 2) * w, (float(cy) + float(bh) / 2) * h))
    return out


def read_status(p: Path) -> str:
    if p.exists():
        for ln in reversed(p.read_text().splitlines()):
            ln = ln.strip()
            if ln.startswith("#"):
                s = ln[1:].strip()
                if s in ("ok", "bad", "pending"):
                    return s
    return "pending"


def write_txt(p: Path, boxes: list, w: int, h: int) -> None:
    lines = [f"{c} {((x1 + x2) / 2 / w):.4f} {((y1 + y2) / 2 / h):.4f} "
             f"{((x2 - x1) / w):.4f} {((y2 - y1) / h):.4f}" for c, x1, y1, x2, y2 in boxes]
    p.write_text("\n".join(lines))


def split_items(items: list[Item], seed: int = 7) -> tuple[list, list]:
    acc = [i for i in items if i.status == "ok"]
    random.Random(seed).shuffle(acc)
    k = max(1, int(len(acc) * 0.8)) if acc else 0
    return acc[:k], acc[k:]


class LabelTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Train dong phuc")
        self.geometry("1100x750")
        IMGS.mkdir(parents=True, exist_ok=True)
        LBL.mkdir(parents=True, exist_ok=True)
        self.items: list[Item] = self._load_work()
        self.idx = 0
        self.sel = -1
        self.q: queue.Queue = queue.Queue()
        self._img_ref = None
        self._build()
        self._refresh_all()
        self.after(200, self._poll)

    # ---------- setup ----------
    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.t1, self.t2, self.t3, self.t4 = (ttk.Frame(nb) for _ in range(4))
        for t, s in zip((self.t1, self.t2, self.t3, self.t4),
                        ("1. Video", "2. Auto-label", "3. Duyet", "4. Train")):
            nb.add(t, text=s)
        self._build_video()
        self._build_autolabel()
        self._build_review()
        self._build_train()
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status).pack(side="bottom", fill="x")

    def _load_work(self) -> list[Item]:
        items = []
        for p in sorted(IMGS.glob("*.jpg")):
            img = cv2.imread(str(p))
            if img is None:
                continue
            h, w = img.shape[:2]
            t = LBL / (p.stem + ".txt")
            items.append(Item(p, read_txt(t, w, h), read_status(t)))
        return items

    def _save_item(self, it: Item):
        img = cv2.imread(str(it.path))
        h, w = img.shape[:2]
        write_txt(LBL / (it.path.stem + ".txt"), it.boxes, w, h)
        # giu status trong dong comment cuoi file de mo lai van con
        with open(LBL / (it.path.stem + ".txt"), "a") as f:
            f.write(f"\n# {it.status}\n")

    # ---------- tab 1: video ----------
    def _build_video(self):
        self.videos: list[Path] = []
        self.vid_list = tk.Listbox(self.t1, height=8)
        self.vid_list.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(self.t1)
        r.pack(fill="x", padx=8)
        self.stride = tk.IntVar(value=15)
        self.dedup = tk.DoubleVar(value=6.0)
        ttk.Button(r, text="Them video", command=self._add_videos).pack(side="left")
        ttk.Label(r, text="stride").pack(side="left", padx=(12, 2))
        ttk.Spinbox(r, from_=1, to=120, textvariable=self.stride, width=5).pack(side="left")
        ttk.Label(r, text="dedup").pack(side="left", padx=(12, 2))
        ttk.Spinbox(r, from_=0, to=50, increment=0.5, textvariable=self.dedup, width=5).pack(side="left")
        ttk.Button(r, text="Cat frame", command=self._cut).pack(side="left", padx=12)
        self.cut_info = tk.StringVar(value=f"work: {len(self.items)} anh")
        ttk.Label(self.t1, textvariable=self.cut_info).pack(padx=8, anchor="w")

    def _add_videos(self):
        for f in filedialog.askopenfilenames(filetypes=[("video", "*.mp4 *.avi *.mov *.mkv")]):
            self.videos.append(Path(f))
            self.vid_list.insert("end", f)

    def _cut(self):
        def job():
            n = 0
            prev = None
            for v in self.videos:
                cap = cv2.VideoCapture(str(v))
                i = 0
                while True:
                    ok, fr = cap.read()
                    if not ok:
                        break
                    if i % max(1, self.stride.get()) == 0:
                        small = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (32, 32))
                        if prev is None or float(np.abs(small.astype(int) - prev).mean()) >= self.dedup.get():
                            p = IMGS / f"{v.stem}_{n:05d}.jpg"
                            cv2.imwrite(str(p), fr)
                            self.items.append(Item(p))
                            n += 1
                            prev = small
                    i += 1
                cap.release()
            self.q.put(("cut_done", n))
        threading.Thread(target=job, daemon=True).start()
        self.status.set("dang cat frame...")

    # ---------- tab 2: auto-label ----------
    def _build_autolabel(self):
        r = ttk.Frame(self.t2)
        r.pack(fill="x", padx=8, pady=8)
        self.conf = tk.DoubleVar(value=0.35)
        ttk.Label(r, text="conf").pack(side="left")
        ttk.Spinbox(r, from_=0.1, to=0.9, increment=0.05, textvariable=self.conf, width=5).pack(side="left", padx=4)
        ttk.Button(r, text="Chay auto-label", command=self._autolabel).pack(side="left", padx=8)
        self.prog = ttk.Progressbar(self.t2, mode="determinate")
        self.prog.pack(fill="x", padx=8)
        self.al_info = tk.StringVar()
        ttk.Label(self.t2, textvariable=self.al_info).pack(padx=8, anchor="w")

    def _autolabel(self):
        todo = [it for it in self.items if it.status == "pending" and not it.boxes]
        if not todo:
            messagebox.showinfo("xong", "khong co anh nao can label")
            return

        def job():
            from ..recognition.uniform_engine import UniformEngine
            eng = UniformEngine(conf=self.conf.get()).open()
            for k, it in enumerate(todo):
                img = cv2.imread(str(it.path))
                det = eng.predict(img)
                it.boxes = [(int(c), *map(float, b)) for b, c in zip(det.xyxy, det.class_id)]
                self._save_item(it)
                self.q.put(("prog", (k + 1) / len(todo)))
            self.q.put(("al_done", len(todo)))
        threading.Thread(target=job, daemon=True).start()

    # ---------- tab 3: review ----------
    def _build_review(self):
        bar = ttk.Frame(self.t3)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="◀", width=3, command=lambda: self._nav(-1)).pack(side="left")
        ttk.Button(bar, text="▶", width=3, command=lambda: self._nav(1)).pack(side="left")
        self.newcls = tk.IntVar(value=1)
        for i, n in enumerate(UNIFORM_CLASSES):
            ttk.Radiobutton(bar, text=n, variable=self.newcls, value=i).pack(side="left", padx=4)
        ttk.Button(bar, text="Duyet (A)", command=self._accept).pack(side="left", padx=8)
        ttk.Button(bar, text="Loai (X)", command=self._reject).pack(side="left")
        self.rv_info = tk.StringVar()
        ttk.Label(bar, textvariable=self.rv_info).pack(side="left", padx=12)
        self.cv = tk.Canvas(self.t3, bg="black")
        self.cv.pack(fill="both", expand=True, padx=8, pady=4)
        self.cv.bind("<Button-1>", self._down)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonRelease-1>", self._up)
        self.bind("<Key>", self._key)
        self._d0 = None

    def _nav(self, d: int):
        if self.items:
            self.idx = (self.idx + d) % len(self.items)
            self.sel = -1
            self._draw()

    def _accept(self):
        if self.items:
            it = self.items[self.idx]
            it.status = "ok"
            self._save_item(it)
            self._nav(1)
            self._refresh_all()

    def _reject(self):
        if self.items:
            it = self.items[self.idx]
            it.status = "bad"
            self._save_item(it)
            self._nav(1)
            self._refresh_all()

    def _key(self, e):
        if e.keysym in ("a", "A"):
            self._accept()
        elif e.keysym in ("x", "X"):
            self._reject()
        elif e.keysym in ("Left", "Right"):
            self._nav(-1 if e.keysym == "Left" else 1)
        elif e.keysym == "Delete" and self.items and 0 <= self.sel < len(self.items[self.idx].boxes):
            del self.items[self.idx].boxes[self.sel]
            self.sel = -1
            self._save_item(self.items[self.idx])
            self._draw()
        elif e.keysym in ("0", "1", "2") and self.items and 0 <= self.sel < len(self.items[self.idx].boxes):
            c, x1, y1, x2, y2 = self.items[self.idx].boxes[self.sel]
            self.items[self.idx].boxes[self.sel] = (int(e.keysym), x1, y1, x2, y2)
            self._save_item(self.items[self.idx])
            self._draw()

    def _cv_xy(self, e):
        return self.cv.canvasx(e.x) / self._s, self.cv.canvasy(e.y) / self._s

    def _down(self, e):
        if not self.items:
            return
        x, y = self._cv_xy(e)
        boxes = self.items[self.idx].boxes
        self.sel = next((i for i in range(len(boxes) - 1, -1, -1)
                         if boxes[i][1] <= x <= boxes[i][3] and boxes[i][2] <= y <= boxes[i][4]), -1)
        self._d0 = None if self.sel >= 0 else (x, y)
        self._draw()

    def _drag(self, e):
        if self._d0 and self.items:
            x, y = self._cv_xy(e)
            self._dragbox = (*self._d0, x, y)
            self._draw()

    def _up(self, e):
        if self._d0 and self.items and getattr(self, "_dragbox", None):
            x0, y0, x1, y1 = self._dragbox
            if abs(x1 - x0) > 8 and abs(y1 - y0) > 8:
                self.items[self.idx].boxes.append(
                    (self.newcls.get(), min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                self._save_item(self.items[self.idx])
        self._d0 = None
        self._dragbox = None
        self._draw()

    def _draw(self):
        self.cv.delete("all")
        if not self.items:
            return
        it = self.items[self.idx]
        img = cv2.imread(str(it.path))
        h0, w0 = img.shape[:2]
        self._s = min(1000 / w0, 640 / h0, 1.0)
        disp = cv2.resize(img, (int(w0 * self._s), int(h0 * self._s)))
        with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as t:
            cv2.imwrite(t.name, disp)
            self._img_ref = tk.PhotoImage(file=t.name)
        Path(t.name).unlink(missing_ok=True)
        self.cv.config(width=self._img_ref.width(), height=self._img_ref.height())
        self.cv.create_image(0, 0, anchor="nw", image=self._img_ref)
        for i, (c, x1, y1, x2, y2) in enumerate(it.boxes):
            col = "yellow" if i == self.sel else COLORS.get(c, "white")
            self.cv.create_rectangle(x1 * self._s, y1 * self._s, x2 * self._s, y2 * self._s,
                                     outline=col, width=3 if i == self.sel else 2)
            self.cv.create_text(x1 * self._s + 4, y1 * self._s - 10, anchor="w", fill=col,
                                text=UNIFORM_CLASSES[c] if c < len(UNIFORM_CLASSES) else c)
        if getattr(self, "_dragbox", None):
            x0, y0, x1, y1 = self._dragbox
            self.cv.create_rectangle(x0 * self._s, y0 * self._s, x1 * self._s, y1 * self._s,
                                     outline="yellow", dash=(4, 2))
        ok = sum(1 for i in self.items if i.status == "ok")
        bad = sum(1 for i in self.items if i.status == "bad")
        self.rv_info.set(f"{self.idx + 1}/{len(self.items)} {it.path.name} "
                         f"[{it.status}] ok={ok} bad={bad} pending={len(self.items) - ok - bad}")

    # ---------- tab 4: train ----------
    def _build_train(self):
        r = ttk.Frame(self.t4)
        r.pack(fill="x", padx=8, pady=8)
        self.epochs = tk.IntVar(value=100)
        self.imgsz = tk.IntVar(value=640)
        self.autoexp = tk.BooleanVar(value=True)
        ttk.Label(r, text="epochs").pack(side="left")
        ttk.Spinbox(r, from_=10, to=500, textvariable=self.epochs, width=6).pack(side="left", padx=4)
        ttk.Label(r, text="imgsz").pack(side="left")
        ttk.Combobox(r, textvariable=self.imgsz, values=(416, 640), width=6).pack(side="left", padx=4)
        ttk.Checkbutton(r, text="tu export ONNX sau train", variable=self.autoexp).pack(side="left", padx=8)
        ttk.Button(r, text="Train", command=self._train).pack(side="left", padx=4)
        ttk.Button(r, text="Dong goi Colab (.zip)", command=self._zip_colab).pack(side="left", padx=4)
        ttk.Button(r, text="Thay model chinh", command=self._deploy).pack(side="left", padx=4)
        self.tr_info = tk.StringVar(value="chua train")
        ttk.Label(self.t4, textvariable=self.tr_info).pack(padx=8, anchor="w")
        self.log = tk.Text(self.t4, height=20)
        self.log.pack(fill="both", expand=True, padx=8, pady=4)
        self.best_pt: Path | None = None

    def _log(self, s: str):
        self.log.insert("end", s + "\n")
        self.log.see("end")

    def _train(self):
        tr, va = split_items(self.items)
        if len(tr) < 10:
            messagebox.showwarning("thieu data", f"chi co {len(tr)} anh train, can >= 10")
            return
        root = DATA_DIR / "uniform"
        for d in ("images/train", "images/val", "labels/train", "labels/val"):
            (root / d).mkdir(parents=True, exist_ok=True)
            for f in (root / d).glob("*"):
                f.unlink()
        for subset, sub in ((tr, "train"), (va, "val")):
            for it in subset:
                img = cv2.imread(str(it.path))
                h, w = img.shape[:2]
                shutil.copy(it.path, root / f"images/{sub}" / it.path.name)
                write_txt(root / f"labels/{sub}" / (it.path.stem + ".txt"), it.boxes, w, h)
        yaml = (root / "uniform_data.yaml")
        yaml.write_text(f"path: {root.resolve()}\ntrain: images/train\nval: images/val\nnames:\n" +
                        "".join(f"  {i}: {n}\n" for i, n in enumerate(UNIFORM_CLASSES)), encoding="utf-8")
        self._log(f"dataset: train={len(tr)} val={len(va)}")

        def job():
            from ultralytics import YOLO
            base = "yolo26n.pt"
            for cand in (Path("backend") / "yolo26n.pt", Path("yolo26n.pt"), Path(base)):
                if cand.exists():
                    base = str(cand)
                    break
            self.q.put(("log", f"train tu {base} ..."))
            YOLO(base).train(data=str(yaml), epochs=self.epochs.get(), imgsz=self.imgsz.get(),
                             classes=list(range(len(UNIFORM_CLASSES))))
            runs = sorted(Path("runs/detect").glob("train*/weights/best.pt"),
                          key=lambda p: p.stat().st_mtime)
            self.best_pt = runs[-1] if runs else None
            self.q.put(("train_done", str(self.best_pt)))
        threading.Thread(target=job, daemon=True).start()
        self.tr_info.set("dang train (log chi tiet o terminal)...")

    def _zip_colab(self):
        import zipfile
        tr, va = split_items(self.items)
        acc = tr + va
        if len(acc) < 10:
            messagebox.showwarning("thieu data", f"chi co {len(acc)} anh ok, can >= 10")
            return
        root = DATA_DIR / "uniform"
        for d in ("images/train", "images/val", "labels/train", "labels/val"):
            (root / d).mkdir(parents=True, exist_ok=True)
            for f in (root / d).glob("*"):
                f.unlink()
        for subset, sub in ((tr, "train"), (va, "val")):
            for it in subset:
                img = cv2.imread(str(it.path))
                h, w = img.shape[:2]
                shutil.copy(it.path, root / f"images/{sub}" / it.path.name)
                write_txt(root / f"labels/{sub}" / (it.path.stem + ".txt"), it.boxes, w, h)
        (root / "uniform_data.yaml").write_text(
            f"path: {root.resolve()}\ntrain: images/train\nval: images/val\nnames:\n" +
            "".join(f"  {i}: {n}\n" for i, n in enumerate(UNIFORM_CLASSES)), encoding="utf-8")
        zf = root / "uniform.zip"
        with zipfile.ZipFile(zf, "w", zipfile.ZIP_DEFLATED) as z:
            for sub in ("images/train", "images/val", "labels/train", "labels/val"):
                for f in (root / sub).glob("*"):
                    z.write(f, f"uniform/{sub}/{f.name}")
        messagebox.showinfo("xong", f"da dong goi {zf}\n({len(tr)} train + {len(va)} val)\n"
                                     f"upload file nay vao cell 3 cua colab_train_uniform.ipynb")
        self._log(f"colab zip: {zf} ({len(tr)} train + {len(va)} val)")

    def _deploy(self):
        if not self.best_pt or not self.best_pt.exists():
            messagebox.showwarning("chua co model", "train truoc hoac best.pt khong ton tai")
            return
        from .export_yolo_onnx import export_onnx
        out = DATA_DIR / "weights" / "yolo26n.onnx"
        if out.exists():
            shutil.copy(out, out.with_suffix(".onnx.bak"))
        export_onnx(self.best_pt, out)
        self.tr_info.set(f"da thay {out.name} (backup .bak)")
        messagebox.showinfo("xong", f"da thay model chinh.\nrestart backend de nap.")

    # ---------- poll ----------
    def _poll(self):
        try:
            while True:
                k, v = self.q.get_nowait()
                if k == "cut_done":
                    self.cut_info.set(f"work: {len(self.items)} anh (+{v} moi)")
                    self.status.set("cat frame xong")
                    self._draw()
                elif k == "prog":
                    self.prog["value"] = v * 100
                elif k == "al_done":
                    self.al_info.set(f"da label {v} anh. sang tab Duyet (A duyet, X loai).")
                    self._draw()
                elif k == "log":
                    self._log(v)
                elif k == "train_done":
                    if v and v != "None":
                        import csv
                        res = Path(v).parents[1] / "results.csv"
                        tail = list(csv.DictReader(res.open()))[-1] if res.exists() else {}
                        map50 = tail.get("metrics/mAP50(B)", "?")
                        self.tr_info.set(f"train xong: {v} mAP50={map50}")
                        self._log(f"best: {v} mAP50={map50}")
                        if self.autoexp.get():
                            self._deploy()
                    else:
                        self.tr_info.set("train loi: khong thay best.pt")
        except queue.Empty:
            pass
        self.after(200, self._poll)

    def _refresh_all(self):
        ok = sum(1 for i in self.items if i.status == "ok")
        self.cut_info.set(f"work: {len(self.items)} anh (ok={ok})")
        self._draw()


def main():
    LabelTool().mainloop()


if __name__ == "__main__":
    main()
