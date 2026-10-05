from __future__ import annotations
import asyncio
import time
import cv2
import numpy as np
from loguru import logger
from ..core.config import SNAPSHOT_DIR
from ..core.database import Session
from ..models.attendance import AttendanceRecord

# Hang doi luu diem danh: thay thread-moi-lan-log cu (leak thread khi dong nguoi).
queue: asyncio.Queue = asyncio.Queue(maxsize=200)


async def saver_loop():
    while True:
        r, img = await queue.get()
        try:
            name = f"{r['student']}_{int(time.time())}.jpg"
            await asyncio.to_thread(cv2.imwrite, str(SNAPSHOT_DIR / name), img)
            async with Session() as s:
                s.add(AttendanceRecord(student_code=r["student"], uniform_status=r["uniform"],
                                       violations=",".join(r["violations"]), snapshot=name))
                await s.commit()
        except Exception as e:
            logger.warning(f"save attendance skip: {e}")
        finally:
            queue.task_done()


def put(r: dict, img: np.ndarray):
    try:
        queue.put_nowait((r, img))
    except asyncio.QueueFull:
        logger.warning("save queue full, drop log")
