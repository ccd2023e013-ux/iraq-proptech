#!/usr/bin/env python3
"""Print the installed distributions the backend needs at runtime (no extras).

Used by dep_triage.py to tell production dependencies from dev/test-only ones.
"""

from __future__ import annotations

import re
from importlib import metadata

seen: set[str] = set()
stack = ["proptech-backend"]
while stack:
    name = stack.pop()
    key = name.lower().replace("_", "-")
    if key in seen:
        continue
    seen.add(key)
    try:
        requires = metadata.requires(name) or []
    except metadata.PackageNotFoundError:
        continue
    for req in requires:
        if "extra ==" in req:
            continue  # optional extras (dev, test) are not runtime
        dep = re.split(r"[\s\[<>=!~;(]", req, maxsplit=1)[0]
        if dep:
            stack.append(dep)
seen.discard("proptech-backend")
print("\n".join(sorted(seen)))
