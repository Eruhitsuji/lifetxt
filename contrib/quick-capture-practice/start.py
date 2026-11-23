"""Serve Quick Capture practice over loopback using only the standard library."""

import argparse
import json
import secrets
import sys
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))

from lifetxt.quick_input import resolve_quick_input
from lifetxt.serializer import item_to_line


def resolve(text, syntax, today):
    parsed = resolve_quick_input(text, syntax=syntax, today=today)
    item = parsed.item
    return {
        "mode": parsed.mode,
        "title": item.title,
        "status": item.status,
        "type": item.kind,
        "details": item.details,
        "line": item_to_line(item),
        "warnings": [
            f"{d.code} {d.message}" for d in parsed.diagnostics if d.severity == "warning"
        ],
    }


class PracticeHandler(BaseHTTPRequestHandler):
    def send_content(self, status, mime, data, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", f"practice={cookie}; SameSite=Strict; HttpOnly; Path=/")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, data):
        self.send_content(
            status, "application/json; charset=utf-8",
            json.dumps(data, ensure_ascii=True).encode("utf-8"),
        )

    def allowed_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_GET(self):
        if not self.allowed_host() or self.path != "/":
            self.send_error(404)
            return
        self.send_content(
            200, "text/html; charset=utf-8", self.server.page, cookie=self.server.token,
        )

    def do_POST(self):
        if not self.allowed_host() or self.path != "/resolve":
            self.send_error(404)
            return
        expected_cookie = f"practice={self.server.token}"
        cookies = [part.strip() for part in self.headers.get("Cookie", "").split(";")]
        if expected_cookie not in cookies or self.headers.get_content_type() != "application/json":
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("入力が長すぎるか、空です。")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("入力形式を確認してください。")
            text, syntax = data.get("text"), data.get("syntax")
            example, example_syntax = data.get("example"), data.get("exampleSyntax")
            if not isinstance(text, str) or syntax not in ("quick", "todo"):
                raise ValueError("入力形式を確認してください。")
            today = date.today()
            result = {"item": resolve(text, syntax, today)}
            if isinstance(example, str) and example_syntax in ("quick", "todo"):
                result["expected"] = resolve(example, example_syntax, today)
            self.send_json(200, result)
        except (ValueError, OverflowError, RecursionError) as error:
            self.send_json(400, {"error": str(error) or "入力を確認してください。"})

    def log_message(self, *_args):
        pass


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--port", type=int, default=0, help="Local port (default: automatically selected)")
    cli.add_argument("--no-browser", action="store_true", help="Print the address without opening it")
    args = cli.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), PracticeHandler) as server:
        server.page = (ROOT / "index.html").read_bytes()
        server.token = secrets.token_urlsafe(24)
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Quick Capture 練習室  {url}", flush=True)
        print("終了するには Ctrl+C を押してください。", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
