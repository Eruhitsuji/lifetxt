"""Local JS checker candidate, including opt-in real Chromium acceptance."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from scripts.build_js_checker_site import CSP, ROOT, build_candidate
from scripts.build_website import build
from scripts.check_website import check


class JSCheckerSiteTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.site = self.root / "lifetxt"
        build_candidate(self.site)

    def test_candidate_only_adds_expected_files_and_home_links(self):
        intro = self.root / "intro"
        build(intro)
        self.assertEqual(check(intro), [])
        baseline = {p.relative_to(intro).as_posix() for p in intro.rglob("*") if p.is_file()}
        candidate = {p.relative_to(self.site).as_posix() for p in self.site.rglob("*") if p.is_file()}
        self.assertEqual(candidate - baseline, {
            "en/check/index.html", "ja/check/index.html", "js-checker/ui.mjs",
            "js-checker/parser.mjs", "js-checker/checker.css", "js-checker/LICENSE.txt",
        })
        self.assertEqual(baseline - candidate, set())
        self.assertEqual(
            (self.site / "js-checker/parser.mjs").read_bytes(),
            (ROOT / "contrib/lifetxt-js-check/parser.mjs").read_bytes(),
        )
        for name in baseline - {"index.html", "ja/index.html", "en/index.html"}:
            self.assertEqual((self.site / name).read_bytes(), (intro / name).read_bytes(), name)
        for name, href in (("index.html", "en/check/"), ("ja/index.html", "check/"), ("en/index.html", "check/")):
            html = (self.site / name).read_text(encoding="utf-8")
            self.assertIn(f'href="{href}"', html)
            self.assertNotIn("<script", html)
        for lang in ("ja", "en"):
            page = (self.site / lang / "check/index.html").read_text(encoding="utf-8")
            self.assertIn(CSP, page)
            self.assertEqual(page.count("<script"), 1)
            self.assertIn('<script type="module" src="../../js-checker/ui.mjs">', page)
            self.assertNotIn("<form", page)

    def test_rejects_existing_output(self):
        with self.assertRaises(FileExistsError):
            build_candidate(self.site)

    @unittest.skipUnless(os.environ.get("LIFETXT_JS_CHECKER_CHROMIUM"), "Chromium not configured")
    def test_bilingual_chromium(self):
        from playwright.sync_api import expect, sync_playwright

        handler = partial(SimpleHTTPRequestHandler, directory=str(self.root))
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}/lifetxt"
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        executable_path=os.environ["LIFETXT_JS_CHECKER_CHROMIUM"],
                        args=["--no-sandbox"],
                    )
                    for lang in ("ja", "en"):
                        with self.subTest(lang=lang):
                            self.check_page(browser, origin, lang, expect)
                    context = browser.new_context(java_script_enabled=False)
                    page = context.new_page()
                    page.goto(f"{origin}/ja/check/")
                    expect(page.locator("noscript")).to_be_visible()
                    expect(page.locator("#check")).to_be_disabled()
                    context.close()
                    browser.close()
            finally:
                server.shutdown()
                thread.join()

    def check_page(self, browser, origin, lang, expect):
        context = browser.new_context()
        try:
            context.add_init_script("""
                window.writes = [];
                for (const [obj, key] of [[Storage.prototype, 'setItem'],
                                          [indexedDB, 'open'], [caches, 'open']]) {
                    const original = obj[key];
                    obj[key] = function(...args) {
                        window.writes.push(key);
                        return original.apply(this, args);
                    };
                }
                window.violations = [];
                document.addEventListener('securitypolicyviolation', e => {
                    window.violations.push(e.violatedDirective);
                });
            """)
            page = context.new_page()
            errors = []
            requests = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            context.on("request", lambda request: requests.append((request.url, request.method, request.post_data)))
            page.goto(f"{origin}/{lang}/")
            expect(page.locator("script")).to_have_count(0)
            page.locator('a[href="check/"]').click()
            expect(page.locator("html")).to_have_attribute("lang", lang)
            expect(page.locator("#check")).to_be_enabled()
            text = page.locator("#input")
            button = page.locator("#check")
            output = page.locator("#output")
            status = page.locator("#status")
            text.fill('[N] N "日本語😀"\n| 続き')
            button.press("Enter")
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            text.fill('[ ] T "unfinished')
            expect(status).to_be_empty()
            expect(output).to_be_empty()
            button.click()
            expect(output).to_contain_text("unclosed-quote")
            text.fill('[ ] T item \\' + '\n  tag:a\nbad')
            button.click()
            expect(output).to_contain_text("line-join")
            expect(output).to_contain_text("invalid-item-start")
            expect(status).to_contain_text("検査対象外" if lang == "ja" else "not checked")
            text.fill('#' + 'あ' * 5461)
            button.click()
            expect(output).to_be_empty()
            text.fill('#' + 'あ' * 5461 + 'x')
            button.click()
            expect(output).to_contain_text("input-too-large")
            text.fill("bad\n" * 101)
            button.click()
            self.assertEqual(output.inner_text().count("invalid-item-start"), 100)
            expect(output).to_contain_text("1件" if lang == "ja" else "1 additional")
            self.assertEqual(
                page.evaluate("[localStorage.length, sessionStorage.length]"), [0, 0]
            )
            self.assertEqual(page.evaluate("window.writes"), [])
            self.assertEqual(page.evaluate("window.violations"), [])
            self.assertEqual(context.cookies(), [])
            self.assertEqual(errors, [])
            self.assertTrue(requests)
            for url, method, body in requests:
                self.assertTrue(url.startswith(origin + "/"), url)
                self.assertNotIn("?", url)
                self.assertEqual(method, "GET")
                self.assertIsNone(body)
        finally:
            context.close()
