"""Admin-editable runtime settings (a typed whitelist over ``system_settings``).

Only keys declared here can be read or written; values are validated. Secrets
never live here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.system.models import SystemSetting


@dataclass(frozen=True)
class SettingSpec:
    default: Any
    description: str
    validate: Callable[[Any], Any]
    public: bool = False


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("must be true or false")
    return value


def _int_range(lo: int, hi: int) -> Callable[[Any], int]:
    def check(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(f"must be an integer between {lo} and {hi}")
        return value

    return check


def _text(max_len: int) -> Callable[[Any], str]:
    def check(value: Any) -> str:
        if not isinstance(value, str) or len(value) > max_len:
            raise ValueError(f"must be text of at most {max_len} characters")
        return value.strip()

    return check


SETTINGS: dict[str, SettingSpec] = {
    "listings.lifetime_days": SettingSpec(
        90, "Days an approved listing stays published before it expires", _int_range(7, 365)
    ),
    "listings.auto_approve_verified_agencies": SettingSpec(
        False, "Publish listings from verified agencies without manual review", _bool
    ),
    "inquiries.daily_limit_per_user": SettingSpec(
        10, "Inquiries one account may send per hour", _int_range(1, 200)
    ),
    "site.announcement_ar": SettingSpec(
        "", "Banner text shown to all visitors (Arabic)", _text(300), public=True
    ),
    "site.announcement_en": SettingSpec(
        "", "Banner text shown to all visitors (English)", _text(300), public=True
    ),
}


def get_setting(db: Session, key: str) -> Any:
    spec = SETTINGS[key]
    row = db.get(SystemSetting, key)
    return spec.default if row is None else row.value


def all_settings(db: Session, *, public_only: bool = False) -> dict[str, Any]:
    stored = {r.key: r.value for r in db.execute(select(SystemSetting)).scalars()}
    return {
        key: stored.get(key, spec.default)
        for key, spec in SETTINGS.items()
        if spec.public or not public_only
    }


def set_setting(db: Session, key: str, value: Any) -> Any:
    spec = SETTINGS.get(key)
    if spec is None:
        raise AppError("Unknown setting", code="UNKNOWN_SETTING", status_code=404)
    try:
        clean = spec.validate(value)
    except ValueError as exc:
        raise AppError(str(exc), code="VALIDATION_ERROR", status_code=422) from exc
    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=clean, description=spec.description))
    else:
        row.value = clean
    return clean
