"""Optional real HTTP/browser checks for the shipped procedure definition UI."""

from pathlib import Path
import os
import socket
import tempfile
import threading
import time
import unittest

from tests.test_procedure_definition import SAMPLE
from tests.test_web_planner_browser import browser_path


class ProcedureBrowserTests(unittest.TestCase):
    def test_mobile_desktop_keyboard_xss_reload_and_large_text_alternative(self):
        try:
            import uvicorn
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Optional Web/Playwright dependencies unavailable")
        with sync_playwright() as playwright:
            executable = browser_path() or playwright.chromium.executable_path
            if not Path(executable).is_file():
                if os.environ.get("LIFETXT_REQUIRE_PROCEDURE_BROWSER") == "1":
                    self.fail("Required procedure browser unavailable")
                self.skipTest("Optional Chromium unavailable")
            from lifetxt import bootstrap_legacy_surfaces

            bootstrap_legacy_surfaces()
            from lifetxt.webapp import create_app

            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "definitions.txt"
                malicious = '<img src=x onerror="window.pwned=1">'
                source.write_text(SAMPLE + "| " + malicious + "\n", encoding="utf-8")
                app = create_app(paths=[str(source)], writable_path=str(source))
                server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
                sock = socket.socket()
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
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
                    browser = playwright.chromium.launch(
                        executable_path=executable, headless=True, args=["--no-sandbox"]
                    )
                    origin = "http://127.0.0.1:%s" % port
                    requests = []
                    page = browser.new_page()
                    page.on(
                        "request",
                        lambda request: requests.append((request.method, request.url)),
                    )
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    for width, lang in ((390, "ja"), (1280, "en")):
                        with self.subTest(width=width, lang=lang):
                            page.set_viewport_size({"width": width, "height": 844})
                            page.goto(origin + "/procedures?lang=" + lang)
                            page.locator("#catalog a").first.click()
                            page.wait_for_selector("#definition:not([hidden])")
                            self.assertEqual(4, page.locator("#steps > li").count())
                            self.assertIn(
                                "PG201", page.locator("#warnings").inner_text()
                            )
                            self.assertEqual(4, page.locator("#flow svg a").count())
                            self.assertEqual(0, page.locator("img").count())
                            self.assertIsNone(page.evaluate("window.pwned"))
                            self.assertIn(
                                malicious, page.locator("#steps").inner_text()
                            )
                            self.assertEqual(
                                lang, page.locator("html").get_attribute("lang")
                            )
                            self.assertLessEqual(
                                page.evaluate("document.documentElement.scrollWidth"),
                                width,
                            )
                            page.locator("#steps .step-links a").first.focus()
                            page.keyboard.press("Enter")
                            self.assertTrue(
                                page.evaluate(
                                    "document.activeElement.id.startsWith('procedure-step-')"
                                )
                            )
                            page.locator("details summary").click()
                            page.select_option("#format", "mermaid")
                            self.assertIn(
                                "flowchart TD", page.locator("#export").inner_text()
                            )
                            self.assertIn("source=", page.url)
                            self.assertIn("id=r", page.url)
                            old = page.locator("#meta").inner_text()
                            source.write_text(
                                source.read_text(encoding="utf-8") + "# revision\n",
                                encoding="utf-8",
                            )
                            page.reload()
                            page.wait_for_selector("#definition:not([hidden])")
                            self.assertNotEqual(old, page.locator("#meta").inner_text())
                    # Domain maximum is preserved without rendering an oversized SVG.
                    source.write_text(
                        "[N] N Root id:r proc_role:root proc_version:1 proc_start:s0\n"
                        + "".join(
                            "[N] N Step id:s%d parent:r proc_role:step proc_kind:action proc_next:s%d\n"
                            % (i, i + 1)
                            for i in range(499)
                        )
                        + "[N] N End id:s499 parent:r proc_role:step proc_kind:end\n",
                        encoding="utf-8",
                    )
                    page.reload()
                    page.wait_for_selector("#definition:not([hidden])")
                    self.assertEqual(500, page.locator("#steps > li").count())
                    self.assertEqual(0, page.locator("#flow svg").count())
                    self.assertIn("Large flowchart", page.locator("#flow").inner_text())
                    page.route(
                        "**/api/procedures",
                        lambda route: route.fulfill(
                            status=404, content_type="application/json", body="{}"
                        ),
                    )
                    page.goto(origin + "/procedures?lang=en")
                    page.wait_for_function(
                        "document.getElementById('feedback').textContent.includes('does not support')"
                    )
                    self.assertEqual(
                        origin + "/",
                        page.locator("header a").evaluate("node=>node.href"),
                    )
                    self.assertFalse(errors, errors)
                    self.assertEqual(
                        {"GET"}, {method for method, url in requests if "/api/" in url}
                    )
                    self.assertFalse(list(Path(directory).glob("*.procedure-runs.txt")))
                finally:
                    if browser:
                        browser.close()
                    server.should_exit = True
                    thread.join(timeout=10)
                    sock.close()
                self.assertFalse(thread.is_alive())
