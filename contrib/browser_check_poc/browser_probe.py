"""Real HTTP/Chromium probe for #1360; never publishes or opens real records."""

import argparse
from functools import partial
import http.server
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            # Cancelling a worker deliberately abandons in-flight static assets.
            self.server.cancelled_transfers += 1


def run(directory, executable, output, screenshots=None):
    from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

    directory = directory.resolve()
    fixtures = json.loads((directory / "fixtures.json").read_text())
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(directory))
    )
    server.cancelled_transfers = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    evidence = {
        "kind": "actual headless Chromium over loopback HTTP",
        "physical_device": False,
        "screenshots_inspected": False,
        "safari_firefox_screen_reader_desktop_zoom": "not tested",
        "cases": [],
        "requests": [],
        "console_errors": [],
        "page_errors": [],
    }
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(executable.resolve()),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            evidence["chromium"] = browser.version
            # Never disable web security, bypass CSP, or change the app CSP.
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            requests = []
            context.on(
                "request",
                lambda r: requests.append(
                    {
                        "path": urlsplit(r.url).path,
                        "origin_ok": r.url.startswith(origin + "/"),
                        "method": r.method,
                        "query": urlsplit(r.url).query,
                        "has_post_data": r.post_data is not None,
                    }
                ),
            )
            page.on(
                "console",
                lambda m: (
                    evidence["console_errors"].append(m.text)
                    if m.type == "error"
                    else None
                ),
            )
            page.on("pageerror", lambda e: evidence["page_errors"].append(str(e)))
            response = page.goto(origin + "/")
            assert response.status == 200
            assert "Content-Security-Policy" in page.content()
            # The entire initial page must settle without starting the runtime.
            page.wait_for_load_state("networkidle")
            initial = len(requests)
            assert not page.workers
            assert not any("/runtime/" in r["path"] for r in requests)
            page.locator("#input").fill('[ ] T "Synthetic NO_UPLOAD_SENTINEL"')
            assert len(requests) == initial
            assert not page.workers
            evidence["lazy_load"] = True

            def perform(text, keyboard=False):
                page.locator("#input").fill(text)
                started = time.perf_counter()
                if keyboard:
                    page.locator("#check").focus()
                    page.keyboard.press("Enter")
                else:
                    page.locator("#check").click()
                expect(page.locator("#status")).to_have_text(
                    "Finished (parser-only scope).", timeout=30000
                )
                raw = page.locator("#output").inner_text()
                # Output has one ready envelope on cold start and a result envelope.
                result = json.JSONDecoder().raw_decode(
                    raw[raw.rfind("\n{") + 1 :] if "\n{" in raw else raw
                )[0]
                return result, (time.perf_counter() - started) * 1000, raw

            cold, cold_wall, raw = perform(fixtures[1]["text"], keyboard=True)
            startup = json.JSONDecoder().raw_decode(raw)[0]
            evidence["cold"] = {
                "wall_ms": cold_wall,
                "startup": startup,
                "first_check_ms": cold["check_ms"],
            }
            assert len(page.workers) == 1
            warm_count = len(requests)
            for fixture in fixtures:
                result, wall, _ = perform(fixture["text"])
                match = result["result"] == fixture["expected"]
                evidence["cases"].append(
                    {
                        "name": fixture["name"],
                        "match": match,
                        "check_ms": result["check_ms"],
                        "wall_ms": wall,
                    }
                )
                assert match, fixture["name"]
            assert len(requests) == warm_count
            evidence["warm_no_http"] = True
            context.set_offline(True)
            offline, _, _ = perform('[ ] T "Offline synthetic check"')
            assert offline["result"]["valid"]
            context.set_offline(False)
            evidence["offline_warm_check"] = True
            # HTML-like input is displayed only as text and cannot add a DOM node.
            result, _, _ = perform('[ ] T "Read" <img>:x')
            assert page.locator("#output img, #output script").count() == 0
            assert "<img>" in page.locator("#output").inner_text()
            evidence["text_only_output"] = True

            sizes = []
            for lines in (1, 100, 1000, 2000):
                r, wall, _ = perform('[ ] T "Read paper"\n' * lines)
                assert r["result"]["items"] == lines
                sizes.append(
                    {
                        "lines": lines,
                        "bytes": 19 * lines,
                        "check_ms": r["check_ms"],
                        "wall_ms": wall,
                    }
                )
            evidence["sizes"] = sizes
            count = len(requests)
            page.locator("#input").fill("あ" * 22000)
            page.locator("#check").click()
            expect(page.locator("#status")).to_have_text(
                "Input exceeds 65536 UTF-8 bytes."
            )
            assert len(requests) == count
            evidence["oversize_refused_without_http"] = True

            page.locator("#cancel").click()
            expect(page.locator("#input")).to_have_value("")
            expect(page.locator("#output")).to_be_empty()
            # Start and cancel while the fresh Worker is still initializing.
            page.locator("#input").fill('[ ] T "Cancel"')
            page.locator("#check").click()
            page.locator("#cancel").click()
            expect(page.locator("#status")).to_have_text(
                "Cancelled; input, output and runtime cleared."
            )
            perform('[ ] T "Restart"')
            evidence["cancel_and_restart"] = True

            layouts = []
            for width in (1280, 640, 390, 320):
                page.set_viewport_size({"width": width, "height": 900})
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                )
                layouts.append({"width": width, "horizontal_overflow": overflow})
                assert not overflow
            evidence["viewports"] = layouts
            # This is visual/pinch scale, NOT desktop browser zoom acceptance.
            cdp = context.new_cdp_session(page)
            cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 2})
            evidence["emulated_visual_scale"] = page.evaluate("visualViewport.scale")
            assert evidence["emulated_visual_scale"] == 2
            cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 1})
            page.locator("#input").focus()
            page.keyboard.press("Tab")
            assert page.locator("#check").evaluate("e=>e===document.activeElement")
            evidence["keyboard_focus"] = page.locator("#check").evaluate(
                "e=>getComputedStyle(e).outline"
            )
            assert "3px" in evidence["keyboard_focus"]
            evidence["aria"] = {
                "label": page.get_by_label("life.txt sample").count(),
                "status": page.get_by_role("status").count(),
            }
            assert evidence["aria"] == {"label": 1, "status": 1}
            # Inspect persistent web APIs, not the in-memory Python virtual FS.
            evidence["storage"] = page.evaluate("""async () => ({
              local:Object.keys(localStorage),session:Object.keys(sessionStorage),
              indexedDB:(await indexedDB.databases()).map(x=>x.name),
              caches:await caches.keys(),serviceWorkers:(await navigator.serviceWorker.getRegistrations()).length,
              cookies:document.cookie
            })""")
            assert evidence["storage"] == {
                "local": [],
                "session": [],
                "indexedDB": [],
                "caches": [],
                "serviceWorkers": 0,
                "cookies": "",
            }
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                for width in (1280, 390):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.screenshot(
                        path=str(screenshots / f"chromium-{width}.png"), full_page=True
                    )
            evidence["requests"] = requests
            assert all(
                r["origin_ok"]
                and r["method"] == "GET"
                and not r["query"]
                and not r["has_post_data"]
                for r in requests
            )
            assert not evidence["page_errors"], evidence["page_errors"]
            assert not evidence["console_errors"], evidence["console_errors"]
            for name, expected in (
                ("runtime/pyodide.asm.wasm", "application/wasm"),
                ("worker.mjs", "javascript"),
            ):
                # HTTP clients use GET only; these validation reads follow the privacy trace.
                r = context.request.get(origin + "/" + name)
                assert expected in r.headers["content-type"]
            evidence["mime"] = "WASM application/wasm; module JavaScript"
            context.close()
            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                device_scale_factor=3,
            )
            m = mobile.new_page()
            m.goto(origin + "/")
            m.get_by_label("life.txt sample").fill('[ ] T "日本語😀" due:wrong')
            m.get_by_role("button", name="Check", exact=True).click()
            expect(m.get_by_role("status")).to_have_text(
                "Finished (parser-only scope).", timeout=30000
            )
            assert "W203" in m.locator("#output").inner_text()
            assert not m.evaluate("document.documentElement.scrollWidth > innerWidth")
            evidence["mobile_emulation"] = {
                "width": 390,
                "touch": True,
                "device_scale_factor": 3,
                "warning": "W203",
                "physical_device": False,
            }
            if screenshots:
                m.screenshot(
                    path=str(screenshots / "chromium-touch-390.png"), full_page=True
                )
            mobile.close()

            # Separate contexts keep intentional failures out of the success trace.
            failed = browser.new_context()
            failed.route(
                "**/core.zip",
                lambda route: route.fulfill(status=503, body="unavailable"),
            )
            f = failed.new_page()
            f.goto(origin + "/")
            f.locator("#check").click()
            expect(f.get_by_role("status")).to_have_text(
                re.compile("Check failed"), timeout=10000
            )
            f.locator("#cancel").click()
            failed.unroute("**/core.zip")
            f.locator("#input").fill('[ ] T "Retry after failed download"')
            f.locator("#check").click()
            expect(f.get_by_role("status")).to_have_text(
                "Finished (parser-only scope).", timeout=30000
            )
            evidence["download_failure_and_retry"] = True
            failed.close()

            timed = browser.new_context()
            held = []
            timed.route("**/core.zip", lambda route: held.append(route))
            t = timed.new_page()
            t.goto(origin + "/")
            t.clock.install()
            with timed.expect_event(
                "request", predicate=lambda r: r.url.endswith("/core.zip")
            ):
                t.locator("#check").click()
            t.clock.fast_forward(120001)
            expect(t.get_by_role("status")).to_have_text(
                "Timed out; runtime and input cleared."
            )
            expect(t.locator("#input")).to_have_value("")
            assert not t.locator("#check").is_disabled()
            evidence["startup_timeout"] = (
                "real DOM/Worker with held asset; page timer fast-forwarded 120001ms"
            )
            for route in held:
                try:
                    route.abort()
                except PlaywrightError:
                    pass  # Termination may already have closed the worker target.
            timed.unroute_all(behavior="ignoreErrors")
            timed.close()

            csp_context = browser.new_context()
            csp_page = csp_context.new_page()
            csp_page.goto(origin + "/")
            blocked = False
            try:
                csp_page.add_script_tag(
                    content="document.documentElement.dataset.inlineProbe='executed'"
                )
            except PlaywrightError:
                blocked = True
            assert (
                blocked
                and csp_page.evaluate("document.documentElement.dataset.inlineProbe")
                is None
            )
            evidence["csp_inline_script_blocked"] = True
            csp_context.close()
            browser.close()
            evidence["cancelled_static_transfers"] = server.cancelled_transfers
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "chromium": evidence["chromium"],
                    "cases": len(evidence["cases"]),
                    "matches": sum(c["match"] for c in evidence["cases"]),
                    "requests": len(evidence["requests"]),
                    "cold_ms": cold_wall,
                    "browser_errors": evidence["page_errors"],
                }
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--chromium", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    run(args.site, args.chromium, args.output, args.screenshots)
