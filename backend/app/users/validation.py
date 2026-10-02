"""Input normalization and policy for account data."""

from __future__ import annotations

import re

_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Iraqi mobile numbers: 07[3-9]X XXX XXXX → +9647[3-9]XXXXXXXX
_IRAQ_MOBILE = re.compile(r"^7[3-9]\d{8}$")

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
_COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "0123456789",
        "password123",
        "password1234",
        "qwertyuiop",
        "iloveyou123",
        "1q2w3e4r5t",
        "aaaaaaaaaa",
        "basra12345",
        "baghdad123",
        "iraq123456",
    }
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_iraqi_phone(raw: str) -> str:
    """Return an Iraqi mobile number in E.164 form or raise ``ValueError``.

    Accepts local (07xx…), national (7xx…), and international (+964 / 00964)
    formats, with spaces, dashes and Arabic-Indic digits.
    """
    digits = re.sub(r"[\s\-().]", "", raw.translate(_ARABIC_INDIC))
    if digits.startswith("+964"):
        digits = digits[4:]
    elif digits.startswith("00964"):
        digits = digits[5:]
    elif digits.startswith("964") and len(digits) == 13:
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not _IRAQ_MOBILE.match(digits):
        raise ValueError("Invalid Iraqi mobile number")
    return "+964" + digits


def password_problems(password: str, *, email: str | None = None) -> list[str]:
    """Return a list of stable problem codes (empty means acceptable)."""
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append("PASSWORD_TOO_SHORT")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append("PASSWORD_TOO_LONG")
    if password.lower() in _COMMON_PASSWORDS or len(set(password)) < 4:
        problems.append("PASSWORD_TOO_COMMON")
    local_part = normalize_email(email).split("@")[0] if email else ""
    if len(local_part) >= 3 and local_part in password.lower():
        problems.append("PASSWORD_CONTAINS_EMAIL")
    return problems
