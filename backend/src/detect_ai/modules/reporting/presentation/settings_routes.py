from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.system_setting import SystemSetting
from detect_ai.modules.identity.public import require_role

router = APIRouter(dependencies=[Depends(require_role("ADMIN"))])

# Ngưỡng phần trăm cấm thi/cảnh báo: giá trị phải là số trong 0–100.
# API từ chối rác ngay (422) thay vì ghi DB rồi công thức fallback lặng lẽ.
PERCENT_SETTING_KEYS = frozenset({
    "MAX_ABSENCE_PERCENT_EXAM_BAN",
    "WARNING_ABSENCE_PERCENT",
})

# Công tắc mail: chỉ nhận true/false.
BOOL_SETTING_KEYS = frozenset({
    "EMAIL_ENABLED",
    "EMAIL_REMINDER_ENABLED",
    "EMAIL_WARNING_ENABLED",
    "EMAIL_BAN_ENABLED",
    "SMTP_ENABLED",
    "SMTP_USE_TLS",
})

# Port/timeout SMTP: số nguyên dương.
INT_SETTING_KEYS = frozenset({
    "SMTP_PORT",
    "SMTP_TIMEOUT_S",
})

# Chuỗi SMTP tự do (host/user/password/from): chỉ giới hạn độ dài cột DB.
TEXT_SETTING_KEYS = frozenset({
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
})


def _validate_setting_value(key: str, value: Any) -> str:
    val_str = str(value)
    if key in PERCENT_SETTING_KEYS:
        try:
            num = float(val_str)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Giá trị của {key} phải là số trong khoảng 0–100.",
            )
        if not (0 <= num <= 100):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Giá trị của {key} phải là số trong khoảng 0–100.",
            )
    elif key in BOOL_SETTING_KEYS:
        if val_str.strip().lower() not in ("true", "false", "1", "0"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Giá trị của {key} phải là true/false.",
            )
    elif key in INT_SETTING_KEYS:
        try:
            num = int(val_str.strip())
        except (TypeError, ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Giá trị của {key} phải là số nguyên dương.",
            )
        if not (1 <= num <= 65535):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Giá trị của {key} phải là số nguyên dương.",
            )
    elif key in TEXT_SETTING_KEYS:
        if len(val_str) > 255:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Giá trị của {key} tối đa 255 ký tự.",
            )
    return val_str


class SettingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str
    description: Optional[str] = None


class SystemSettingsResponse(BaseModel):
    settings: Dict[str, str]
    items: List[SettingItem]
    has_smtp_password: bool = False


SECRET_SETTING_KEYS = frozenset({
    "SMTP_PASSWORD",
})


def _mask_value(key: str, value: str) -> str:
    return "" if key in SECRET_SETTING_KEYS and value else value


@router.get("", response_model=SystemSettingsResponse)
async def get_settings(
    s: AsyncSession = Depends(get_db),
):
    result = await s.execute(select(SystemSetting).order_by(SystemSetting.key))
    rows = result.scalars().all()

    settings_dict = {row.key: _mask_value(row.key, row.value) for row in rows}
    items = [
        SettingItem(
            id=row.id,
            key=row.key,
            value=_mask_value(row.key, row.value),
            description=row.description,
        )
        for row in rows
    ]

    return SystemSettingsResponse(
        settings=settings_dict, items=items,
        has_smtp_password=any(r.key == "SMTP_PASSWORD" and r.value for r in rows),
    )


@router.put("", response_model=SystemSettingsResponse)
async def update_settings(
    body: Dict[str, Any],
    s: AsyncSession = Depends(get_db),
):
    # Fetch existing settings into a dictionary
    result = await s.execute(select(SystemSetting))
    existing_map = {row.key: row for row in result.scalars().all()}

    # If body has a nested "settings" key, unpack it, otherwise use body directly
    settings_to_update = body.get("settings", body) if isinstance(body.get("settings"), dict) else body

    for k, v in settings_to_update.items():
        val_str = _validate_setting_value(k, v)
        # Secret rỗng = giữ nguyên giá trị cũ (tránh UI ghi đè khi để trống).
        if k in SECRET_SETTING_KEYS and not val_str and k in existing_map:
            continue
        if k in existing_map:
            existing_map[k].value = val_str
        else:
            new_setting = SystemSetting(key=k, value=val_str)
            s.add(new_setting)

    await s.commit()

    # Re-fetch all settings
    result_fresh = await s.execute(select(SystemSetting).order_by(SystemSetting.key))
    fresh_rows = result_fresh.scalars().all()

    settings_dict = {row.key: _mask_value(row.key, row.value) for row in fresh_rows}
    items = [
        SettingItem(
            id=row.id,
            key=row.key,
            value=_mask_value(row.key, row.value),
            description=row.description,
        )
        for row in fresh_rows
    ]
    has_pw = any(r.key == "SMTP_PASSWORD" and r.value for r in fresh_rows)
    return SystemSettingsResponse(settings=settings_dict, items=items, has_smtp_password=has_pw)
