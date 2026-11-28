"""Local JS checker candidate, including opt-in real Chromium acceptance."""

from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from lifetxt.attachments import hash_directory
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
            self.assertIn(f'<a class="button" href="{href}">', html)
            self.assertEqual(html.count(f'href="{href}"'), 1)
            self.assertNotIn(f'href="{href}"', (intro / name).read_text(encoding="utf-8"))
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
                    context = browser.new_context(
                        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
                    )
                    for home, href, destination in (
                        ("", "en/check/", "en/check/"),
                        ("ja/", "check/", "ja/check/"),
                        ("en/", "check/", "en/check/"),
                    ):
                        with self.subTest(mobile=home):
                            page = context.new_page()
                            page.goto(f"{origin}/{home}")
                            checker = page.locator(f'main .hero .actions a[href="{href}"]')
                            expect(checker).to_be_in_viewport()
                            checker.tap()
                            expect(page).to_have_url(f"{origin}/{destination}")
                            expect(page.locator("#lesson h2")).to_be_visible()
                            self.assertTrue(page.evaluate(
                                "document.documentElement.scrollWidth === window.innerWidth"
                            ))
                            page.locator("#load-sample").tap()
                            expect(page.locator("#input")).to_be_focused()
                            page.locator("#check").tap()
                            expect(page.locator("#status")).not_to_be_empty()
                            page.close()
                    context.close()
                    context = browser.new_context(java_script_enabled=False)
                    page = context.new_page()
                    page.goto(f"{origin}/ja/check/")
                    expect(page.locator("noscript")).to_be_visible()
                    expect(page.locator("#check")).to_be_disabled()
                    expect(page.locator("#load-sample")).to_be_disabled()
                    expect(page.locator("#files")).to_be_disabled()
                    expect(page.locator("#checker-config")).to_be_disabled()
                    expect(page.locator("#attachment-folder")).to_be_disabled()
                    expect(page.locator("#verify-attachment-hashes")).to_be_disabled()
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
            page.locator('main .hero .actions a[href="check/"]').click()
            expect(page.locator("html")).to_have_attribute("lang", lang)
            expect(page.locator("#check")).to_be_enabled()
            text = page.locator("#input")
            button = page.locator("#check")
            output = page.locator("#output")
            status = page.locator("#status")
            example = (ROOT / "website/example.txt").read_text(encoding="utf-8")
            expect(page.locator("#lesson pre")).to_have_text(example.splitlines()[0])
            expect(page.locator("#lesson dt")).to_have_count(4)
            sample = page.locator("#load-sample")
            sample.press("Enter")
            expect(text).to_be_focused()
            expect(text).to_have_value(example)
            text.fill(example.replace("Plan next week", "My first task"))
            text.press("Tab")
            expect(button).to_be_focused()
            button.press("Enter")
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            expect(sample).to_be_disabled()
            text.fill("")
            expect(sample).to_be_enabled()
            text.fill('[N] N "日本語😀"\n| 続き')
            button.press("Enter")
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            text.fill("[ ] T Example due:2026-02-30")
            button.click()
            expect(status).to_contain_text("lifetxt check")
            expect(output).to_contain_text("invalid-date-or-datetime")
            expect(output).to_contain_text("due:")
            expect(output).to_contain_text("警告" if lang == "ja" else "Warning")
            text.fill("[ ] T Example due:2024-02-29 at:08:30:15.1+09:00")
            button.click()
            expect(output).to_be_empty()
            text.fill("[ ] T Example due:json<< [null] >>")
            button.click()
            expect(output).to_contain_text("detail-expects-text")
            expect(output).to_contain_text("エラー" if lang == "ja" else "Error")
            text.fill("[ ] E Example from:2026-12-01T10:00+09:00 to:2026-12-01T00:30Z")
            button.click()
            expect(output).to_contain_text("event-end-before-start")
            expect(output).to_contain_text("to:")
            expect(output).to_contain_text("警告" if lang == "ja" else "Warning")
            text.fill("[ ] E Example from:2026-12-01T10:00+09:00 to:2026-12-01T01:00Z")
            button.click()
            expect(output).to_be_empty()
            text.fill("[ ] E Example repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3 interval:2")
            button.click()
            expect(output).to_be_empty()
            text.fill("[ ] E Example repeat:RRULE:FREQ=WEEKLY;BYMONTHDAY=1 count:0")
            button.click()
            expect(output).to_contain_text("invalid-rrule")
            expect(output).to_contain_text("repeat: [BYMONTHDAY]")
            expect(output).to_contain_text("expected-positive-integer")
            expect(output).to_contain_text("count:")
            text.fill('[ ] T Review id:review\n[ ] T Proxy id:proxy\n'
                      '[ ] T Submit requires:review=done requires:json<< {"any":["proxy=[x]"]} >>')
            button.click()
            expect(output).to_be_empty()
            text.fill("[ ] T Submit requires:review=finished")
            button.click()
            expect(output).to_contain_text("invalid-requires")
            expect(output).to_contain_text("requires:")
            expect(output).to_contain_text("状態名" if lang == "ja" else "state names")
            text.fill('[ ] T First id:report\n[ ] T Next id:report id:"has space"')
            button.click()
            expect(output).to_contain_text("invalid-id")
            expect(output).to_contain_text("duplicate-id")
            expect(output).to_contain_text('"report"')
            expect(output).to_contain_text("1行目" if lang == "ja" else "line 1")
            text.fill("[ ] T Source id:self ref:old parent:self requires:report=done\n"
                      "[ ] T Report id:report\n[ ] T Another id:report")
            button.click()
            expect(output).to_contain_text("missing-reference")
            expect(output).to_contain_text('ID "old"')
            expect(output).to_contain_text("self-reference")
            expect(output).to_contain_text("ambiguous-reference")
            expect(output).to_contain_text('ID "report"')
            text.fill("[ ] T A id:a depends_on:b blocks:b\n[ ] T B id:b")
            button.click()
            expect(output).to_contain_text("reference-cycle")
            expect(output).to_contain_text("depends_on:")
            expect(output).to_contain_text('"a" → "b" → "a"')
            text.fill("[ ] T Old id:old on:2026-10-10\n"
                      "[ ] T New id:new on:2026-10-08 follows:old")
            button.click()
            expect(output).to_contain_text("temporal-reference-order")
            expect(output).to_contain_text('follows: ID "old"' if lang == "ja" else 'ID "old"')
            text.fill("[x] T Parent id:p done:2026-10-01 depends_on:child\n"
                      "  [ ] T Child id:child")
            button.click()
            expect(output).to_contain_text("completed-with-open-dependency")
            expect(output).to_contain_text("closed-parent-with-open-children")
            expect(output).to_contain_text("1 件" if lang == "ja" else "1 open child")
            text.fill("[/] S Working from:2026-10-01T09:00 state:focus")
            button.click()
            expect(output).to_be_empty()
            text.fill("[ ] S Working")
            button.click()
            expect(output).to_contain_text("status-missing-from")
            expect(output).to_contain_text("status-missing-state")
            expect(output).to_contain_text("status-open-marker")
            text.fill("[ ] M Reminder sender:self recipient:alice notify_from:2026-10-01 notify_to:2026-10-01")
            button.click()
            expect(output).to_be_empty()
            text.fill("[ ] M Reminder notify_from:2026-10-02 notify_to:2026-10-01")
            button.click()
            expect(output).to_contain_text("message-missing-sender")
            expect(output).to_contain_text("message-missing-recipient")
            expect(output).to_contain_text("notification-end-before-start")
            text.fill("[ ] T Work id:work progress:120%\n"
                      "[N] N Event record:progress_event parent:work")
            button.click()
            expect(output).to_contain_text("invalid-progress")
            expect(output).to_contain_text("progress-event-missing")
            expect(output).to_contain_text("progress-event-timestamp")
            text.fill("[ ] T Work id:work\n"
                      "[N] N Event record:item_event parent:work event:completed")
            button.click()
            expect(output).to_contain_text("item-event-missing")
            expect(output).to_contain_text("item-event-payload")
            expect(output).to_contain_text("item-event-timestamp")
            text.fill("[ ] J Journal\n[x] T Finished\n[/] T Ongoing done:2026-11-27")
            button.click()
            expect(output).to_contain_text("note-item-with-workflow-marker")
            expect(output).to_contain_text("completed-item-missing-done")
            expect(output).to_contain_text("done-without-completed-marker")
            text.fill("[ ] T Work est:90 elapsed:bad importance:high importance:low")
            button.click()
            expect(output).to_contain_text("[1h30m]")
            expect(output).to_contain_text("invalid-duration")
            expect(output).to_contain_text("invalid-importance")
            text.fill('[ ] T "unfinished')
            expect(status).to_be_empty()
            expect(output).to_be_empty()
            button.click()
            expect(output).to_contain_text("unclosed-quote")
            text.fill('[ ] T item \\' + '\n  tag:a\n| body')
            button.click()
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            expect(output).to_be_empty()
            text.fill('[ ] T item \\' + '\n  tag:a\\\n')
            button.click()
            expect(output).to_contain_text("dangling-line-join")
            expect(output).to_contain_text("2行" if lang == "ja" else "Line 2")
            text.fill('[ ] T item options:json<<\n\t{"text":"a >> b"}\n>> tag:after')
            button.click()
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            expect(output).to_contain_text("custom-detail-key")
            expect(output).to_contain_text("options:")
            expect(output).to_contain_text("値は保持されます" if lang == "ja" else "values are preserved")
            text.fill('[ ] T Item <Key>:yes owner:json<< true >>')
            button.click()
            expect(output).to_contain_text("detail-key-style")
            expect(output).to_contain_text("<Key>:")
            expect(output.locator("key")).to_have_count(0)
            expect(output).to_contain_text("detail-expects-text")
            expect(output).to_contain_text("owner:")
            text.fill('[ ] T item options:json<<\n ["a",]\n>>\n[ ] T next')
            button.click()
            expect(output).to_contain_text("invalid-json-detail")
            expect(output).to_contain_text("1行" if lang == "ja" else "Line 1")
            expect(output).not_to_contain_text("invalid-item-start")
            text.fill('[ ] T item options:json<< 9007199254740993 >>')
            button.click()
            expect(output).to_contain_text("json-integer-precision")
            expect(status).to_contain_text("検査対象外" if lang == "ja" else "not checked")
            text.fill("  [ ] T Orphan\n[ ] T Root\n  [ ] T Child")
            button.click()
            expect(output).to_contain_text("1行" if lang == "ja" else "Line 1")
            expect(output).to_contain_text("indent-no-parent")
            expect(output).to_contain_text("3行" if lang == "ja" else "Line 3")
            expect(output).to_contain_text("indent-parent-no-id")
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            text.fill("[ ] T Root id:root\n  [ ] T Child")
            button.click()
            expect(output).to_be_empty()
            text.fill("#! format_version: 2")
            button.click()
            expect(output).to_contain_text("unsupported-format")
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
            text.fill("[ ] T Paste-survives")
            files = page.locator("#files")
            clear_files = page.locator("#clear-files")
            expect(clear_files).to_be_disabled()
            files.set_input_files([
                {"name": "inbox.txt", "mimeType": "text/plain",
                 "buffer": b"[ ] T A id:a depends_on:b\n[ ] T First id:dup"},
                {"name": "work.txt", "mimeType": "text/plain",
                 "buffer": b"[ ] T B id:b depends_on:a\n[ ] T Second id:dup"},
            ])
            expect(text).to_be_disabled()
            expect(status).to_be_empty()
            button.click()
            expect(output).to_contain_text("reference-cycle")
            expect(output).to_contain_text("duplicate-id")
            expect(output).not_to_contain_text("missing-reference")
            expect(output).to_contain_text('"work.txt" の2行目' if lang == "ja" else '"work.txt", line 2')
            expect(output).to_contain_text('"inbox.txt" の2行目' if lang == "ja" else '"inbox.txt", line 2')
            clear_files.click()
            expect(text).to_be_focused()
            expect(text).to_have_value("[ ] T Paste-survives")
            expect(output).to_be_empty()
            button.click()
            expect(output).to_be_empty()
            for name, payload, message in (
                ("invalid.txt", b"\xff", "UTF-8"),
                ("large.txt", b"x" * 16_385, "16 KiB"),
            ):
                files.set_input_files({"name": name, "mimeType": "text/plain", "buffer": payload})
                button.click()
                expect(status).to_contain_text(name)
                expect(status).to_contain_text(message)
                expect(output).to_be_empty()
            files.set_input_files([
                {"name": f"file-{i}.txt", "mimeType": "text/plain", "buffer": b""}
                for i in range(65)
            ])
            button.click()
            expect(status).to_contain_text("64")
            expect(output).to_be_empty()

            clear_files.click()
            page.locator("#checker-settings summary").click()
            config = page.locator("#checker-config")
            clear_config = page.locator("#clear-config")
            expect(clear_config).to_be_disabled()
            text.fill("[ ] T Target uid:a\n[ ] T Lookup ref:a")
            button.click()
            expect(output).to_contain_text("missing-reference")
            config.set_input_files({
                "name": "settings.json", "mimeType": "application/json",
                "buffer": b'\xef\xbb\xbf{"ids":{"key":"uid"},"api":{"id_key":"source"}}',
            })
            button.click()
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            expect(output).to_be_empty()
            files.set_input_files([
                {"name": "target.txt", "mimeType": "text/plain", "buffer": b"[ ] T Target uid:a"},
                {"name": "lookup.txt", "mimeType": "text/plain", "buffer": b"[ ] T Lookup ref:a"},
            ])
            button.click()
            expect(status).to_contain_text("見つかりません" if lang == "ja" else "No errors found")
            expect(output).to_be_empty()
            clear_config.click()
            button.click()
            expect(output).to_contain_text("missing-reference")
            clear_files.click()
            for payload, message in (
                (b'{"ids":{"key":5}}', "無効" if lang == "ja" else "invalid configuration"),
                (b"invalid", "無効" if lang == "ja" else "invalid configuration"),
                (b"\xff", "UTF-8"),
                (b" " * 16_385, "16 KiB"),
            ):
                config.set_input_files({
                    "name": "bad-settings.json", "mimeType": "application/json", "buffer": payload,
                })
                button.click()
                expect(status).to_contain_text("bad-settings.json")
                expect(status).to_contain_text(message)
                expect(output).to_be_empty()
            clear_config.click()
            folder = page.locator("#attachment-folder")
            clear_folder = page.locator("#clear-folder")
            verify_hashes = page.locator("#verify-attachment-hashes")
            expect(verify_hashes).not_to_be_checked()
            text.fill("[ ] T Docs file:docs/report.bin#sha256=ABCD dir:docs")
            button.click()
            expect(output).to_contain_text("attachment-folder-unavailable")
            expect(status).to_contain_text("検査対象外" if lang == "ja" else "not checked")
            expect(clear_folder).to_be_disabled()
            with TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "docs").mkdir()
                (root / "empty").mkdir()
                (root / "docs/report.bin").write_bytes(b"\xff")
                folder.set_input_files(root)
                expect(output).to_be_empty()
                button.click()
                expect(output).to_be_empty()
                text.fill(
                    "[ ] T Bad file:missing file:docs dir:docs/report.bin "
                    "dir:empty file:../outside file:/absolute file:docs/report.bin#sha256=xyz"
                )
                button.click()
                expect(output).to_contain_text("attachment-missing")
                expect(output).to_contain_text("attachment-directory-unobserved")
                expect(output).to_contain_text("attachment-outside-folder")
                expect(output).to_contain_text("attachment-invalid-value")
                self.assertEqual(output.inner_text().count("attachment-wrong-type"), 2)
                files.set_input_files({
                    "name": "inbox.txt", "mimeType": "text/plain",
                    "buffer": b"[ ] T Docs file:docs/report.bin dir:. file:missing",
                })
                button.click()
                expect(output).to_contain_text("attachment-missing")
                expect(output).to_contain_text('"inbox.txt"')
                self.assertEqual(len(output.inner_text().splitlines()), 1)
                clear_files.click()
                with (root / "docs/large.bin").open("wb") as large:
                    large.truncate(200 * 1024 * 1024 + 1)
                hashed_tree = root / "tree"
                (hashed_tree / "nested").mkdir(parents=True)
                (hashed_tree / ".git").mkdir()
                (hashed_tree / "nested/ä.txt").write_bytes(b"nested")
                (hashed_tree / "𐀀.txt").write_bytes(b"supplementary")
                (hashed_tree / "Ａ.txt").write_bytes(b"fullwidth")
                (hashed_tree / ".git/ignored").write_bytes(b"ignored")
                tree_digest = hash_directory(hashed_tree, length=64)
                folder.set_input_files(root)
                page.evaluate("""() => {
                    window.readAttachments = [];
                    window.originalArrayBuffer = File.prototype.arrayBuffer;
                    File.prototype.arrayBuffer = function () {
                        window.readAttachments.push(this.name);
                        return window.originalArrayBuffer.call(this);
                    };
                }""")
                digest = sha256(b"\xff").hexdigest()
                text.fill(
                    f"[ ] T Verify file:docs/report.bin#sha256={digest[:16].upper()} "
                    f"file:docs/report.bin#sha256={digest} file:docs/report.bin#sha256=ABCD "
                    "file:docs/large.bin#sha256=abcd dir:docs#sha256=abcd\n"
                    f"[ ] T Tree dir:tree#sha256={tree_digest[:16].upper()} dir:tree#sha256={tree_digest} "
                    "dir:tree#sha256=0000"
                )
                button.click()
                expect(output).to_be_empty()
                self.assertEqual(page.evaluate("window.readAttachments"), [])
                verify_hashes.check()
                button.click()
                expect(output).to_contain_text("attachment-hash-changed")
                expect(output).to_contain_text("attachment-hash-too-large")
                expect(output).to_contain_text("attachment-directory-limit")
                expect(status).to_contain_text("検査対象外" if lang == "ja" else "not checked")
                self.assertEqual(len(output.inner_text().splitlines()), 4)
                expect(output).to_contain_text(f"SHA-256 {tree_digest[:4]}")
                self.assertEqual(
                    page.evaluate("window.readAttachments"),
                    ["report.bin", "ä.txt", "Ａ.txt", "𐀀.txt"],
                )
                text.fill("[ ] T Empty dir:empty#sha256=0000")
                button.click()
                expect(output).to_contain_text("attachment-directory-unobserved")

                page.evaluate("""() => {
                    File.prototype.arrayBuffer = function () {
                        return new Promise(resolve => {
                            window.finishAttachmentRead = () => window.originalArrayBuffer.call(this).then(resolve);
                        });
                    };
                }""")
                text.fill("[ ] T Stale file:docs/report.bin#sha256=abcd")
                button.click()
                expect(button).to_be_disabled()
                clear_folder.click()
                page.evaluate("window.finishAttachmentRead()")
                expect(output).to_be_empty()
                expect(status).to_be_empty()
                expect(button).to_be_enabled()
                page.evaluate("() => { File.prototype.arrayBuffer = window.originalArrayBuffer; }")
                verify_hashes.uncheck()
                button.click()
                expect(output).to_contain_text("attachment-folder-unavailable")
            text.fill("[ ] T Paste-survives")

            # Hold a file read open until the selection is cleared.
            page.evaluate("""() => {
                const read = File.prototype.arrayBuffer;
                File.prototype.arrayBuffer = function () {
                    return new Promise(resolve => {
                        window.finishFileRead = () => read.call(this).then(resolve);
                    });
                };
            }""")
            files.set_input_files({"name": "stale.txt", "mimeType": "text/plain", "buffer": b"bad"})
            button.click()
            expect(button).to_be_disabled()
            clear_files.click()
            page.evaluate("window.finishFileRead()")
            expect(status).to_be_empty()
            expect(output).to_be_empty()
            expect(button).to_be_enabled()
            expect(text).to_have_value("[ ] T Paste-survives")
            config.set_input_files({
                "name": "stale-settings.json", "mimeType": "application/json", "buffer": b"invalid",
            })
            button.click()
            expect(button).to_be_disabled()
            text.fill("[ ] T Edited")
            page.evaluate("window.finishFileRead()")
            expect(status).to_be_empty()
            expect(output).to_be_empty()
            expect(button).to_be_enabled()
            clear_config.click()
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
            page.locator('a[href="../get-started.html"]').click()
            expect(page).to_have_url(f"{origin}/{lang}/get-started.html")
        finally:
            context.close()
