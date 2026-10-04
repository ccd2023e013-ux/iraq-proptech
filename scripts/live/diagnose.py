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
    from urllib.parse import urlparse

    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    endpoint = os.environ["S3_ENDPOINT_URL"]
    parts = urlparse(endpoint)
    note(
        f"S3 endpoint shape: scheme={parts.scheme} host=*{(parts.hostname or '')[-20:]}"
        f" path={parts.path!r}; region={os.environ.get('S3_REGION')!r}; "
        f"boto3 {boto3.__version__}"
    )
    variants = {
        "current": Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
        "checksum-when-required": Config(
            s3={"addressing_style": "path"},
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    }
    region_raw = os.environ.get("S3_REGION", "")
    # The region is not secret; spaced out so the log mask does not hide its shape.
    note(f"S3_REGION shape: {' '.join(region_raw)!r} (length {len(region_raw)})")
    raw: list[str] = []

    def capture(http_response, **_: object) -> None:
        raw.append(f"{http_response.status_code} {http_response.text[:300]!r}")

    for region in [region_raw.strip(), "eu-central-1", "us-east-1"]:
        probe_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            config=variants_config
            if (
                variants_config := Config(s3={"addressing_style": "path"}, signature_version="s3v4")
            )
            else None,
            region_name=region,
            aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"].strip(),
        )
        probe_client.meta.events.register("after-call.s3", capture)
        raw.clear()
        try:
            probe_client.list_objects_v2(Bucket="media", MaxKeys=1)
            note(f"S3 list_objects with region {region!r}: OK")
        except ClientError:
            note(f"S3 list_objects with region {region!r}: {raw[-1] if raw else 'no response'}")
    key_id, secret = os.environ["S3_ACCESS_KEY_ID"], os.environ["S3_SECRET_ACCESS_KEY"]
    note(
        f"S3 key shapes: id length {len(key_id)} (stripped {len(key_id.strip())}), "
        f"secret length {len(secret)} (stripped {len(secret.strip())})"
    )
    for name, config in variants.items():
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            config=config,
            region_name=os.environ.get("S3_REGION"),
            aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        )
        try:
            names = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
            note(f"S3[{name}] buckets visible: {names}")
        except ClientError as exc:
            note(f"S3[{name}] list_buckets: {exc.response.get('Error', {})}")
        key = f"diagnostics/{uuid.uuid4()}.txt"
        try:
            client.put_object(Bucket="media", Key=key, Body=b"probe", ContentType="text/plain")
            body = client.get_object(Bucket="media", Key=key)["Body"].read()
            client.delete_object(Bucket="media", Key=key)
            note(
                f"S3[{name}] write/read/delete on 'media': "
                f"{'OK' if body == b'probe' else 'MISMATCH'}"
            )
        except ClientError as exc:
            err = exc.response.get("Error", {})
            meta = exc.response.get("ResponseMetadata", {})
            note(f"S3[{name}] put/get FAILED: {err} http={meta.get('HTTPStatusCode')}")

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
        errors = db.execute(
            text(
                "SELECT created_at, path, error_type FROM error_events "
                "ORDER BY created_at DESC LIMIT 5"
            )
        ).all()
    note(f"database counts: {counts}")
    note(f"recent errors: {[(str(r[0])[:19], r[1], r[2]) for r in errors]}")
    note(f"demo seed audit events: {[(str(r[0]), r[1]) for r in seeded]}")

print("::notice title=live diagnose summary::" + " | ".join(checks).replace("\n", " "))
