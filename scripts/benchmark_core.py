#!/usr/bin/env python
"""Reproducible large-workspace storage scaling benchmark."""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, sys, tempfile, time
from datetime import date, datetime
from pathlib import Path
from lifetxt.agenda import agenda_records, parse_agenda_range
from lifetxt.command_center import command_center
from lifetxt.parser import parse_text
from lifetxt.query import run_query

try:
    import resource
except ImportError:  # Windows has no stdlib resource module.
    resource = None

SCHEMA = "lifetxt-storage-benchmark-v1"
SIZES = (1000, 10000, 100000, 200000)
REFERENCE_DATE = date(2026, 9, 24)

def synthetic_text(count, offset=0):
    rows = []
    utf8_title = chr(26085) + chr(26412) + chr(35486)
    for index in range(offset, offset + count):
        kind = ("T", "E", "N")[index % 3]
        status = "[x]" if index % 11 == 0 else "[ ]"
        detail = "id:item_{0:07d} project:benchmark tag:stable".format(index)
        if kind == "T":
            detail += " due:2026-09-{0:02d}".format(index % 28 + 1)
        elif kind == "E":
            detail += " on:2026-09-{0:02d}".format(index % 28 + 1)
        rows.append('# {0} {1} "{4} task {2:07d}" {3}\n'.format(status, kind, index, detail, utf8_title))
        if index % 97 == 0:
            rows.append("# benchmark comment {0}\n\n".format(index))
    return "".join(rows)

def rss_bytes():
    if resource is None or os.name == "nt":
        return None
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)

def measure(function):
    before = rss_bytes()
    started = time.perf_counter()
    result = function()
    after = rss_bytes()
    return {"duration_seconds": round(time.perf_counter() - started, 6),
            "peak_rss_bytes": after,
            "rss_delta_bytes": after - before if after is not None and before is not None else None,
            "result": result}

def parsed(text):
    items, diagnostics = parse_text(text)
    errors = [d for d in diagnostics if getattr(d, "severity", "") == "error"]
    if errors:
        raise RuntimeError("synthetic fixture invalid: %s" % errors[0])
    return items

def benchmark_layout(layout, count):
    chunks = (count // 2, count - count // 2) if layout == "multi-source" else (count,)
    with tempfile.TemporaryDirectory(prefix="lifetxt-storage-benchmark-") as directory:
        paths = []
        for index, chunk in enumerate(chunks):
            path = Path(directory) / ("active.life.txt" if index == 0 else "archive.life.txt")
            path.write_text(synthetic_text(chunk, sum(chunks[:index])), encoding="utf-8")
            paths.append(path)
        texts = [path.read_text(encoding="utf-8") for path in paths]
        all_text = "".join(texts)
        rows = {"layout": layout, "records": count,
                "bytes": sum(p.stat().st_size for p in paths),
                "source_files": [{"path": p.name, "bytes": p.stat().st_size} for p in paths],
                "fixture_sha256": hashlib.sha256(all_text.encode("utf-8")).hexdigest(),
                "operations": {}}
        result = measure(lambda: [parsed(text) for text in texts])
        items = [item for group in result["result"] for item in group]
        result["result"] = {"records": len(items)}
        rows["operations"]["parse_load"] = result
        result = measure(lambda: sum(len(parse_text(text)[1]) for text in texts))
        result["result"] = {"diagnostics": result["result"]}
        rows["operations"]["check"] = result
        result = measure(lambda: run_query(items, "open project:benchmark tag:stable")[0])
        result["result"] = {"records": len(result["result"])}
        rows["operations"]["query"] = result
        start, end = parse_agenda_range("2026-09-24", "2026-09-25", now=datetime(2026, 9, 24))
        result = measure(lambda: agenda_records(items, start, end))
        result["result"] = {"records": len(result["result"])}
        rows["operations"]["agenda"] = result
        result = measure(lambda: command_center(items, {}, REFERENCE_DATE, horizon_days=3))
        result["result"] = {"keys": sorted(result["result"])}
        rows["operations"]["today"] = result
        result = measure(lambda: [item for item in items if "日本語" in item.title])
        result["result"] = {"records": len(result["result"])}
        rows["operations"]["search"] = result
        return rows

def benchmark(root, sizes):
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except Exception:
        commit = None
    return {"schema": SCHEMA, "benchmark_version": "1", "commit": commit,
            "python": platform.python_version(), "platform": platform.platform(),
            "interpreter": Path(sys.executable).name, "reference_date": REFERENCE_DATE.isoformat(),
            "sizes": list(sizes),
            "layouts": [benchmark_layout(layout, count) for count in sizes for layout in ("single-file", "multi-source")],
            "unsupported_surfaces": {
                "web_server": "not measured: startup and HTTP scheduling are environment/port dependent; use a deployment-specific harness",
                "tui": "not measured: terminal rendering/startup timing is environment dependent and not a stable scaling signal"},
            "interpretation": {
                "thresholds": "No universal limits are inferred from one machine; compare trends and repeated runs.",
                "rss": "Unix getrusage peak is recorded; Windows reports null because this dependency-free harness has no reliable cross-process RSS provider."}}

def markdown(report):
    lines = ["# Storage Scaling Benchmark", "", "Generated by scripts/benchmark_core.py.", "",
             "| Records | Layout | Bytes | Parse | Check | Query | Agenda | Today | RSS peak |",
             "|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in report["layouts"]:
        op = row["operations"]
        lines.append("| {0:,} | {1} | {2:,} | {3:.6f} | {4:.6f} | {5:.6f} | {6:.6f} | {7:.6f} | {8} |".format(
            row["records"], row["layout"], row["bytes"], op["parse_load"]["duration_seconds"],
            op["check"]["duration_seconds"], op["query"]["duration_seconds"],
            op["agenda"]["duration_seconds"], op["today"]["duration_seconds"],
            op["parse_load"]["peak_rss_bytes"] or "n/a"))
    lines += ["", "This is a trend baseline, not a universal hard-limit recommendation. Web/server and TUI measurements are omitted because their timing is environment-dependent.", ""]
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=SIZES)
    args = parser.parse_args()
    report = benchmark(args.root.resolve(), tuple(args.sizes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"ok": True, "schema": SCHEMA, "sizes": args.sizes}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
