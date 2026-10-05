from __future__ import annotations

"""WebSocket Kiosk: stream frame 2 chiều, rớt frame cũ khi bận.

Protocol (giữ nguyên để frontend không vỡ):
- Client -> server: binary JPEG (480px q0.6, mỗi ~450ms, 1 in-flight).
- Server -> client: JSON {faces:[{track_id,bbox,student_id,user_code,full_name,
  score,liveness,decision,votes}], infer_ms, next_interval_ms, next_width, dropped}.
- Auth: ?schedule_id=&token=<JWT teacher> (WS không gửi Authorization header được).
- Fallback: mất WS thì frontend dùng POST /api/v1/kiosk/checkin như cũ.

Engine recognition v2. Queue(maxsize=1) latest-only + 2 task recv/infer riêng;
mỗi schedule 1 KioskSession.
"""

import asyncio
import time
from detect_ai.api.deps_kiosk import adaptive_feedback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from detect_ai.shared.kernel.database import Session
from detect_ai.core.security import decode_access_token
from detect_ai.models.user import User
from detect_ai.modules.attendance.application.checkin import record_checkin
from detect_ai.modules.recognition import public
from detect_ai.services.settings_repo import load_min_checkout_gap

router = APIRouter()


async def _auth_teacher(token: str | None, protocols: str | None = None) -> User | None:
    if not token and protocols:
        for p in protocols.split(","):
            p = p.strip()
            if p.startswith("jwt-"):
                token = p[4:]
                break
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    if not payload or payload.get("role") != "TEACHER":
        return None
    try:
        uid = int(payload.get("sub"))
    except Exception:
        return None
    try:
        async with Session() as s:
            u = await s.get(User, uid)
            if u is None or not u.is_active or u.deleted_at is not None:
                return None
            # Detach để dùng ngoài session.
            return User(id=u.id, user_code=u.user_code, full_name=u.full_name,
                        email=u.email, password_hash="", role_id=u.role_id,
                        is_active=True)
    except Exception:
        return None


@router.websocket("/api/v1/kiosk/ws")
async def kiosk_ws(ws: WebSocket):
    await ws.accept()
    cfg = public.get_config()
    params = ws.query_params
    try:
        schedule_id = int(params.get("schedule_id", "0"))
    except Exception:
        await ws.send_json({"error": "schedule_id không hợp lệ"})
        await ws.close()
        return
    teacher = await _auth_teacher(params.get("token"), ws.headers.get("sec-websocket-protocol"))
    if teacher is None:
        await ws.send_json({"error": "token giáo viên không hợp lệ"})
        await ws.close()
        return

    from fastapi import HTTPException as _HTTPException

    from detect_ai.api.deps_kiosk import authorize_kiosk_schedule as _authorize

    async with Session() as s:
        try:
            sched = await _authorize(s, schedule_id, teacher.id)
        except _HTTPException as e:
            await ws.send_json({"error": e.detail})
            await ws.close()
            return
        class_id = sched.class_id
        gallery = await public.load_gallery(s, class_id, ttl_s=cfg.gallery_cache_ttl_s)
    if len(gallery) == 0:
        await ws.send_json({"error": "Lớp chưa có dữ liệu khuôn mặt", "gallery_size": 0})
        await ws.close()
        return

    sess = public.get_session(schedule_id, cfg)
    by_id = {e.student_id: e for e in gallery.entries}
    latest: asyncio.Queue = asyncio.Queue(maxsize=1)
    dropped = 0
    stop = asyncio.Event()
    hook = public.uniform_hook_factory()
    async with Session() as _s0:
        try:
            min_gap = await load_min_checkout_gap(_s0)  # cache 30s ở repo
        except Exception:
            min_gap = svc.MIN_CHECKOUT_GAP_MINUTES

    async def recv() -> None:
        nonlocal dropped
        while not stop.is_set():
            try:
                raw = await ws.receive_bytes()
            except WebSocketDisconnect:
                stop.set()
                break
            except Exception:
                continue
            if latest.full():
                try:
                    latest.get_nowait()
                    dropped += 1
                except asyncio.QueueEmpty:
                    pass
            try:
                latest.put_nowait(raw)
            except asyncio.QueueFull:
                dropped += 1

    async def infer() -> None:
        while not stop.is_set():
            try:
                raw = await asyncio.wait_for(latest.get(), timeout=10.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                img = await asyncio.to_thread(public.decode_frame, raw, int(cfg.kiosk_max_width))
            except public.ImageDecodeError:
                continue
            except Exception:
                continue
            t0 = time.perf_counter()
            try:
                decisions = await asyncio.to_thread(sess.process, img, gallery, None, None, hook)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"kiosk ws infer lỗi: {e}")
                continue
            infer_ms = (time.perf_counter() - t0) * 1000.0
            faces = []
            try:
                async with Session() as s:
                    checked = await record_checkin(
                        s,
                        schedule_id,
                        teacher.id,
                        decisions,
                        frame_bgr=img,
                        min_gap_minutes=min_gap,
                    )
                    for d in decisions:
                        entry = by_id.get(d.student_id) if d.student_id else None
                        faces.append({
                            "track_id": d.track_id,
                            "bbox": [round(float(v), 1) for v in d.bbox],
                            "student_id": d.student_id,
                            "user_code": entry.user_code if entry else None,
                            "full_name": entry.full_name if entry else None,
                            "score": round(d.score, 3),
                            "liveness": round(d.liveness, 3),
                            "decision": public.to_legacy(d.decision),
                            "votes": d.votes,
                        })
            except Exception as e:  # noqa: BLE001
                logger.debug(f"kiosk ws db lỗi: {e}")
                checked = {"checked_in": [], "checked_out": [], "already_done": []}
            base = int(cfg.kiosk_interval_ms)
            nxt, w = adaptive_feedback(base, int(cfg.kiosk_max_width), infer_ms)
            try:
                await ws.send_json({"faces": faces, "checked_in": checked.get("checked_in", []),
                                    "checked_out": checked.get("checked_out", []),
                                    "already_done": checked.get("already_done", []),
                                    "infer_ms": round(infer_ms, 1),
                                    "next_interval_ms": nxt, "next_width": w,
                                    "dropped": dropped,
                                    "gallery_size": len(gallery)})
            except Exception:
                stop.set()
                break

    recv_t = asyncio.create_task(recv())
    infer_t = asyncio.create_task(infer())
    _, pending = await asyncio.wait({recv_t, infer_t}, return_when=asyncio.FIRST_COMPLETED)
    stop.set()
    for t in pending:
        t.cancel()
    for t in (recv_t, infer_t):
        try:
            if not t.cancelled():
                exc = t.exception()
                if exc is not None and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                    logger.debug(f"ws stop: {exc}")
        except Exception:
            pass
