from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, Mapping, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.shared.kernel import config as C

@dataclass
class SmtpConfig:
    enabled: bool = False
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    from_addr: str = ""
    use_tls: bool = True
    timeout_s: int = 10

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.host and self.user and self.from_addr)


def _as_bool(raw: Any, default: bool) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in ("true", "1", "yes", "t")


def _as_int(raw: Any, default: int) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def config_from_map(m: Mapping[str, Any]) -> SmtpConfig:
    """Dựng config từ map system_settings (key SMTP_*)."""
    s = C.S
    return SmtpConfig(
        enabled=_as_bool(m.get("SMTP_ENABLED"), bool(s.smtp_enabled)),
        host=str(m.get("SMTP_HOST", s.smtp_host) or "").strip(),
        port=_as_int(m.get("SMTP_PORT"), int(s.smtp_port)),
        user=str(m.get("SMTP_USER", s.smtp_user) or "").strip(),
        password=str(m.get("SMTP_PASSWORD", s.smtp_password) or ""),
        from_addr=str(m.get("SMTP_FROM", s.smtp_from) or "").strip(),
        use_tls=_as_bool(m.get("SMTP_USE_TLS"), bool(s.smtp_use_tls)),
        timeout_s=_as_int(m.get("SMTP_TIMEOUT_S"), int(s.smtp_timeout_s)),
    )


async def load_smtp_config(session: AsyncSession) -> SmtpConfig:
    """Đọc SMTP từ DB (1 query); env chỉ fallback khi DB chưa có key."""
    from detect_ai.shared.kernel.settings import load_settings_map

    m = await load_settings_map(session)
    return config_from_map(m)


def smtp_configured() -> bool:
    """Giữ API cũ: check nhanh env (dùng cho log/tests không có session)."""
    s = C.S
    return bool(s.smtp_enabled and s.smtp_host and s.smtp_user and s.smtp_from)


def _build_message(to: str, subject: str, html: str, text: str, from_addr: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr or C.S.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text or "Xem nội dung trong bản HTML.")
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _send_sync(msg: EmailMessage, cfg: SmtpConfig) -> None:
    if cfg.use_tls:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout_s) as c:
            c.starttls()
            c.login(cfg.user, cfg.password)
            c.send_message(msg)
    else:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout_s) as c:
            if cfg.user:
                c.login(cfg.user, cfg.password)
            c.send_message(msg)


async def send(
    to: str,
    subject: str,
    html: str,
    text: str = "",
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Gửi 1 mail. Có session -> đọc SMTP từ DB; không session -> env cũ. Thiếu config -> log-only, không raise."""
    to = (to or "").strip()
    if "@" not in to:
        return {"ok": False, "skipped": True, "error": "invalid_email"}
    cfg: Optional[SmtpConfig] = None
    if session is not None:
        try:
            cfg = await load_smtp_config(session)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[mail config] không đọc được DB ({e}), fallback env")
    if cfg is None:
        s = C.S
        cfg = SmtpConfig(
            enabled=bool(s.smtp_enabled),
            host=s.smtp_host,
            port=int(s.smtp_port),
            user=s.smtp_user,
            password=s.smtp_password,
            from_addr=s.smtp_from,
            use_tls=bool(s.smtp_use_tls),
            timeout_s=int(s.smtp_timeout_s),
        )
    if not cfg.configured:
        logger.info(f"[mail log-only] to={to} subject={subject}")
        return {"ok": True, "skipped": True, "mode": "log-only"}
    try:
        msg = _build_message(to, subject, html, text, cfg.from_addr)
        await asyncio.to_thread(_send_sync, msg, cfg)
        # ponytail: sleep chống rate-limit ở service batch, không ở đây.
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[mail failed] to={to} err={e}")
        return {"ok": False, "error": str(e)[:300]}
