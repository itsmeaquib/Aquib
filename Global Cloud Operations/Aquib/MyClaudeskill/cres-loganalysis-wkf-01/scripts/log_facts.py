#!/usr/bin/env python3
"""log_facts.py - deterministic facts from log files so a log analysis can quote numbers that reconcile.

Reports, per file and overall:
  * line count, first/last timestamp seen
  * top error signatures (timestamps/numbers/hex normalised so repeats collapse)
  * occurrences of an optional --pattern (regex), with first/last time and hourly buckets
  * restart "cycles": count of --cycle-marker lines, and pattern hits per cycle
  * whether a --success-marker ever appears (and when)
  * largest silent gap between pattern matches
  * --expect N: says whether the number you intend to quote matches the log

Usage:
  python log_facts.py --input <file|dir> [--pattern REGEX] [--cycle-marker REGEX]
                      [--success-marker REGEX] [--expect N] [--top 8] [--json out.json]

Read-only. Times are reported exactly as written in the log (no timezone conversion);
the caller must state the log timezone in the analysis.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

TS_PATTERNS = [
    (re.compile(r"(\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{2}):(\d{2}):(\d{2})"), "ymd"),
    (re.compile(r"(\d{2})/(\d{2})/(\d{4})[ T](\d{2}):(\d{2}):(\d{2})"), "mdy"),
]
ERR_HINT = re.compile(
    r"(exception|error|fatal|fail|cannot|unable|denied|refused|timeout|timed out|"
    r"too many|ORA-\d+|exit code|exited)", re.I)


def parse_ts(line):
    for rx, kind in TS_PATTERNS:
        m = rx.search(line)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        try:
            return datetime(*g) if kind == "ymd" else datetime(g[2], g[0], g[1], g[3], g[4], g[5])
        except ValueError:
            return None
    return None


def normalise(line):
    s = line.strip()
    for rx, _ in TS_PATTERNS:
        s = rx.sub("<ts>", s)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", s)
    s = re.sub(r"\b\d+(\.\d+)*\b", "<n>", s)
    return re.sub(r"\s+", " ", s)[:220]


def iter_files(path):
    if os.path.isfile(path):
        yield path
        return
    for root, _, files in os.walk(path):
        for f in sorted(files):
            if f.lower().endswith((".log", ".txt", ".out", ".csv", ".xml", ".json")) or "." not in f:
                yield os.path.join(root, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--pattern")
    ap.add_argument("--cycle-marker")
    ap.add_argument("--success-marker")
    ap.add_argument("--expect", type=int,
                    help="count you intend to quote; the script says whether it reconciles")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json")
    a = ap.parse_args()

    pat = re.compile(a.pattern, re.I) if a.pattern else None
    cyc = re.compile(a.cycle_marker, re.I) if a.cycle_marker else None
    suc = re.compile(a.success_marker, re.I) if a.success_marker else None

    sigs, hourly = Counter(), Counter()
    match_ts, cycle_ts, success_ts = [], [], []
    files_out, total_lines, pat_count = [], 0, 0
    hits_per_cycle = []
    cur = None  # pattern hits in the current cycle

    for fp in iter_files(a.input):
        n, first, last, fhits = 0, None, None, 0
        try:
            fh = open(fp, "r", errors="replace")
        except OSError as e:
            files_out.append({"file": fp, "error": str(e)})
            continue
        with fh:
            for line in fh:
                n += 1
                ts = parse_ts(line)
                if ts:
                    first = first or ts
                    last = ts
                if cyc and cyc.search(line):
                    if cur is not None:
                        hits_per_cycle.append(cur)
                    cur = 0
                    if ts:
                        cycle_ts.append(ts)
                if suc and suc.search(line) and ts:
                    success_ts.append(ts)
                if pat:
                    if pat.search(line):
                        pat_count += 1
                        fhits += 1
                        if cur is not None:
                            cur += 1
                        if ts:
                            match_ts.append(ts)
                            hourly[ts.strftime("%Y-%m-%d %H:00")] += 1
                        sigs[normalise(line)] += 1
                elif ERR_HINT.search(line):
                    sigs[normalise(line)] += 1
        if cur is not None:
            hits_per_cycle.append(cur)
            cur = None
        total_lines += n
        files_out.append({"file": fp, "lines": n,
                          "first_ts": str(first) if first else None,
                          "last_ts": str(last) if last else None,
                          "pattern_hits": fhits})

    gap = None
    if len(match_ts) > 1:
        srt = sorted(match_ts)
        g = max(((b - x).total_seconds(), x, b) for x, b in zip(srt, srt[1:]))
        gap = {"seconds": int(g[0]), "from": str(g[1]), "to": str(g[2])}

    out = {
        "files": files_out,
        "total_lines": total_lines,
        "pattern": a.pattern,
        "pattern_count": pat_count if pat else None,
        "pattern_first": str(min(match_ts)) if match_ts else None,
        "pattern_last": str(max(match_ts)) if match_ts else None,
        "hourly_buckets": dict(sorted(hourly.items())),
        "largest_gap_between_matches": gap,
        "cycles_detected": len(cycle_ts) if cyc else None,
        "cycle_starts": [str(t) for t in cycle_ts] if cyc else None,
        "pattern_hits_per_cycle": hits_per_cycle if (cyc and pat) else None,
        "success_marker_found": bool(success_ts) if suc else None,
        "success_times": [str(t) for t in success_ts[:10]] if suc else None,
        "top_signatures": [{"count": c, "signature": s} for s, c in sigs.most_common(a.top)],
    }
    if a.expect is not None and pat:
        out["expect_reconciles"] = (a.expect == pat_count)
        out["expect_note"] = f"you intend to quote {a.expect}; log contains {pat_count}"

    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=2)

    print(f"Files scanned: {len(files_out)}   Total lines: {total_lines}")
    for f in files_out:
        print(f"  - {f['file']}: {f.get('lines', 'ERR')} lines, {f.get('first_ts')} -> {f.get('last_ts')}")
    if pat:
        print(f"\nPattern /{a.pattern}/ : {pat_count} hits  ({out['pattern_first']} -> {out['pattern_last']})")
        for h, c in sorted(hourly.items()):
            print(f"    {h}  x{c}")
        if gap:
            print(f"  Largest gap between hits: {gap['seconds']}s ({gap['from']} -> {gap['to']})")
    if cyc:
        print(f"\nCycle marker /{a.cycle_marker}/ : {len(cycle_ts)} cycles")
        if pat and hits_per_cycle:
            print(f"  Pattern hits per cycle: {hits_per_cycle}")
    if suc:
        if success_ts:
            print(f"\nSuccess marker /{a.success_marker}/ : FOUND at {', '.join(map(str, success_ts[:3]))}")
        else:
            print(f"\nSuccess marker /{a.success_marker}/ : NOT FOUND (no successful start in scanned logs)")
    print("\nTop signatures:")
    for s in out["top_signatures"]:
        print(f"  x{s['count']:<5} {s['signature']}")
    if "expect_note" in out:
        print(f"\nReconcile: {'OK' if out['expect_reconciles'] else 'MISMATCH'} - {out['expect_note']}")


if __name__ == "__main__":
    sys.exit(main())
