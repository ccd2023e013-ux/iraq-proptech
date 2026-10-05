"""Operational commands.

    python -m app.cli create-superadmin --email admin@example.com --name "Admin"
        (password from SUPERADMIN_PASSWORD or an interactive prompt)
    python -m app.cli seed-demo [--listings 40] [--allow-production]
    python -m app.cli reset-demo
    python -m app.cli run-jobs [name ...]   (default: every scheduled job once)
    python -m app.cli storage-export DIR   (configured storage → local directory)
    python -m app.cli storage-import DIR   (local directory → configured storage)
    python -m app.cli preflight [--db]
        (configuration checks; exit 1 on errors in production — run before start)

SUPER_ADMIN can only be created here — never through the API — so a
compromised admin account cannot mint new super admins.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.audit import service as audit
from app.auth.security import hash_password
from app.auth.service import ensure_password_acceptable
from app.db.session import get_sessionmaker
from app.rbac.catalog import Role
from app.users.models import User, UserRole, UserStatus
from app.users.validation import normalize_email


def create_superadmin(email: str, name: str, password: str) -> str:
    email = normalize_email(email)
    ensure_password_acceptable(password, email)
    with get_sessionmaker()() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                full_name=name,
                password_hash=hash_password(password),
                preferred_locale="ar",
                status=UserStatus.ACTIVE,
                email_verified_at=datetime.now(UTC),
                password_changed_at=datetime.now(UTC),
            )
            user.role_links.append(UserRole(role_code=Role.CUSTOMER))
            db.add(user)
            db.flush()
        if Role.SUPER_ADMIN not in user.roles:
            user.role_links.append(UserRole(role_code=Role.SUPER_ADMIN))
        audit.record(
            db,
            "user.superadmin_created_cli",
            actor_id=None,
            resource_type="user",
            resource_id=user.id,
        )
        db.commit()
        return str(user.id)


def _record_cli_error(command: str, exc: Exception) -> None:
    from app.moderation.models import ErrorEvent

    summary = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
    try:
        with get_sessionmaker()() as db:
            db.add(ErrorEvent(path=f"cli:{command}", method="CLI", error_type=summary[:120]))
            db.commit()
    except Exception as db_exc:  # the database itself may be the problem
        print(f"could not record the error: {type(db_exc).__name__}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sa = sub.add_parser("create-superadmin", help="Create or promote a SUPER_ADMIN")
    sa.add_argument("--email", required=True)
    sa.add_argument("--name", default="Super Admin")
    demo = sub.add_parser("seed-demo", help="Create clearly-labelled DEMO districts and listings")
    demo.add_argument("--listings", type=int, default=40)
    demo.add_argument("--allow-production", action="store_true")
    sub.add_parser("reset-demo", help="Delete DEMO listings created by seed-demo")
    iraq = sub.add_parser(
        "seed-demo-iraq",
        help="National DEMO dataset (7 cities, generated images, demo accounts if "
        "DEMO_ACCOUNT_PASSWORD is set)",
    )
    iraq.add_argument("--per-city", type=int, default=18)
    iraq.add_argument("--no-images", action="store_true")
    iraq.add_argument("--allow-production", action="store_true")
    osm_cmd = sub.add_parser(
        "import-osm-pois",
        help="Import named places (schools, hospitals, mosques…) for a city from "
        "OpenStreetMap via one Overpass request (ODbL attribution kept)",
    )
    osm_cmd.add_argument("--city", default="basra")
    osm_cmd.add_argument("--bbox", help="west,south,east,north (city-sized, inside Iraq)")
    osm_cmd.add_argument("--dry-run", action="store_true")
    dev = sub.add_parser(
        "import-development",
        help="Load a curated, source-cited development dataset (idempotent)",
    )
    dev.add_argument("--dataset", default="basra")
    pf = sub.add_parser("preflight", help="Check configuration (and the database with --db)")
    pf.add_argument("--db", action="store_true", help="also check PostGIS and migrations")
    for name, text in (
        ("storage-export", "Copy every stored object from the configured storage to DIR"),
        ("storage-import", "Copy every object in DIR into the configured storage"),
    ):
        sp = sub.add_parser(name, help=text)
        sp.add_argument("directory")
    rj = sub.add_parser("run-jobs", help="Run maintenance jobs once (no worker needed)")
    rj.add_argument("names", nargs="*")
    args = parser.parse_args(argv)

    if args.command in ("storage-export", "storage-import"):
        from app.storage import LocalStorage, copy_all, get_storage

        configured, local = get_storage(), LocalStorage(args.directory)
        if args.command == "storage-export":
            print(copy_all(configured, local))
        else:
            print(copy_all(local, configured))
        return 0

    if args.command == "run-jobs":
        from app.workers import registry

        with get_sessionmaker()() as db:
            for result in registry.run(db, args.names or registry.FREQUENT):
                print(f"{result['job']}: {result['status']} {result['detail'] or result['error']}")
        return 0

    if args.command == "import-development":
        from app.development import service as development

        with get_sessionmaker()() as db:
            print(development.import_dataset(db, args.dataset))
        return 0

    if args.command == "import-osm-pois":
        from app.geo import osm

        bbox = None
        if args.bbox:
            w, s_, e, n = (float(v) for v in args.bbox.split(","))
            bbox = (w, s_, e, n)
        try:
            with get_sessionmaker()() as db:
                print(osm.import_places(db, city_slug=args.city, bbox=bbox, dry_run=args.dry_run))
        except Exception as exc:
            _record_cli_error("import-osm-pois", exc)
            raise
        return 0

    if args.command == "preflight":
        from app.core.config import get_settings
        from app.core.preflight import config_findings, database_findings

        settings = get_settings()
        findings = config_findings(settings) + (database_findings() if args.db else [])
        for f in findings:
            print(f"{f.level.upper():7} {f.code}: {f.message}")
        errors = [f for f in findings if f.level == "error"]
        print(f"preflight: {len(errors)} error(s), {len(findings) - len(errors)} warning(s)")
        return 1 if errors else 0

    if args.command in ("seed-demo", "reset-demo"):
        from app import demo as demo_data
        from app.core.config import get_settings

        if (
            args.command == "seed-demo"
            and get_settings().is_production
            and not args.allow_production
        ):
            print("Refusing to seed DEMO data in production without --allow-production")
            return 2
        with get_sessionmaker()() as db:
            if args.command == "seed-demo":
                result = demo_data.seed(db, listings=max(0, min(args.listings, 500)))
            else:
                result = demo_data.reset(db)
        print(result)
        return 0

    if args.command == "seed-demo-iraq":
        from app import demo_iraq
        from app.core.config import get_settings

        if get_settings().is_production and not args.allow_production:
            print("Refusing to seed DEMO data in production without --allow-production")
            return 2
        try:
            with get_sessionmaker()() as db:
                result = demo_iraq.seed(
                    db,
                    per_city=max(0, min(args.per_city, 200)),
                    account_password=os.environ.get("DEMO_ACCOUNT_PASSWORD") or None,
                    images=not args.no_images,
                )
        except Exception as exc:
            # Start-up seeding runs in the background where logs are easy to miss:
            # leave the failure in the admin error log (type + short message only).
            _record_cli_error("seed-demo-iraq", exc)
            raise
        print(result)
        return 0

    if args.command == "create-superadmin":
        password = os.environ.get("SUPERADMIN_PASSWORD") or getpass.getpass("Password: ")
        user_id = create_superadmin(args.email, args.name, password)
        print(f"SUPER_ADMIN ready: {user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
