"""Read-only audit of the LIVE database (Supabase) — run inside the backend image.

    docker run --rm -e DATABASE_URL=... -v "$PWD/scripts/live:/live:ro" \\
      proptech-backend python /live/db_audit.py

Checks extensions, migration head, PostGIS geometry, schema integrity (tables,
foreign keys, indexes on every foreign key), and the DEMO dataset. It never
writes: the real database is only read. Prints GitHub notices with the numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.session import get_engine

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("  ✓ " if condition else "  ✗ ") + message)
    if not condition:
        FAILURES.append(message)


def main() -> int:
    backend = Path("/app")
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()

    with get_engine().connect() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        q = lambda sql, **kw: db.execute(text(sql), kw)  # noqa: E731

        ext = dict(q("SELECT extname, extversion FROM pg_extension").tuples().all())
        check("postgis" in ext, f"PostGIS installed ({ext.get('postgis')})")
        check("pg_trgm" in ext, f"pg_trgm installed ({ext.get('pg_trgm')})")
        version = q("SELECT version_num FROM alembic_version").scalar_one()
        check(version == head, f"migrations at head ({version} == {head})")
        server = q("SHOW server_version").scalar_one()

        tables = q(
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename NOT IN ('spatial_ref_sys')"
        ).scalar_one()
        check(tables >= 50, f"{tables} application tables")
        fks = q(
            "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE c.contype = 'f' AND n.nspname = 'public'"
        ).scalar_one()
        unindexed = q(
            """
            SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE c.contype = 'f' AND n.nspname = 'public' AND NOT EXISTS (
              SELECT 1 FROM pg_index i WHERE i.indrelid = c.conrelid
                AND (SELECT array_agg(x ORDER BY x)
                     FROM unnest((i.indkey::int2[])[0:cardinality(c.conkey) - 1]) x)
                  = (SELECT array_agg(y ORDER BY y) FROM unnest(c.conkey) y))
            """
        ).scalar_one()
        check(fks > 50 and unindexed == 0, f"{fks} foreign keys, {unindexed} without an index")
        invalid = q(
            "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND NOT i.indisvalid"
        ).scalar_one()
        check(invalid == 0, f"{invalid} invalid indexes")
        not_validated = q(
            "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE n.nspname = 'public' AND NOT c.convalidated"
        ).scalar_one()
        check(not_validated == 0, f"{not_validated} unvalidated constraints")

        meters = q(
            "SELECT ST_Distance(ST_SetSRID(ST_MakePoint(47.7804, 30.5085), 4326)::geography, "
            "ST_SetSRID(ST_MakePoint(47.8100, 30.5150), 4326)::geography)"
        ).scalar_one()
        check(2000 < meters < 3500, f"PostGIS geography distance in Basra: {meters:.0f} m")
        normalized = q("SELECT normalize_ar('بيت للبيع فى البصره')").scalar_one()
        check(bool(normalized), f"Arabic normalization function: {normalized}")

        per_city = (
            q(
                """
            SELECT c.slug, count(*) FILTER (WHERE p.is_demo), count(*) FILTER (WHERE NOT p.is_demo),
                   count(DISTINCT m.property_id)
            FROM properties p JOIN cities c ON c.id = p.city_id
            LEFT JOIN property_media m ON m.property_id = p.id AND m.deleted_at IS NULL
            WHERE p.deleted_at IS NULL AND p.status = 'APPROVED'
            GROUP BY c.slug ORDER BY c.slug
            """
            )
            .tuples()
            .all()
        )
        demo_total = sum(r[1] for r in per_city)
        real_total = sum(r[2] for r in per_city)
        cities = {r[0] for r in per_city if r[1] > 0}
        wanted = {"basra", "baghdad", "najaf", "karbala", "erbil", "mosul", "sulaymaniyah"}
        check(wanted <= cities, f"demo listings in {len(cities & wanted)}/7 required cities")
        check(demo_total >= 100, f"{demo_total} approved DEMO listings ({real_total} non-demo)")
        lister_leak = q(
            """
            SELECT count(*) FROM properties p JOIN users u ON u.id = p.lister_id
            WHERE u.email LIKE 'demo%@example.com' AND NOT p.is_demo
              AND p.title_ar NOT LIKE '%فحص مباشر%'
            """
        ).scalar_one()
        check(lister_leak == 0, f"{lister_leak} listings by demo accounts not marked is_demo")
        unlabeled = q(
            "SELECT count(*) FROM properties WHERE is_demo AND title_ar NOT LIKE '%تجريبي%'"
        ).scalar_one()
        check(unlabeled == 0, f"{unlabeled} DEMO listings without 'تجريبي' in the title")
        without_image = q(
            """
            SELECT count(*) FROM properties p WHERE p.is_demo AND p.deleted_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM property_media m
                              WHERE m.property_id = p.id AND m.deleted_at IS NULL)
            """
        ).scalar_one()
        check(without_image == 0, f"{without_image} DEMO listings without an image")
        demo_areas = q(
            "SELECT count(*) FROM districts WHERE geometry_source LIKE 'DEMO%'"
        ).scalar_one()
        accounts = q(
            "SELECT count(*) FROM users WHERE email LIKE 'demo.%@example.com'"
        ).scalar_one()
        check(accounts == 5, f"{accounts}/5 demo accounts")
        users = q("SELECT count(*) FROM users").scalar_one()

    summary = (
        f"PostgreSQL {server}; PostGIS {ext.get('postgis')}; revision {version}; {tables} tables; "
        f"{fks} FKs ({unindexed} unindexed); demo listings {demo_total} in {len(cities)} cities; "
        f"demo areas {demo_areas}; users {users}; per city: "
        + ", ".join(f"{r[0]}={r[1]}" for r in per_city if r[1])
    )
    print(f"::notice title=live database summary::{summary}")
    if FAILURES:
        print("DATABASE AUDIT FAILED: " + "; ".join(FAILURES))
        return 1
    print("DATABASE AUDIT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
