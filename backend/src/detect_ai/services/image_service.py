from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi import HTTPException, UploadFile
from loguru import logger
from PIL import Image, ImageOps

from ..core.supabase import STORAGE_DIR, SupabaseStorageHelper, supabase_storage

SNAPSHOT_SUBDIR = "snapshots"

# Giới hạn decode ảnh upload để chống decompression-bomb / OOM.
MAX_IMAGE_PIXELS = 12_000_000  # ~12MP
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def decode_image_bytes(content: bytes) -> np.ndarray:
    """Decode bytes ảnh -> BGR uint8 (OpenCV-ready), xử lý EXIF orientation.

    Một cổng duy nhất thay các chỗ `cv2.imdecode` rải rác (files.py, storage).
    Pillow tự validate định dạng + EXIF; BGR giữ nguyên quy ước OpenCV.
    """
    try:
        with Image.open(BytesIO(content)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise ValueError("ảnh quá lớn")
            rgb = np.asarray(im, dtype=np.uint8)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"File ảnh lỗi hoặc không đọc được: {e}")
    return rgb[:, :, ::-1].copy()  # RGB -> BGR


async def decode_upload(photo: UploadFile) -> np.ndarray:
    content = await photo.read()
    if not content:
        raise HTTPException(422, "File ảnh rỗng")
    return decode_image_bytes(content)


def encode_jpeg(img_bgr: np.ndarray, quality: int = 85) -> bytes:
    """Encode BGR array -> JPEG bytes bằng Pillow (thay cv2.imencode rải rác)."""
    rgb = img_bgr[:, :, ::-1]
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=int(quality))
    return buf.getvalue()


def resolve_avatar_url(avatar_url: str | None, student_code: str) -> str | None:
    """Avatar DB -> fallback file local `/static/storage/avatars/<code>.jpg`."""
    if avatar_url:
        return avatar_url
    try:
        local_file: Path = (
            supabase_storage.storage_dir / SupabaseStorageHelper.BUCKET_AVATARS / f"{student_code}.jpg"
        )
    except Exception:  # noqa: BLE001
        return None
    if local_file.exists():
        return f"/static/storage/{SupabaseStorageHelper.BUCKET_AVATARS}/{student_code}.jpg"
    return None


