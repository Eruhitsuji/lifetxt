#!/usr/bin/env python
"""Verify the stable MCP read surface from a clean built artifact."""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _run(command, cwd, input_text=None):
    return subprocess.run(
        command,
        cwd=str(cwd),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _python(venv_dir):
    return str(
        Path(venv_dir) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def run(root):
    work = Path(tempfile.mkdtemp(prefix="lifetxt-mcp-artifact-smoke-"))
    try:
        dist = work / "dist"
        dist.mkdir()
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--sdist",
                "--wheel",
                "--outdir",
                str(dist),
            ],
            root,
        )
        wheels = sorted(dist.glob("*.whl"))
        sdists = sorted(dist.glob("*.tar.gz"))
        _assert(len(wheels) == 1 and len(sdists) == 1, "expected one wheel and sdist")
        wheel = wheels[0]
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()

        env_dir = work / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(str(env_dir))
        wheel_python = _python(env_dir)
        _run(
            [
                wheel_python,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--disable-pip-version-check",
                str(wheel),
            ],
            work,
        )

        life = work / "life.txt"
        life.write_text(
            "[ ] T Review release evidence id:smoke-1 project:release\n",
            encoding="utf-8",
        )
        expected_hash = hashlib.sha256(life.read_bytes()).hexdigest()
        requests = (
            "\n".join(
                [
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "resources/list",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 3,
                            "method": "resources/read",
                            "params": {"uri": "lifetxt://source/0"},
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 4,
                            "method": "tools/call",
                            "params": {"name": "list_items", "arguments": {}},
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 5,
                            "method": "unknown/method",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 6,
                            "method": "tools/call",
                            "params": {
                                "name": "create_item",
                                "arguments": {
                                    "title": "blocked",
                                    "expected_file_hash": expected_hash,
                                },
                            },
                        }
                    ),
                    json.dumps(
                        {"jsonrpc": "2.0", "id": 7, "method": "ping", "params": {}}
                    ),
                ]
            )
            + "\n"
        )
        result = _run(
            [wheel_python, "-m", "lifetxt", "mcp", "--read-only", str(life)],
            work,
            requests,
        )
        responses = {
            item["id"]: item
            for item in (
                json.loads(line) for line in result.stdout.splitlines() if line.strip()
            )
        }
        init = responses[1]["result"]
        _assert(init["serverInfo"]["name"] == "lifetxt-mcp", "MCP identity mismatch")
        _assert(init["serverInfo"]["version"], "MCP version missing")
        _assert(
            responses[2]["result"]["resources"][0]["uri"] == "lifetxt://source/0",
            "resource list mismatch",
        )
        _assert(
            "Review release evidence" in responses[3]["result"]["contents"][0]["text"],
            "resource read mismatch",
        )
        _assert(
            responses[4]["result"]["content"], "stable read tool returned no result"
        )
        _assert(
            responses[5]["error"]["code"] == -32601, "unknown method was not bounded"
        )
        write_error = responses[6]["error"]
        _assert("read-only" in write_error["message"].lower(), "write was not rejected")
        _assert(responses[7]["result"] == {}, "server did not continue after error")
        return {
            "ok": True,
            "artifact": wheel.name,
            "sha256": digest,
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "checks": [
                "initialize",
                "resources/list",
                "resources/read",
                "read-tool",
                "bounded-error",
                "read-only-write-rejection",
            ],
        }
    finally:
        shutil.rmtree(str(work), ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    args = parser.parse_args()
    print(json.dumps(run(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
