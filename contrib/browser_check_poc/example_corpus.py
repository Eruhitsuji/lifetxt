"""Compare every bounded public text example using the existing Node WASM probe."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from contrib.browser_check_poc.adapter import MAX_BYTES, check_text
from contrib.browser_check_poc.build import ROOT, SOURCE, build


def collect_examples(root):
    fixtures, excluded = [], []
    for path in sorted(root.rglob("*.txt")):
        raw = path.read_bytes()
        metadata = {
            "name": path.relative_to(root).as_posix(),
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if len(raw) > MAX_BYTES:
            excluded.append({**metadata, "reason": "outside experimental byte limit"})
            continue
        text = raw.decode("utf-8")
        fixtures.append({**metadata, "text": text, "expected": check_text(text)})
    if not fixtures:
        raise ValueError("No executable public examples; cannot claim conformance")
    return fixtures, excluded


def run(site, output):
    fixtures, excluded = collect_examples(ROOT / "examples")
    build(site)
    fixture_file = site / "fixtures.json"
    fixture_file.write_text(
        json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Same pinned runtime and Core; only the experiment's fixture set changes.
    manifest_file = site / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    data = fixture_file.read_bytes()
    manifest["files"]["fixtures.json"] = {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    raw_output = site / "node-example-result.json"
    subprocess.run(
        ["node", str(SOURCE / "probe.mjs"), str(site), str(raw_output)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    observed = json.loads(raw_output.read_text(encoding="utf-8"))
    if [c["name"] for c in observed["cases"]] != [f["name"] for f in fixtures]:
        raise ValueError("Incomplete or mismatched example result set")
    if not all(c["match"] for c in observed["cases"]):
        raise ValueError("Native/WASM example mismatch; retain raw output")
    observed["cases"] = [
        {k: v for k, v in case.items() if k != "result"} for case in observed["cases"]
    ]
    observed.update(
        {
            "issue": 1366,
            "scope": "Public text examples; parser-only Node WASM, not complete Format or CLI or browser coverage",
            "status": "passed",
            "source_inputs": [
                {k: v for k, v in f.items() if k not in ("text", "expected")}
                for f in fixtures
            ],
            "excluded": excluded,
            "manifest": manifest,
            "manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "node_probe_sha256": hashlib.sha256(
                (SOURCE / "probe.mjs").read_bytes()
            ).hexdigest(),
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(observed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": len(fixtures),
                "matches": len(fixtures),
                "excluded": len(excluded),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.site, args.output)