async def upload_avatar_image(user_code: str, img_bgr: np.ndarray) -> str | None:
    """Upload ảnh chân dung (JPEG quality 85, upsert theo user_code).

    Trả None khi lỗi (ảnh chỉ để hiển thị).
    """
    try:
        content = encode_jpeg(img_bgr, quality=85)
        return await supabase_storage.upload_file(
            bucket=SupabaseStorageHelper.BUCKET_AVATARS,
            path=f"{user_code}.jpg",
            content=content,
            content_type="image/jpeg",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lỗi upload ảnh chân dung cho {user_code}: {e}")
        return None


def save_attendance_snapshot(
    img_bgr: np.ndarray,
    bbox: list[float] | tuple[float, ...] | None,
    schedule_id: int,
    student_id: int,
    kind: str,
    uniform_det=None,
    uniform_status: str = "unknown",
) -> str | None:
    """Lưu snapshot điểm danh xuống thư mục local, trả URL /static/storage/....

    Ảnh là FULL FRAME có vẽ khung làm bằng chứng (giống file *_uniform_*.jpg):
    khung xanh quanh mặt + khung áo (xanh = đạt, đỏ = vi phạm) + nhãn trạng
    thái + timestamp. Chỉ gọi đúng lúc transition check-in/check-out
    (tối đa 2 ảnh/người/tiết). kind: "in" | "out".
    uniform_det: UniformDetections của đúng frame này (để boxes khớp hình).
    Lỗi ghi đĩa -> log + trả None, không chặn điểm danh.
    """
    try:
        if img_bgr is None or getattr(img_bgr, "size", 0) == 0:
            return None
        h, w = img_bgr.shape[:2]
        from datetime import datetime, timezone

        from PIL import ImageDraw, ImageFont

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        GREEN, RED = (0, 200, 0), (220, 30, 30)

        rgb = img_bgr[:, :, ::-1].copy()
        pil = Image.fromarray(rgb)
        dr = ImageDraw.Draw(pil)
        try:
            font = ImageFont.load_default(size=20)
            small = ImageFont.load_default(size=16)
        except TypeError:  # Pillow cũ không có tham số size
            font = ImageFont.load_default()
            small = font

        # 1. Khung mặt (xanh = đã nhận diện chốt điểm danh).
        face_box: list[int] | None = None
        if bbox is not None and len(bbox) >= 4:
            face_box = [int(float(v)) for v in bbox[:4]]
            face_box[0] = max(0, face_box[0])
            face_box[1] = max(0, face_box[1])
            face_box[2] = min(w, face_box[2])
            face_box[3] = min(h, face_box[3])
            if face_box[2] > face_box[0] and face_box[3] > face_box[1]:
                dr.rectangle(face_box, outline=GREEN, width=3)
            else:
                face_box = None

        # 2. Khung đồng phục từ detect đúng frame này.
        names = list(getattr(uniform_det, "names", []) or [])
        xyxy = getattr(uniform_det, "xyxy", None)
        cids = getattr(uniform_det, "class_id", None)
        drew_shirt = False
        has_invalid = False
        label_box: list[int] | None = None
        label_col = RED
        if xyxy is not None and cids is not None and names:
            for i in range(len(xyxy)):
                cid = int(cids[i])
                if cid < 0 or cid >= len(names):
                    continue
                nm = names[cid]
                if nm not in ("valid_shirt", "invalid_shirt"):
                    continue
                sb = [max(0, int(float(v))) for v in xyxy[i][:4]]
                sb[2] = min(w, sb[2])
                sb[3] = min(h, sb[3])
                if sb[2] <= sb[0] or sb[3] <= sb[1]:
                    continue
                col = GREEN if nm == "valid_shirt" else RED
                dr.rectangle(sb, outline=col, width=3)
                drew_shirt = True
                if nm == "invalid_shirt":
                    has_invalid = True
                if label_box is None or nm == "invalid_shirt":
                    label_box, label_col = sb, col

        # 3. Vi phạm nhưng không thấy hộp áo -> khoanh đỏ person chứa mặt.
        is_bad = uniform_status == "violation"
        if is_bad and not drew_shirt and face_box is not None and xyxy is not None and cids is not None and names:
            fb = np.asarray(face_box, dtype=np.float32)
            for i in range(len(xyxy)):
                cid = int(cids[i])
                if cid < 0 or cid >= len(names) or names[cid] != "person":
                    continue
                pb = np.asarray(xyxy[i][:4], dtype=np.float32)
                if (pb[0] <= fb[0] + 5 and pb[1] <= fb[1] + 5
                        and pb[2] >= fb[2] - 5 and pb[3] >= fb[3] - 5):
                    box = [int(v) for v in pb]
                    dr.rectangle(box, outline=RED, width=3)
                    label_box, label_col = box, RED
                    break

        # 4. Nhãn trạng thái (ASCII để mọi font PIL đều vẽ được).
        txt: str | None = None
        if is_bad:
            reason = "sai_ao" if has_invalid else "thieu_ao_chuan"
            txt = f"VI PHAM: {reason}"
        elif uniform_status == "ok":
            txt = "DONG PHUC DAT"
        anchor = label_box or face_box
        if txt is not None and anchor is not None:
            tb = dr.textbbox((0, 0), txt, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            bx1 = max(0, anchor[0])
            by2 = max(th + 12, anchor[1] - 4)
            by1 = by2 - th - 10
            bar = GREEN if txt == "DONG PHUC DAT" else RED
            dr.rectangle([bx1, by1, bx1 + tw + 12, by2], fill=bar)
            dr.text((bx1 + 6, by1 + 5), txt, font=font, fill=(255, 255, 255))

        # 5. Timestamp góc trái-dưới.
        dr.text((8, h - 24), ts, font=small, fill=(255, 255, 255),
                stroke_width=1, stroke_fill=(0, 0, 0))

        annotated = np.asarray(pil)[:, :, ::-1].copy()
        # Giới hạn 640px cạnh dài để mỗi file chỉ ~60-120KB.
        try:
            ch, cw = annotated.shape[:2]
            longest = max(ch, cw)
            if longest > 640:
                import cv2

                s = 640.0 / float(longest)
                annotated = cv2.resize(annotated, (max(1, int(cw * s)), max(1, int(ch * s))),
                                       interpolation=cv2.INTER_LINEAR)
        except Exception:  # noqa: BLE001
            pass
        content = encode_jpeg(annotated, quality=75)
        safe_kind = "in" if kind == "in" else "out"
        subdir = STORAGE_DIR / SNAPSHOT_SUBDIR / str(int(schedule_id))
        subdir.mkdir(parents=True, exist_ok=True)
        fname = f"{int(student_id)}_{safe_kind}_{ts}.jpg"
        (subdir / fname).write_bytes(content)
        return f"/static/storage/{SNAPSHOT_SUBDIR}/{int(schedule_id)}/{fname}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Không lưu được snapshot điểm danh: {e}")
        return None
