"""Fast release smoke tests for lifetxt.

This runner intentionally covers the main command and API surfaces without
replacing the full unittest suite.
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        work = Path(temp_dir)
        life = work / "life.txt"
        life.write_text(
            "\n".join(
                [
                    "[ ] T Write_Report id:task_001 due:2026-06-12 project:demo",
                    "[ ] E Standup id:event_001 from:2026-06-12T09:00 to:2026-06-12T09:15",
                    "[/] S Working id:status_001 from:2026-06-12T10:00 state:working person:self",
                    "[ ] M Ping id:msg_001 sender:self recipient:self notify_at:%s" % _now_text(),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        _run("check", str(life))

        json_path = work / "items.json"
        jsonl_path = work / "items.jsonl"
        csv_path = work / "items.csv"
        roundtrip_path = work / "roundtrip.life.txt"
        _run("to-json", str(life), "-o", str(json_path), "--pretty")
        _run("to-jsonl", str(life), "-o", str(jsonl_path))
        _run("to-csv", str(life), "-o", str(csv_path))
        _run("from-json", str(json_path), "-o", str(roundtrip_path))
        _run("check", str(roundtrip_path))
        _assert(json_path.exists() and json.loads(json_path.read_text(encoding="utf-8")), "JSON export is empty.")
        _assert(jsonl_path.read_text(encoding="utf-8").strip(), "JSONL export is empty.")
        _assert("Write_Report" in csv_path.read_text(encoding="utf-8"), "CSV export missed task.")

        half_open = work / "half_open.life.txt"
        half_open.write_text(
            "[ ] R Late notify_at:2026-06-12T23:59:59.5\n"
            "[ ] R Boundary notify_at:2026-06-13T00:00:00\n",
            encoding="utf-8",
        )
        agenda = _run(
            "agenda",
            str(half_open),
            "--from",
            "2026-06-12",
            "--to",
            "2026-06-12",
            "--format",
            "life",
        ).stdout
        _assert("Late" in agenda, "Half-open date range missed same-day fractional second.")
        _assert("Boundary" not in agenda, "Half-open date range included next-day boundary.")

        timer_state = work / "timer.json"
        config = work / "config.json"
        config.write_text(json.dumps({"timer": {"state_file": str(timer_state)}}), encoding="utf-8")
        _run("--config", str(config), "timer", "start", str(life), "--id", "task_001")
        _assert(timer_state.exists(), "Timer state file was not created.")
        _run("--config", str(config), "timer", "status", str(life))
        _run("--config", str(config), "timer", "cancel")
        _assert(not timer_state.exists(), "Timer cancel did not remove state file.")

        notify_state = work / "notifications.json"
        _run(
            "notify",
            str(life),
            "--recipient",
            "self",
            "--lookahead",
            "1h",
            "--grace",
            "1h",
            "--watch",
            "--once",
            "--state-file",
            str(notify_state),
        )
        state = json.loads(notify_state.read_text(encoding="utf-8"))
        _assert(state.get("seen"), "Notification seen-state was not persisted.")

        _mcp_smoke(life)
        _web_api_smoke(work)

    print("lifetxt smoke tests passed")
    return 0


def _run(*args):
    process = subprocess.run(
        [sys.executable, "-m", "lifetxt"] + list(args),
        cwd=str(ROOT),
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if process.returncode != 0:
        raise AssertionError(
            "Command failed: python -m lifetxt %s\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (" ".join(args), process.stdout, process.stderr)
        )
    return process


def _mcp_smoke(life):
    from lifetxt.mcp import McpContext, handle_request

    context = McpContext(paths=[str(life)], writable_path=str(life))
    result = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        context,
    )
    _assert(result["result"]["serverInfo"]["name"] == "lifetxt-mcp", "MCP initialize failed.")


def _web_api_smoke(work):
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:
        print("Skipping Web API smoke test: %s" % exc)
        return

    from lifetxt.webapp import create_app

    path = work / "web.life.txt"
    path.write_text("[ ] T Existing id:web_001\n", encoding="utf-8")
    client = TestClient(create_app([str(path)], writable_path=str(path)))
    response = client.get("/api/items?open_only=false")
    _assert(response.status_code == 200, "Web API items request failed.")
    response = client.post(
        "/api/items",
        json={"status": "[ ]", "type": "T", "title": "From_API", "details": {"id": ["web_002"]}},
    )
    _assert(response.status_code in (200, 201), "Web API write request failed.")

    read_only = TestClient(create_app([str(path)], writable_path=str(path), read_only=True))
    response = read_only.post(
        "/api/items",
        json={"status": "[ ]", "type": "T", "title": "Blocked", "details": {}},
    )
    _assert(response.status_code == 403, "Read-only Web API did not block write.")


def _now_text():
    return datetime.now().replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
