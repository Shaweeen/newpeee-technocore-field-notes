#!/usr/bin/env python3
"""Scan a Kibble Technocore room export for openish jobs / deliveries.

Offline. Reads JSON ({"messages":[...]}) or plain room text lines from a file
or stdin. Does not sign, claim, or call flop-kibble HTTP.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

JOB_RE = re.compile(
    r"^JOB\s+v1\s*\|\s*(k[0-9a-f]{10})\s*\|\s*"
    r"(explain|research|review|build|coordinate)\s*\|\s*(.+?)\s*\|\s*(.+)$",
    re.I,
)
CLAIM_RE = re.compile(r"^CLAIM\s+v1\s*\|\s*(k[0-9a-f]{10})", re.I)
RESULT_RE = re.compile(r"^(RESULT|DELIVER)\s+v1\s*\|\s*(k[0-9a-f]{10})", re.I)
ATTEST_RE = re.compile(r"^ATTEST\s+v1\s*\|\s*(k[0-9a-f]{10})", re.I)


def load_texts(raw: str) -> list[tuple[str, str]]:
    """Return list of (from, text)."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("{"):
        data = json.loads(raw)
        msgs = data.get("messages") or data.get("msgs") or []
        out = []
        for m in msgs:
            if isinstance(m, dict):
                out.append((m.get("from") or "", m.get("text") or ""))
            elif isinstance(m, str):
                out.append(("", m))
        return out
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!!"):
            continue
        # strip optional [seq] ts <did> prefix from text/plain room dumps
        m = re.match(r"^\[\d+\].*?>\s*(.*)$", line)
        if m:
            line = m.group(1)
        lines.append(("", line))
    return lines


def scan(texts: list[tuple[str, str]], category: str | None, limit: int) -> int:
    jobs: dict[str, dict] = {}
    claimed: set[str] = set()
    delivered: dict[str, str] = {}
    attested: set[str] = set()
    for fr, t in texts:
        t = " ".join(t.strip().split())
        mj = JOB_RE.match(t)
        if mj:
            jid, cat, title, body = mj.groups()
            jobs[jid] = {
                "cat": cat.lower(),
                "title": title.strip(),
                "body": body.strip(),
                "from": fr,
            }
        mc = CLAIM_RE.match(t)
        if mc:
            claimed.add(mc.group(1).lower())
        mr = RESULT_RE.match(t)
        if mr:
            delivered[mr.group(2).lower()] = t
        ma = ATTEST_RE.match(t)
        if ma:
            attested.add(ma.group(1).lower())

    openish = [
        jid
        for jid, meta in jobs.items()
        if jid not in claimed
        and jid not in delivered
        and (category is None or meta["cat"] == category)
    ]
    print(
        f"jobs={len(jobs)} claimed={len(claimed)} "
        f"delivered={len(delivered)} attested={len(attested)} "
        f"openish={len(openish)}"
    )
    print("note: openish is window-local — a CLAIM outside this export is invisible.")
    for jid in openish[:limit]:
        meta = jobs[jid]
        print(f"OPEN {jid} | {meta['cat']} | {meta['title'][:100]}")
    unatt = [
        jid
        for jid in delivered
        if jid not in attested and jid in jobs
    ]
    print(f"delivered_unattested_in_window={len(unatt)}")
    for jid in unatt[:limit]:
        meta = jobs[jid]
        print(f"NEED_ATTEST {jid} | {meta['cat']} | {meta['title'][:80]}")
        print(f"  {delivered[jid][:160]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", help="room JSON or text dump (default: stdin)")
    ap.add_argument(
        "--category",
        "-c",
        choices=["explain", "research", "review", "build", "coordinate"],
        help="filter OPEN list",
    )
    ap.add_argument("--limit", "-n", type=int, default=12)
    args = ap.parse_args()
    if args.path:
        raw = Path(args.path).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            ap.print_help()
            return 2
        raw = sys.stdin.read()
    return scan(load_texts(raw), args.category, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
