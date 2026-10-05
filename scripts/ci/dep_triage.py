#!/usr/bin/env python3
"""Dependency advisory triage: report every advisory, fail only on real risk.

Usage:
  dep_triage.py python <pip-audit.json> <runtime-packages.txt>
  dep_triage.py npm <npm-audit-all.json> <npm-audit-prod.json>

Every advisory is reported (severity, package, installed and fixed versions,
whether the package ships in production, and the triage decision) in the job
summary and in ``dep-triage-<ecosystem>.json``. Nothing is silently ignored.

The job FAILS only when an advisory is
  * HIGH or CRITICAL (or of unknown severity) and
  * in a package that ships in production (runtime dependency), and
  * not covered by a current, written entry in security/advisory-triage.json
    (reason why it is not exploitable or not reachable, reviewer, review date).

Dev/build-only advisories and LOW/MODERATE ones are reported as warnings.
An expired triage entry stops covering its advisory.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIAGE = ROOT / "security" / "advisory-triage.json"
BLOCKING = {"HIGH", "CRITICAL", "UNKNOWN"}


def load_triage() -> dict[str, dict]:
    if not TRIAGE.exists():
        return {}
    entries = json.loads(TRIAGE.read_text(encoding="utf-8")).get("advisories", [])
    out = {}
    for e in entries:
        for key in ("id", "package", "decision", "reason", "reviewed_by", "review_by"):
            if not e.get(key):
                raise SystemExit(f"triage entry missing {key}: {e}")
        if e["decision"] not in {
            "not_exploitable",
            "not_reachable",
            "accepted_temporarily",
        }:
            raise SystemExit(f"triage decision not allowed: {e['decision']}")
        out[f"{e['package'].lower()}::{e['id']}"] = e
    return out


def osv_severity(vuln_id: str) -> str:
    """GHSA/PYSEC severity from OSV (best effort; UNKNOWN when unavailable)."""
    try:
        with urllib.request.urlopen(
            f"https://api.osv.dev/v1/vulns/{vuln_id}", timeout=15
        ) as r:
            data = json.load(r)
    except Exception:
        return "UNKNOWN"
    sev = (data.get("database_specific") or {}).get("severity")
    return str(sev).upper() if sev else "UNKNOWN"


def python_rows(audit: Path, runtime_file: Path) -> list[dict]:
    runtime = {
        line.strip().lower().replace("_", "-")
        for line in runtime_file.read_text().splitlines()
        if line.strip()
    }
    data = json.loads(audit.read_text())
    deps = data.get("dependencies", data) if isinstance(data, dict) else data
    rows = []
    for dep in deps:
        name = dep["name"].lower().replace("_", "-")
        for v in dep.get("vulns", []):
            ids = [v["id"], *v.get("aliases", [])]
            ghsa = next((i for i in ids if i.startswith("GHSA-")), v["id"])
            rows.append(
                {
                    "ecosystem": "python",
                    "package": name,
                    "installed": dep.get("version"),
                    "id": v["id"],
                    "aliases": v.get("aliases", []),
                    "severity": osv_severity(ghsa),
                    "fixed_in": v.get("fix_versions", []),
                    "runtime": name in runtime,
                    "summary": (v.get("description") or "")[:200],
                }
            )
    return rows


def npm_rows(all_file: Path, prod_file: Path) -> list[dict]:
    every = json.loads(all_file.read_text() or "{}").get("vulnerabilities", {})
    prod = set(json.loads(prod_file.read_text() or "{}").get("vulnerabilities", {}))
    rows = []
    for name, v in every.items():
        advisories = [x for x in v.get("via", []) if isinstance(x, dict)]
        for adv in advisories or [
            {
                "source": "transitive",
                "title": "via "
                + ", ".join(x for x in v.get("via", []) if isinstance(x, str)),
            }
        ]:
            fix = v.get("fixAvailable")
            rows.append(
                {
                    "ecosystem": "npm",
                    "package": name,
                    "installed": v.get("range"),
                    "id": str(adv.get("url") or adv.get("source")),
                    "aliases": [],
                    "severity": str(
                        adv.get("severity") or v.get("severity") or "unknown"
                    ).upper(),
                    "fixed_in": [fix.get("version")] if isinstance(fix, dict) else [],
                    "runtime": name in prod,
                    "direct": v.get("isDirect", False),
                    "summary": str(adv.get("title", ""))[:200],
                }
            )
    return rows


def main() -> int:
    eco, a, b = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    rows = python_rows(a, b) if eco == "python" else npm_rows(a, b)
    triage = load_triage()
    today = date.today().isoformat()
    blocking = 0
    for r in rows:
        entry = triage.get(f"{r['package']}::{r['id']}")
        if entry and entry["review_by"] < today:
            entry = None
            r["triage"] = "triage entry expired"
        elif entry:
            r["triage"] = (
                f"{entry['decision']}: {entry['reason']} ({entry['reviewed_by']})"
            )
        if not r["runtime"]:
            r["decision"] = "report (dev/build-only, not shipped)"
        elif r["severity"] not in BLOCKING:
            r["decision"] = "report (low/moderate in a runtime dependency)"
        elif entry:
            r["decision"] = f"report (triaged: {entry['decision']})"
        else:
            r["decision"] = (
                "BLOCK (high/critical/unknown in a runtime dependency, untriaged)"
            )
            blocking += 1

    out = ROOT / f"dep-triage-{eco}.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        f"### Dependency advisories ({eco}): {len(rows)} found, {blocking} blocking",
        "",
        "| Severity | Package | Installed | Advisory | Ships in production | Fixed in | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in sorted(rows, key=lambda r: (not r["runtime"], r["severity"])):
        fixed = ", ".join(map(str, r["fixed_in"])) or "-"
        lines.append(
            f"| {r['severity']} | {r['package']} | {r['installed']} | {r['id']} | "
            f"{'yes' if r['runtime'] else 'no (dev/build)'} | {fixed} "
            f"| {r['decision']} |"
        )
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    for r in rows:
        level = "error" if r["decision"].startswith("BLOCK") else "warning"
        print(
            f"::{level} title=dependency advisory ({eco})::{r['severity']} {r['package']} "
            f"{r['id']} — runtime={r['runtime']} — {r['decision']}"
        )
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
