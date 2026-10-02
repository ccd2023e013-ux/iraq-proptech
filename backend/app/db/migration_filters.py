"""Filters shared by Alembic's env.py and the migration drift test.

Our migrations manage only our own tables. Anything created by an extension
(PostGIS, the tiger geocoder that the postgis Docker image installs, topology,
...) or by a hosting provider (e.g. Supabase's ``auth``/``storage`` schemas) is
never compared or dropped.

Extension-owned tables are discovered from the catalog (``pg_depend`` with
``deptype = 'e'``) instead of a hard-coded list, so this stays correct on any
PostgreSQL host regardless of which extensions it ships.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection, text

EXTERNAL_TABLES = frozenset({"spatial_ref_sys", "geography_columns", "geometry_columns"})
EXTERNAL_SCHEMAS = frozenset(
    {"tiger", "tiger_data", "topology", "extensions", "auth", "storage", "realtime", "vault"}
)

_EXTENSION_TABLES_SQL = text(
    """
    SELECT c.relname
    FROM pg_depend d
    JOIN pg_class c ON c.oid = d.objid AND d.classid = 'pg_class'::regclass
    WHERE d.deptype = 'e' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    """
)

IncludeObject = Callable[[Any, str | None, str, bool, Any], bool]


def extension_owned_tables(connection: Connection) -> frozenset[str]:
    return frozenset(connection.execute(_EXTENSION_TABLES_SQL).scalars())


def make_include_object(connection: Connection) -> IncludeObject:
    excluded = EXTERNAL_TABLES | extension_owned_tables(connection)

    def include_object(
        obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
    ) -> bool:
        if type_ == "table":
            return name not in excluded and getattr(obj, "schema", None) not in EXTERNAL_SCHEMAS
        table = getattr(obj, "table", None)
        if table is not None:  # indexes, constraints, columns of an excluded table
            return table.name not in excluded and table.schema not in EXTERNAL_SCHEMAS
        return True

    return include_object


def compare_type(
    context: Any,
    inspected_column: Any,
    metadata_column: Any,
    inspected_type: Any,
    metadata_type: Any,
) -> bool | None:
    """PostGIS-aware type comparison (``None`` = use Alembic's default).

    Geometry columns are equal when geometry type and SRID match; Alembic's
    generic comparison would otherwise report spurious differences.
    """
    from geoalchemy2 import Geometry
    from sqlalchemy.types import NullType

    if isinstance(metadata_type, Geometry):
        if isinstance(inspected_type, NullType):
            return False  # reflection without PostGIS type info: nothing to compare
        if isinstance(inspected_type, Geometry):
            same_kind = (inspected_type.geometry_type or "").upper() == (
                metadata_type.geometry_type or ""
            ).upper()
            return not (same_kind and inspected_type.srid == metadata_type.srid)
    return None
