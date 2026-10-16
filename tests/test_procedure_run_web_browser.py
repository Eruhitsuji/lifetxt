"""Real HTTP/browser run operations, conflicts, reload and uncertain receipt recovery."""

import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from tests.test_procedure_definition import SAMPLE
from tests.test_web_planner_browser import browser_path


class ProcedureRunBrowserTests(unittest.TestCase):
    def test_explicit_run_mobile_tabs_reload_and_lost_response(self):
        try:
            import uvicorn
            from playwright.sync_api import sync_playwright, expect
        except ImportError:
            self.skipTest("Optional Web/Playwright unavailable")
        with sync_playwright() as pw:
            executable = browser_path() or pw.chromium.executable_path
            if not Path(executable).is_file():
                if os.environ.get("LIFETXT_REQUIRE_PROCEDURE_BROWSER") == "1":
                    self.fail("Required procedure browser unavailable")
                self.skipTest("Optional Chromium unavailable")
            from lifetxt import bootstrap_legacy_surfaces

            bootstrap_legacy_surfaces()
            from lifetxt.webapp import create_app
            from lifetxt.procedure_run_store import read_log

            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "life.txt"
                source.write_text(SAMPLE, encoding="utf-8")
                log = Path(str(source) + ".procedure-runs.txt")
                config = {
                    "api": {"token": "browser-run-token"},
                    "web": {"revision_mode": "required"},
                    "clock": {"require_remote_write_time": True},
                }
                app = create_app(
                    [str(source)], writable_path=str(source), config=config
                )
                sock = socket.socket()
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
                server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
                thread = threading.Thread(
                    target=server.run, kwargs={"sockets": [sock]}, daemon=True
                )
                thread.start()
                deadline = time.monotonic() + 10
                while not server.started and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(server.started)
                browser = None
                try:
                    browser = pw.chromium.launch(
                        executable_path=executable, headless=True, args=["--no-sandbox"]
                    )
                    context = browser.new_context(
                        viewport={"width": 390, "height": 844}
                    )
                    page = context.new_page()
                    errors, posts = [], []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.on("dialog", lambda dialog: dialog.accept())
                    page.on(
                        "request",
                        lambda req: (
                            posts.append(req.post_data_json)
                            if req.method == "POST"
                            and req.url.endswith("/api/procedure-runs")
                            else None
                        ),
                    )
                    origin = "http://127.0.0.1:%d" % port

                    def sign_in(p):
                        p.fill("#operator-token", "browser-run-token")
                        p.locator('#operator-login button[type="submit"]').click()
                        expect(p.locator("#operator-token")).to_have_value("")

                    def action(p, operation, choice=None):
                        selector = (
                            '#run-actions button[data-operation="%s"]' % operation
                        )
                        if choice:
                            selector += '[data-choice="%s"]' % choice
                        if operation == "next":
                            p.locator(selector).focus()
                            p.keyboard.press("Enter")
                        else:
                            p.locator(selector).click()

                    def status(p, text):
                        expect(p.locator("#run-state")).to_contain_text(
                            text, timeout=10000
                        )
                        expect(p.locator("#run-state")).not_to_contain_text(
                            "未開始", timeout=10000
                        )

                    page.goto(origin + "/procedures?lang=ja")
                    self.assertFalse(log.exists())
                    sign_in(page)
                    page.locator("#catalog a").first.click()
                    page.wait_for_selector(
                        '#run-actions button[data-operation="start"]'
                    )
                    self.assertFalse(log.exists())
                    # Two synchronous click attempts: the first disables the entire group.
                    page.evaluate(
                        "() => {const b=document.querySelector('[data-operation=start]');b.click();b.click();}"
                    )
                    status(page, "現在のステップ: a")
                    first = next(iter(read_log(log).states))
                    self.assertEqual(1, len(posts))
                    self.assertEqual(1, read_log(log).states[first].sequence)
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), 390
                    )
                    self.assertIn("run=" + first, page.url)
                    self.assertEqual(
                        {},
                        page.evaluate(
                            "Object.fromEntries(Object.entries(localStorage).filter(([k,v])=>v.includes('browser-run-token')))"
                        ),
                    )
                    self.assertEqual(
                        0,
                        page.evaluate(
                            "Object.values(sessionStorage).filter(v=>v.includes('browser-run-token')).length"
                        ),
                    )

                    other = context.new_page()
                    other.set_viewport_size({"width": 1280, "height": 844})
                    other.on("pageerror", lambda e: errors.append(str(e)))
                    other.goto(page.url)
                    sign_in(other)
                    other.wait_for_selector(
                        '#run-actions button[data-operation="next"]'
                    )
                    action(page, "next")
                    status(page, "現在のステップ: q")
                    action(other, "next")
                    other.wait_for_selector("#run-receipt:not([hidden])")
                    self.assertEqual(2, read_log(log).states[first].sequence)
                    other.locator("#run-receipt").click()
                    expect(other.locator("#run-feedback")).to_contain_text(
                        "見つかりません"
                    )
                    other.locator("#run-reload").click()
                    status(other, "現在のステップ: q")
                    self.assertEqual(2, read_log(log).states[first].sequence)

                    action(page, "pause")
                    status(page, "中断中")
                    page.reload()
                    self.assertTrue(page.locator("#run-panel").is_hidden())
                    self.assertEqual(3, read_log(log).states[first].sequence)
                    sign_in(page)
                    page.wait_for_selector(
                        '#run-actions button[data-operation="resume"]'
                    )
                    action(page, "resume")
                    status(page, "実施中")

                    def lose_response(route):
                        route.fetch()
                        route.abort("connectionreset")

                    page.route("**/api/procedure-runs", lose_response, times=1)
                    action(page, "choose", "yes")
                    page.wait_for_selector("#run-receipt:not([hidden])")
                    self.assertEqual("e", read_log(log).states[first].cursor.step)
                    count = len(read_log(log).events)
                    page.locator("#run-receipt").click()
                    expect(page.locator("#run-feedback")).to_contain_text(
                        "記録されています"
                    )
                    self.assertEqual(count, len(read_log(log).events))
                    action(page, "finish")
                    status(page, "完了")
                    self.assertEqual(
                        "completed", read_log(log).states[first].cursor.status
                    )
                    page.locator("#run-new").click()
                    page.wait_for_selector(
                        '#run-actions button[data-operation="start"]'
                    )

                    def malformed_success(route):
                        route.fetch()
                        route.fulfill(
                            status=200, content_type="application/json", body="{}"
                        )

                    page.route("**/api/procedure-runs", malformed_success, times=1)
                    action(page, "start")
                    page.wait_for_selector("#run-receipt:not([hidden])")
                    self.assertEqual(2, len(read_log(log).states))
                    page.locator("#run-receipt").click()
                    expect(page.locator("#run-feedback")).to_contain_text(
                        "記録されています"
                    )
                    status(page, "現在のステップ: a")
                    self.assertEqual(2, len(read_log(log).states))
                    second = next(run for run in read_log(log).states if run != first)
                    source.write_text("invalid changed definition", encoding="utf-8")
                    page.locator("#run-reload").click()
                    expect(page.locator("#run-feedback")).to_contain_text("定義が変更")
                    self.assertEqual(
                        {"pause", "abandon"},
                        set(
                            page.locator("#run-actions button").evaluate_all(
                                "nodes => nodes.map(n=>n.dataset.operation)"
                            )
                        ),
                    )
                    action(page, "abandon")
                    status(page, "打切り")
                    self.assertEqual(
                        "abandoned", read_log(log).states[second].cursor.status
                    )
                    self.assertEqual(
                        "completed", read_log(log).states[first].cursor.status
                    )
                    page.locator("#operator-signout").click()
                    self.assertTrue(page.locator("#run-panel").is_hidden())
                    self.assertEqual("", page.input_value("#operator-token"))
                    self.assertFalse(errors, errors)
                    self.assertEqual(
                        "invalid changed definition", source.read_text(encoding="utf-8")
                    )
                finally:
                    if browser:
                        browser.close()
                    server.should_exit = True
                    thread.join(10)
                    sock.close()
                self.assertFalse(thread.is_alive())
