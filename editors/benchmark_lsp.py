"""Repeatable local LSP analysis baseline; run from the repository root."""

import argparse
import json
import platform
import statistics
import time
import tracemalloc

from lifetxt.lsp_document import Document
from lifetxt.lsp_features import completion
from lifetxt.lsp_workspace import workspace_diagnostics, workspace_items


def benchmark():
    text = "\n".join(
        f'[ ] T "Task {i}" id:t{i} project:demo tag:work' for i in range(1000)
    )
    query = "[ ] T query ref:t99"
    timings = []
    tracemalloc.start()
    for version in range(7):
        started = time.perf_counter()
        docs = {
            "a": Document("a", version, text, check_links=False),
            "q": Document("q", version, query, check_links=False),
        }
        extra = workspace_diagnostics(docs, "id")
        for doc in docs.values():
            doc.diagnostics(extra.get(doc.uri, ()))
        result = completion(
            docs["q"], {"line": 0, "character": len(query)}, workspace_items(docs)
        )
        assert "t999" in [item["label"] for item in result]
        timings.append((time.perf_counter() - started) * 1000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "fixture": "1000-items-two-buffers-v1",
        "python": platform.python_version(),
        "os": platform.system(),
        "machine": platform.machine(),
        "repeats": len(timings),
        "text_utf8_bytes": len(text.encode()),
        "median_ms": round(statistics.median(timings), 3),
        "max_ms": round(max(timings), 3),
        "tracemalloc_peak_bytes": peak,
        "includes": "Core parse, compact position map, workspace reference checks, diagnostic conversion and ID completion; tracemalloc enabled",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", help="Compare median on the same Python/OS/machine fixture"
    )
    parser.add_argument("--max-ratio", type=float, default=2.0)
    args = parser.parse_args()
    result = benchmark()
    print(json.dumps(result, indent=2))
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as handle:
            baseline = json.load(handle)
        if any(
            result[key] != baseline[key]
            for key in ("fixture", "python", "os", "machine")
        ):
            parser.error(
                "Baseline environment/fixture differs; measure a new local baseline"
            )
        if result["median_ms"] > baseline["median_ms"] * args.max_ratio:
            raise SystemExit("Analysis median exceeded the requested regression ratio")
