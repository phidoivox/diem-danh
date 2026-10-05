from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_db
from detect_ai.shared.kernel.system_setting import SystemSetting
from .deps_auth import require_role

router = APIRouter(dependencies=[Depends(require_role("ADMIN"))])


class SettingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str
    description: Optional[str] = None


class SystemSettingsResponse(BaseModel):
    settings: Dict[str, str]
    items: List[SettingItem]


@router.get("", response_model=SystemSettingsResponse)
async def get_settings(
    s: AsyncSession = Depends(get_db),
):
    result = await s.execute(select(SystemSetting).order_by(SystemSetting.key))
    rows = result.scalars().all()

    settings_dict = {row.key: row.value for row in rows}
    items = [
        SettingItem(
            id=row.id,
            key=row.key,
            value=row.value,
            description=row.description,
        )
        for row in rows
    ]

    return SystemSettingsResponse(settings=settings_dict, items=items)


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
        val_str = str(v)
        if k in existing_map:
            existing_map[k].value = val_str
        else:
            new_setting = SystemSetting(key=k, value=val_str)
            s.add(new_setting)

    await s.commit()

    # Re-fetch all settings
    result_fresh = await s.execute(select(SystemSetting).order_by(SystemSetting.key))
    fresh_rows = result_fresh.scalars().all()

    settings_dict = {row.key: row.value for row in fresh_rows}
    items = [
        SettingItem(
            id=row.id,
            key=row.key,
            value=row.value,
            description=row.description,
        )
        for row in fresh_rows
    ]

    return SystemSettingsResponse(settings=settings_dict, items=items)
