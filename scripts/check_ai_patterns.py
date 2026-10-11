"""Offline catalog checks. Fixtures, not LLMs, are the executable authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path("examples/ai-patterns/manifest.json")
GROUPS = {
    "TYPE": 9,
    "STATUS": 7,
    "TIME": 10,
    "REC": 8,
    "REL": 8,
    "GRAM": 8,
    "COM": 8,
    "PIT": 10,
}
KINDS = {"recommended", "A", "B", "C", "D"}


def inside(root: Path, name: str) -> Path:
    """Resolve repository-relative paths; reject traversal and escaping symlinks."""
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    return path


def run_cli(root: Path, args: list[str]) -> dict:
    env = dict(os.environ, TZ="UTC", PYTHONHASHSEED="0")
    result = subprocess.run(
        [sys.executable, "-m", "lifetxt", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "command": ["python", "-m", "lifetxt", *args],
        "exit": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def fence(text: str, marker: str) -> str:
    """Extract a named fence, including longer fences around Markdown bodies."""
    token = f"<!-- fixture:{marker} -->"
    if text.count(token) != 1:
        raise ValueError(f"expected exactly one {token}")
    tail = text.split(token, 1)[1].lstrip()
    match = re.match(r"(`{3,})lifetxt\n", tail)
    if not match:
        raise ValueError(f"missing lifetxt fence for {marker}")
    end = "\n" + match[1] + "\n"
    body = tail[match.end() :]
    if end not in body:
        raise ValueError(f"unterminated fence for {marker}")
    return body.split(end, 1)[0] + "\n"


def anchors(text: str) -> set[str]:
    result = set(re.findall(r'<a id="([^"]+)"', text))
    counts: Counter = Counter()
    for line in text.splitlines():
        match = re.match(r"#{1,6}\s+(.+)", line)
        if match:
            slug = re.sub(r"[^\w\- ]", "", match[1].lower()).replace(" ", "-")
            number = counts[slug]
            counts[slug] += 1
            result.add(slug + (f"-{number}" if number else ""))
    return result


def check_links(root: Path, doc: Path) -> list[str]:
    errors = []
    # Ignore fenced examples: Markdown links there are stored body data.
    text = re.sub(r"(?ms)^(`{3,}).*?^\1\s*$", "", doc.read_text(encoding="utf-8"))
    for target in re.findall(r"\[[^\]\n]+\]\(([^)\s]+)\)", text):
        if re.match(r"[a-zA-Z]+:", target):
            continue
        path_part, _, anchor = unquote(target).partition("#")
        try:
            path = (doc.parent / path_part).resolve() if path_part else doc
            path.relative_to(root.resolve())
            if not path.is_file():
                errors.append(f"{doc.relative_to(root)}: missing link {target}")
            elif (
                anchor
                and path.suffix == ".md"
                and anchor not in anchors(path.read_text(encoding="utf-8"))
            ):
                errors.append(f"{doc.relative_to(root)}: missing anchor {target}")
        except ValueError:
            errors.append(f"{doc.relative_to(root)}: outside repository {target}")
    return errors


def validate(root: Path = ROOT, allow_planned: bool = False) -> dict:
    manifest = json.loads(inside(root, str(CATALOG)).read_text(encoding="utf-8"))
    errors, results, docs, planned = [], [], set(), []
    entries = manifest["patterns"]
    ids = [e["id"] for e in entries]
    expected_ids = {
        f"PAT-{g}-{i:03d}" for g, n in GROUPS.items() for i in range(1, n + 1)
    }
    if len(ids) != len(set(ids)) or set(ids) != expected_ids:
        errors.append("manifest IDs must uniquely cover the approved 68 slots")
    for entry in entries:
        pid = entry["id"]
        if entry["state"] == "planned":
            planned.append(pid)
            if entry.get("validation") != "not run":
                errors.append(f"{pid}: planned must be not run")
            continue
        if entry["state"] != "implemented":
            errors.append(f"{pid}: unsupported state")
            continue
        if not all(
            entry.get(k)
            for k in ("input", "context", "reason", "spec", "sources", "meaning_review")
        ):
            errors.append(f"{pid}: incomplete context/reason/provenance/review")
        if set(entry.get("docs", {})) != {"ja", "en"}:
            errors.append(f"{pid}: both JA and EN documents are required")
        variants = entry.get("variants", [])
        names = [v["name"] for v in variants]
        if (
            not variants
            or names.count("recommended") != 1
            or len(names) != len(set(names))
        ):
            errors.append(
                f"{pid}: unique variants and one recommended fixture required"
            )
        for variant in variants:
            marker = f"{pid}/{variant['name']}"
            try:
                path = inside(root, variant["path"])
                data = path.read_bytes()
                source = data.decode("utf-8")
                if variant["classification"] not in KINDS:
                    errors.append(f"{marker}: invalid classification")
                for lang, doc_name in entry.get("docs", {}).items():
                    doc = inside(root, doc_name)
                    docs.add(doc)
                    text = doc.read_text(encoding="utf-8")
                    if f'<a id="{pid.lower()}"></a>' not in text:
                        errors.append(f"{pid}: missing stable anchor in {lang}")
                    if fence(text, marker) != source:
                        errors.append(
                            f"{marker}: {lang} differs from canonical fixture"
                        )
                result = run_cli(root, ["check", variant["path"], "--format", "json"])
                diagnostics = json.loads(result["stdout"])
                actual = {"exit": result["exit"], "diagnostics": diagnostics}
                actual_codes = [
                    [d["severity"], d["code"], d["line"]] for d in diagnostics
                ]
                expectation = variant["expected"]
                if (
                    result["exit"] != expectation["exit"]
                    or actual_codes != expectation["diagnostics"]
                ):
                    errors.append(
                        f"{marker}: unexpected exit/diagnostics {actual_codes}"
                    )
                if result["stderr"]:
                    errors.append(f"{marker}: unexpected CLI stderr")
                classification = variant["classification"]
                has_error = any(d["severity"] == "error" for d in diagnostics)
                if (classification == "A" and not has_error) or (
                    classification == "B" and (has_error or not diagnostics)
                ):
                    errors.append(f"{marker}: classification contradicts diagnostics")
                digest = hashlib.sha256(data).hexdigest()
                observed = variant.get("observed", {})
                if not observed.get("engine_commit") or not observed.get(
                    "core_version"
                ):
                    errors.append(f"{marker}: missing recorded engine identity")
                if observed.get("sha256") != digest or observed.get("result") != actual:
                    errors.append(f"{marker}: stale recorded validation")
                item = {"id": marker, "sha256": digest, **result, **actual}
                if variant.get("agenda"):
                    query = variant["agenda"]
                    agenda = run_cli(
                        root,
                        [
                            "agenda",
                            variant["path"],
                            "--from",
                            query["from"],
                            "--to",
                            query["to"],
                            "--format",
                            "json",
                        ],
                    )
                    agenda_data = json.loads(agenda["stdout"])
                    if agenda["exit"] != 0 or agenda_data != query["expected"]:
                        errors.append(f"{marker}: agenda expansion changed")
                    item["agenda"] = agenda
                results.append(item)
            except (KeyError, ValueError, OSError, subprocess.SubprocessError) as exc:
                errors.append(f"{marker}: {exc}")
    if planned and not allow_planned:
        errors.append(f"{len(planned)} planned patterns remain (not run)")
    for doc in sorted(docs):
        errors.extend(check_links(root, doc))
    for lang in ("ja", "en"):
        index = root / f"docs/{lang}/ai-patterns.md"
        if index.is_file():
            errors.extend(check_links(root, index))
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    version = run_cli(root, ["--version"])
    return {
        "schema_version": 1,
        "engine_commit": head,
        "core_version": version["stdout"].strip(),
        "timezone": "UTC",
        "planned": planned,
        "checked_fixtures": len(results),
        "results": results,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-planned",
        action="store_true",
        help="Intermediate PRs only; explicitly report unimplemented slots.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional local JSON evidence (not a fixture update).",
    )
    args = parser.parse_args()
    report = validate(allow_planned=args.allow_planned)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        f"checked={report['checked_fixtures']} planned={len(report['planned'])} errors={len(report['errors'])}"
    )
    for error in report["errors"]:
        print(error, file=sys.stderr)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
