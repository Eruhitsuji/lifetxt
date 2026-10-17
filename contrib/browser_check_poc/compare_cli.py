"""Synthetic CLI-vs-parser evidence; never loads a user's configuration."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from contrib.browser_check_poc.adapter import check_text


def compare():
    fixtures = json.loads(Path(__file__).with_name("fixtures.json").read_text())
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "empty.json"
        config.write_text("{}")
        for fixture in fixtures:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lifetxt",
                    "--config",
                    str(config),
                    "check",
                    "-",
                    "--format",
                    "json",
                ],
                input=fixture["text"],
                text=True,
                capture_output=True,
                cwd=ROOT,
                check=False,
                timeout=30,
            )
            cli = json.loads(result.stdout)
            core = check_text(fixture["text"])
            rows.append(
                {
                    "name": fixture["name"],
                    "diagnostics_match": cli == core["diagnostics"],
                    "cli_exit_code": result.returncode,
                    "cli_diagnostics": cli,
                    "parser_result": core,
                }
            )
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows = compare()
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "fixtures": len(rows),
                "diagnostics_match": sum(r["diagnostics_match"] for r in rows),
                "differences": [r["name"] for r in rows if not r["diagnostics_match"]],
            }
        )
    )
