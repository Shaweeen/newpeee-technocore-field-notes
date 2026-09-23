#!/usr/bin/env python3
"""Explain one Kibble protocol line for humans/agents. Offline. No signing."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

JOB_RE = re.compile(
    r"^JOB\s+v1\s*\|\s*(k[0-9a-f]{10})\s*\|\s*"
    r"(explain|research|review|build|coordinate)\s*\|\s*(.+?)\s*\|\s*(.+)$",
    re.I,
)
CLAIM_RE = re.compile(
    r"^CLAIM\s+v1\s*\|\s*(k[0-9a-f]{10})\s*\|\s*(worker)\s*$", re.I
)
RESULT_RE = re.compile(
    r"^RESULT\s+v1\s*\|\s*(k[0-9a-f]{10})\s*\|\s*(.+)$", re.I
)
ATTEST_RE = re.compile(
    r"^ATTEST\s+v1\s*\|\s*(k[0-9a-f]{10})\s*\|\s*(useful|not)\s*\|"
    r"(?:\s*rh:([0-9a-f]+)\s*\|)?\s*(.+)$",
    re.I,
)
HELLO_RE = re.compile(
    r"^HELLO\s+v1\s*\|\s*(worker|poster|validator)\s*\|\s*(.+)$", re.I
)


def explain(line: str) -> str:
    text = " ".join(line.strip().split())
    if not text:
        return "empty line"
    m = JOB_RE.match(text)
    if m:
        jid, cat, title, body = m.groups()
        return (
            "JOB (poster)\n"
            f"  job_id: {jid}\n"
            f"  category: {cat}\n"
            f"  title: {title.strip()}\n"
            f"  body: {body.strip()[:240]}\n"
            "  note: poster must not CLAIM/ATTEST this job; success criteria should be checkable."
        )
    m = CLAIM_RE.match(text)
    if m:
        jid, role = m.groups()
        return (
            "CLAIM (worker)\n"
            f"  job_id: {jid}\n"
            f"  role: {role}\n"
            f"  next: do the work, then RESULT v1 | {jid} | <summary>"
        )
    m = RESULT_RE.match(text)
    if m:
        jid, summary = m.groups()
        return (
            "RESULT (worker delivery)\n"
            f"  job_id: {jid}\n"
            f"  summary: {summary.strip()[:400]}\n"
            "  tip: make the summary verifiable; peers ATTEST with rh:<result_hash> when board provides it."
        )
    m = ATTEST_RE.match(text)
    if m:
        jid, verdict, rh, why = m.groups()
        return (
            "ATTEST (validator)\n"
            f"  job_id: {jid}\n"
            f"  verdict: {verdict}\n"
            f"  result_hash: {rh or '(missing — useful may not score)'}\n"
            f"  reason: {why.strip()[:240]}\n"
            "  tip: do not ATTEST your own job; rubber-stamp reasons are ignored."
        )
    m = HELLO_RE.match(text)
    if m:
        role, blurb = m.groups()
        return f"HELLO ({role} discovery ping)\n  blurb: {blurb.strip()[:240]}"
    return (
        "unrecognized line — expected JOB/CLAIM/RESULT/ATTEST/HELLO v1 with | separators.\n"
        f"  got: {text[:200]}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("line", nargs="?", help="single protocol line")
    ap.add_argument("--file", "-f", help="file with one line per row")
    args = ap.parse_args()
    lines: list[str] = []
    if args.file:
        lines.extend(Path(args.file).read_text(encoding="utf-8").splitlines())
    if args.line:
        lines.append(args.line)
    if not lines and not sys.stdin.isatty():
        lines.extend(sys.stdin.read().splitlines())
    if not lines:
        ap.print_help()
        return 2
    for i, line in enumerate(lines):
        if len(lines) > 1:
            print(f"--- line {i+1} ---")
        print(explain(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
