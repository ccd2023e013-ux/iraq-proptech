"""Schema audit: every foreign key is backed by an index.

An unindexed foreign key makes joins/filters on it sequential scans and makes
``ON DELETE`` on the parent scan the whole child table under lock. The check
reads the live catalog after ``alembic upgrade head``.
"""

import pytest
from sqlalchemy import text

from app.db.session import get_engine

pytestmark = pytest.mark.db

# A foreign key is covered when some index's leading columns are exactly the
# FK's columns (in any order).
_UNINDEXED_FKS = text(
    """
    SELECT c.conrelid::regclass::text AS table_name,
           c.conname,
           array_to_string(ARRAY(
               SELECT a.attname FROM unnest(c.conkey) k
               JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k
           ), ',') AS columns
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    WHERE c.contype = 'f' AND n.nspname = 'public'
      AND NOT EXISTS (
          SELECT 1 FROM pg_index i
          WHERE i.indrelid = c.conrelid
            AND (SELECT array_agg(x ORDER BY x)
                 FROM unnest((i.indkey::int2[])[0:cardinality(c.conkey) - 1]) x)
              = (SELECT array_agg(y ORDER BY y) FROM unnest(c.conkey) y)
      )
    ORDER BY 1, 2
    """
)


def test_every_foreign_key_is_indexed(migrated_db: None) -> None:
    with get_engine().connect() as conn:
        missing = [f"{t}({cols}) [{name}]" for t, name, cols in conn.execute(_UNINDEXED_FKS)]
    assert missing == [], "Foreign keys without a supporting index:\n" + "\n".join(missing)
