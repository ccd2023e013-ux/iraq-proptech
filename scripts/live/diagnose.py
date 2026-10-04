"""Diagnose live configuration problems without printing secrets.

Run inside the backend image with the same variables Render has (whatever is
available as GitHub secrets). Reports: which variables are set (never their
values), whether DEMO_ACCOUNT_PASSWORD passes the password policy, whether the
S3 bucket accepts a write/read/delete, and what the database contains.
"""

from __future__ import annotations

import os
import uuid

checks: list[str] = []


def note(line: str) -> None:
    print(line, flush=True)
    checks.append(line)


for key in (
    "DATABASE_URL",
    "DEMO_ACCOUNT_PASSWORD",
    "S3_ENDPOINT_URL",
    "S3_REGION",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
):
    note(f"{key}: {'set' if os.environ.get(key) else 'NOT SET'}")

password = os.environ.get("DEMO_ACCOUNT_PASSWORD")
if password:
    from app.users.validation import password_problems

    problems = password_problems(password)
    note(
        f"DEMO_ACCOUNT_PASSWORD policy: {'OK' if not problems else ', '.join(problems)} "
        f"(length {len(password)})"
    )

if os.environ.get("S3_ACCESS_KEY_ID") and os.environ.get("S3_ENDPOINT_URL"):
    os.environ.setdefault("STORAGE_BACKEND", "s3")
    os.environ.setdefault("S3_BUCKET", "media")
    try:
        from app.storage import get_storage

        storage = get_storage()
        key = f"diagnostics/{uuid.uuid4()}.txt"
        storage.put(key, b"probe", "text/plain")
        ok = storage.get(key) == b"probe"
        storage.delete(key)
        note(
            f"S3 write/read/delete on bucket '{os.environ['S3_BUCKET']}': "
            f"{'OK' if ok else 'MISMATCH'}"
        )
    except Exception as exc:  # report the class and message, never credentials
        note(f"S3 round trip FAILED: {type(exc).__name__}: {str(exc)[:300]}")

if os.environ.get("DATABASE_URL"):
    from sqlalchemy import text

    from app.db.session import get_engine

    with get_engine().connect() as db:
        counts = {
            t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()  # noqa: S608
            for t in (
                "users",
                "properties",
                "property_media",
                "agencies",
                "districts",
                "audit_logs",
            )
        }
        seeded = db.execute(
            text(
                "SELECT occurred_at, data FROM audit_logs WHERE action LIKE 'demo.%' "
                "ORDER BY occurred_at DESC LIMIT 3"
            )
        ).all()
    note(f"database counts: {counts}")
    note(f"demo seed audit events: {[(str(r[0]), r[1]) for r in seeded]}")

print("::notice title=live diagnose summary::" + " | ".join(checks).replace("\n", " "))
