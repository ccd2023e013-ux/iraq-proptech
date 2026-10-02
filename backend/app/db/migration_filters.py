"""Filters shared by Alembic's env.py and the migration drift test.

Objects owned by PostGIS, extensions, or a hosting provider (e.g. Supabase's
``auth``/``storage`` schemas) are never managed by our migrations.
"""

from __future__ import annotations

from typing import Any

EXTERNAL_TABLES = frozenset({"spatial_ref_sys", "geography_columns", "geometry_columns"})
EXTERNAL_SCHEMAS = frozenset(
    {"tiger", "tiger_data", "topology", "extensions", "auth", "storage", "realtime", "vault"}
)


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    if type_ == "table":
        if name in EXTERNAL_TABLES:
            return False
        if getattr(obj, "schema", None) in EXTERNAL_SCHEMAS:
            return False
    return True
