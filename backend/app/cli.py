"""Operational commands.

    python -m app.cli create-superadmin --email admin@example.com --name "Admin"
        (password from SUPERADMIN_PASSWORD or an interactive prompt)

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sa = sub.add_parser("create-superadmin", help="Create or promote a SUPER_ADMIN")
    sa.add_argument("--email", required=True)
    sa.add_argument("--name", default="Super Admin")
    args = parser.parse_args(argv)

    if args.command == "create-superadmin":
        password = os.environ.get("SUPERADMIN_PASSWORD") or getpass.getpass("Password: ")
        user_id = create_superadmin(args.email, args.name, password)
        print(f"SUPER_ADMIN ready: {user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
