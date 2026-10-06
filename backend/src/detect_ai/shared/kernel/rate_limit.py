"""Rate-limit in-memory cho login + WS (không thêm dependency).

Chính sách (config trong core/config.py):
- Login: mỗi tài khoản 10 lần sai/phút + mỗi IP 60 lần sai/phút.
  Chỉ lần SAI mới bị đếm — login thành công không tốn quota nên không khóa
  nhầm cả trường giờ cao điểm (một IP NAT có hàng chục SV login cùng lúc).
- WS kiosk connect: mỗi IP 20 lần/phút (mỗi connect giữ socket + đốt CPU
  infer nên đếm ngay ở cổng).

ponytail: multi-worker/restart mất bộ đếm (RAM-local). Khi scale >1 worker
hoặc cần chặn bền -> thay bằng Redis fixed-window, giữ nguyên API 3 hàm này.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, status

from .config import S

_hits: dict[str, deque[float]] = {}
_lock = Lock()

# Chặn key phình vô hạn: account_key/IP đều từ input user (username random,
# X-Forwarded-For giả). Quá ngưỡng thì quét key hết hạn, vẫn đầy thì thôi
# không ghi mới (fail-open phần đếm, không fail-open auth).
_MAX_KEYS = 10000


def _sweep(now: float, window_s: float = 60.0) -> None:
    """Xóa key đã hết hạn. Chỉ gọi khi dict quá lớn (hiếm)."""
    cutoff = now - window_s
    dead = [k for k, dq in _hits.items() if not dq or dq[-1] <= cutoff]
    for k in dead:
        _hits.pop(k, None)


def _prune(key: str, now: float, window_s: float = 60.0, create: bool = True) -> deque[float]:
    dq = _hits.get(key)
    if dq is None:
        if not create:
            return deque()  # đọc free: không tạo key rác cho username lạ
        if len(_hits) >= _MAX_KEYS:
            _sweep(now, window_s)
            if len(_hits) >= _MAX_KEYS:
                return deque()  # đầy: trả deque rời, không ghi vào dict
        dq = deque()
        _hits[key] = dq
        return dq
    cutoff = now - window_s
    while dq and dq[0] <= cutoff:
        dq.popleft()
    if not dq:
        # Key hết hạn được dọn ngay để dict không giữ key chết.
        _hits.pop(key, None)
        fresh: deque[float] = deque()
        _hits[key] = fresh
        return fresh
    return dq


def _client_ip(request: Request | None) -> str:
    """IP client sau proxy.

    Chỉ tin X-Forwarded-For khi S.trust_proxy bật (deploy sau nginx/traefik
    có strip header từ ngoài). Mặc định đọc socket IP — sau proxy không bật
    trust_proxy thì mọi user chung 1 IP (chặn nhầm), chứ không bypass được.
    """
    try:
        if request is not None:
            if S.trust_proxy:
                xff = request.headers.get("x-forwarded-for", "")
                if xff:
                    first = xff.split(",")[0].strip()
                    if first:
                        return first[:64]
            if request.client is not None:
                return request.client.host or "unknown"
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def _check_only(key: str, limit: int, window_s: float = 60.0) -> bool:
    """True khi đã hết quota (không tiêu thụ, không tạo key mới)."""
    now = time.monotonic()
    with _lock:
        return len(_prune(key, now, window_s, create=False)) >= limit


def _consume(key: str, limit: int, window_s: float = 60.0) -> bool:
    """True khi hết quota; còn quota thì trừ 1 (check-then-consume 1 lần)."""
    now = time.monotonic()
    with _lock:
        dq = _prune(key, now, window_s)
        if len(dq) >= limit:
            return True
        dq.append(now)
        return False


def check_login_allowed(request: Request | None, account_key: str) -> None:
    """Raise 429 khi tài khoản hoặc IP đã sai quá nhiều lần trong phút qua.

    CHỈ đọc quota, không tiêu thụ (đọc free): brute-force tài khoản không
    tồn tại bị chặn bằng IP-bucket; tài khoản thật bị chặn bằng acct-bucket
    sau N lần SAI (record_login_attempt). Login đúng + login sai ít không
    bao giờ dính 429, kể cả cả trường chung 1 IP.
    """
    if _check_only(f"login:acct:{account_key}", S.login_rate_limit_per_account_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Đăng nhập sai quá nhiều lần. Thử lại sau 1 phút.",
        )
    if _check_only(f"login:ip:{_client_ip(request)}", S.login_rate_limit_per_ip_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều lượt đăng nhập từ mạng này. Thử lại sau 1 phút.",
        )


def record_login_attempt(request: Request | None, account_key: str) -> None:
    """Ghi 1 lần SAI: cổng đọc free, fail password tiêu thụ tại đây.

    Chỉ gọi khi sai credential (không tồn tại / bị khóa / sai mật khẩu) —
    login thành công không tốn quota, cả trường chung 1 IP giờ cao điểm
    không tự khóa nhau.
    """
    now = time.monotonic()
    with _lock:
        _prune(f"login:acct:{account_key}", now).append(now)
        _prune(f"login:ip:{_client_ip(request)}", now).append(now)


def check_ws_allowed(request: Request | None, scope_client=None) -> None:
    """Raise 429 khi IP mở WS quá nhanh. Gọi TRƯỚC ws.accept()."""
    ip = "unknown"
    try:
        if scope_client:
            ip = scope_client[0] or "unknown"
        elif request is not None:
            ip = _client_ip(request)  # trust_proxy applies via _client_ip
    except Exception:  # noqa: BLE001
        pass
    if _consume(f"ws:ip:{ip}", S.ws_connects_per_ip_per_minute):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Mở kết nối quá nhanh. Thử lại sau 1 phút.",
        )


def reset_for_tests() -> None:
    """Xóa bộ đếm (chỉ dùng trong test)."""
    with _lock:
        _hits.clear()
