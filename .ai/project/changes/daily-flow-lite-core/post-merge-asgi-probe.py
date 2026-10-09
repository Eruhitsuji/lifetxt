import asyncio
import json
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
from datetime import datetime, timezone
from lifetxt.webapp import create_app


async def request(app, path, query, headers=()):
    sent = []
    called = False

    async def receive():
        nonlocal called
        if not called:
            called = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Future()

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": urlencode(query).encode(),
        "headers": list(headers),
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "root_path": "",
    }
    await asyncio.wait_for(app(scope, receive, send), 10)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in sent if m["type"] == "http.response.body"
    )
    return status, json.loads(body)


async def main():
    with tempfile.TemporaryDirectory() as name:
        path = Path(name) / "life.txt"
        path.write_text(
            "#! timezone: Asia/Tokyo\n[ ] E Meeting id:meeting from:2031-02-03T09:00 to:2031-02-03T10:00\n[ ] T Work id:work est:1h\n"
        )
        before = path.read_bytes()
        config = {
            "defaults": {"timezone": "Asia/Tokyo"},
            "api": {"token": "audit-token"},
        }
        app = create_app(paths=[str(path)], config=config, read_only=True)
        inventory = sorted(p.name for p in path.parent.iterdir())
        params = {"date": "2031-02-03", "day_start": "09:00", "day_end": "17:00"}
        with patch(
            "lifetxt.daily_flow_web._read",
            side_effect=AssertionError("Unauthorized source read"),
        ):
            status, body = await request(app, "/api/daily-flow", params)
            assert status == 401
        headers = ((b"authorization", b"Bearer audit-token"),)
        with patch(
            "lifetxt.daily_flow_web.now",
            return_value=datetime(2031, 2, 2, tzinfo=timezone.utc),
        ):
            status, body = await request(app, "/api/daily-flow", params, headers)
        assert status == 200 and body["completeness"]["state"] == "complete"
        assert [row["kind"] for row in body["timeline"]] == ["fixed", "candidate"]
        assert str(path) not in json.dumps(body)
        assert (
            path.read_bytes() == before
            and sorted(p.name for p in path.parent.iterdir()) == inventory
        )
        status, body = await request(
            app, "/api/daily-flow", {**params, "day_end": "08:00"}, headers
        )
        assert status == 400 and str(path) not in json.dumps(body)
        path.write_bytes(b"\xff")
        with patch(
            "lifetxt.daily_flow_web.now",
            return_value=datetime(2031, 2, 2, tzinfo=timezone.utc),
        ):
            status, body = await request(app, "/api/daily-flow", params, headers)
        assert (
            status == 200
            and body["completeness"]["state"] == "blocked"
            and body["timeline"] == []
        )
        assert str(path) not in json.dumps(body)
        assert (
            path.read_bytes() == b"\xff"
            and sorted(p.name for p in path.parent.iterdir()) == inventory
        )
        print(
            "PASS: direct ASGI 4 requests: denied auth before read, canonical authorized read-only plan, generic invalid-window error, corrupt-input blocked result; byte/inventory unchanged"
        )


asyncio.run(main())
