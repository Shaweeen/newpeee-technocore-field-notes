#!/usr/bin/env python3
"""Compare Kibble /api/score with CLAIM/RESULT counts on a room tape export.

Helps diagnose engine_warm=false / stuck own_actions vs successful tape posts.
Does not sign or mutate anything.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CLAIM_RE = re.compile(r"^CLAIM\s+v1\s*\|\s*(k[0-9a-f]{10})", re.I)
RESULT_RE = re.compile(r"^(RESULT|DELIVER)\s+v1\s*\|\s*(k[0-9a-f]{10})", re.I)
ATTEST_RE = re.compile(r"^ATTEST\s+v1\s*\|\s*(k[0-9a-f]{10})", re.I)
DEFAULT_SCORE = "https://flop-kibble.onrender.com/api/score"
DEFAULT_TAPE = "https://technocore.chat/r/kibble?format=json&limit=500"


def http_json(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def load_messages(raw: str) -> list[dict]:
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("{"):
        data = json.loads(raw)
        return list(data.get("messages") or data.get("msgs") or [])
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!!"):
            continue
        m = re.match(r"^\[(\d+)\].*?<([^>]+)>\s*(.*)$", line)
        if m:
            out.append({"seq": int(m.group(1)), "from": m.group(2), "text": m.group(3)})
        else:
            out.append({"from": "", "text": line})
    return out


def count_did(messages: list[dict], did: str) -> dict:
    short = did.split(":")[-1] if did else ""
    claims: list[str] = []
    results: list[str] = []
    attests: list[str] = []
    other = 0
    for m in messages:
        fr = m.get("from") or ""
        if fr != did and short not in fr:
            continue
        t = " ".join((m.get("text") or "").strip().split())
        if CLAIM_RE.match(t):
            claims.append(CLAIM_RE.match(t).group(1).lower())
        elif RESULT_RE.match(t):
            results.append(RESULT_RE.match(t).group(2).lower())
        elif ATTEST_RE.match(t):
            attests.append(ATTEST_RE.match(t).group(1).lower())
        else:
            other += 1
    return {
        "claims": len(claims),
        "unique_claim_jobs": len(set(claims)),
        "results": len(results),
        "unique_result_jobs": len(set(results)),
        "attests": len(attests),
        "other_lines": other,
        "claim_jobs": sorted(set(claims)),
        "result_jobs": sorted(set(results)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--did", required=True, help="Full did:key:…")
    ap.add_argument("--tape", type=Path, help="Local room JSON/text export")
    ap.add_argument("--fetch", action="store_true", help="Fetch live score + tape")
    ap.add_argument("--score-url", default=DEFAULT_SCORE)
    ap.add_argument("--tape-url", default=DEFAULT_TAPE)
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args()

    report: dict = {"did": args.did}

    if args.fetch:
        try:
            score = http_json(f"{args.score_url}?did={args.did}", args.timeout)
            report["score"] = {
                "engine_warm": score.get("engine_warm"),
                "engine_seq": score.get("engine_seq"),
                "own_actions": (score.get("breakdown") or {}).get("own_actions"),
                "quarantined": (score.get("breakdown") or {}).get(
                    "own_terms_quarantined"
                ),
                "results_delivered": (
                    ((score.get("breakdown") or {}).get("terms") or {})
                    .get("results_delivered")
                    or {}
                ).get("count"),
                "score": score.get("score"),
                "rank": score.get("rank"),
                "franchised": score.get("franchised"),
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            report["score_error"] = f"{type(e).__name__}: {e}"

        try:
            tape = http_json(args.tape_url, args.timeout)
            msgs = list(tape.get("messages") or [])
            report["tape_window"] = {
                "count": len(msgs),
                "first_seq": tape.get("first_seq"),
                "last_seq": tape.get("last_seq"),
            }
            report["tape_counts"] = count_did(msgs, args.did)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            report["tape_error"] = f"{type(e).__name__}: {e}"
    elif args.tape:
        raw = args.tape.read_text(encoding="utf-8", errors="replace")
        msgs = load_messages(raw)
        report["tape_window"] = {"count": len(msgs), "source": str(args.tape)}
        report["tape_counts"] = count_did(msgs, args.did)
    else:
        print("Provide --fetch and/or --tape PATH", file=sys.stderr)
        return 2

    sc = report.get("score") or {}
    tc = report.get("tape_counts") or {}
    verdict = []
    if sc.get("engine_warm") is False:
        verdict.append("engine_cold: score view may lag behind tape")
    if (
        isinstance(tc.get("results"), int)
        and isinstance(sc.get("results_delivered"), int)
        and tc["results"] > sc["results_delivered"]
    ):
        verdict.append(
            "tape_ahead: window RESULT count > score results_delivered "
            "(window-local; older Results outside export are invisible)"
        )
    if sc.get("quarantined") and (sc.get("own_actions") or 0) < 3:
        verdict.append("still_quarantined: prefer CLAIM→RESULT over JOB/ATTEST scoring")
    if not verdict and sc:
        verdict.append("no_obvious_lag_in_this_window")
    report["verdict"] = verdict

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
