"""Focused synthetic Chromium acceptance for local checker; never deploys (#1399)."""

import argparse
from functools import partial
import http.server
import importlib.util
import json
from pathlib import Path
import platform
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            pass


def run(site, executable, output, screenshots=None):
    from playwright.sync_api import expect, sync_playwright

    spec = importlib.util.spec_from_file_location(
        "checker_adapter", ROOT / "website/checker/adapter.py"
    )
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    fixtures = json.loads(
        (ROOT / "contrib/browser_check_poc/fixtures.json").read_text("utf-8")
    )
    fixtures += [
        {"name": "empty", "text": ""},
        {"name": "utf8-boundary", "text": "#" + "あ" * 5461},
        {"name": "ascii-boundary", "text": "#" + "x" * 16383},
        {"name": "emoji", "text": '[ ] T "日本語😀"'},
        {"name": "supplementary-cjk", "text": '[ ] T "日本語𠮷香港"'},
        {"name": "100-diagnostics", "text": "bad\n" * 100},
        {"name": "500-diagnostics", "text": "bad\n" * 500},
    ]
    report = {
        "kind": "headless Chromium loopback HTTP; synthetic inputs",
        "os": platform.platform(),
        "acceptance": "failed",
        "languages": {},
        "unverified": [
            "physical devices",
            "screen readers",
            "Firefox/Safari",
            "OS peak memory",
            "public Pages delivery",
        ],
    }
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(site.resolve()))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(executable.resolve()),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            report["chromium"] = browser.version
            for lang in ("ja", "en"):
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                context.add_init_script("""window.__messages=[]; window.__storageWrites=[];window.__ticks=0;setInterval(()=>window.__ticks++,10);
const OriginalWorker=window.Worker;
window.Worker=class extends OriginalWorker { constructor(...args) { super(...args); this.addEventListener('message',event=>window.__messages.push(event.data)); }};
for(const [obj,key] of [[Storage.prototype,'setItem'],[indexedDB,'open'],[caches,'open'],[navigator.serviceWorker,'register']]) {
 const original=obj[key]; obj[key]=function(...args){window.__storageWrites.push(key);return original.apply(this,args);}; }
window.__csp=[]; document.addEventListener('securitypolicyviolation',event=>window.__csp.push(event.violatedDirective));""")
                page = context.new_page()
                requests, errors = [], []
                context.on(
                    "request",
                    lambda r: requests.append(
                        {
                            "path": urlsplit(r.url).path,
                            "same_origin": r.url.startswith(origin + "/"),
                            "method": r.method,
                            "query": bool(urlsplit(r.url).query),
                            "body": r.post_data is not None,
                        }
                    ),
                )
                page.on("pageerror", lambda e: errors.append(str(e)))
                response = page.goto(origin + f"/{lang}/check/")
                assert response.status == 200
                page.wait_for_load_state("networkidle")
                assert not page.workers
                assert not any("runtime" in r["path"] for r in requests)
                checks = []

                def perform(text):
                    before = len(page.evaluate("window.__messages"))
                    fill_started = time.perf_counter()
                    page.locator("#input").fill(text)
                    fill_ms = (time.perf_counter() - fill_started) * 1000
                    started = time.perf_counter()
                    page.locator("#check").focus()
                    page.keyboard.press("Enter")
                    page.wait_for_function(
                        "n=>window.__messages.slice(n).some(m=>m.stage==='result')",
                        arg=before,
                        timeout=30000,
                    )
                    expect(page.locator("#check")).to_be_enabled()
                    result = page.evaluate(
                        "n=>window.__messages.slice(n).find(m=>m.stage==='result')",
                        before,
                    )
                    assert result["result"] == adapter.check_text(text)
                    displayed = page.locator("#output").inner_text()
                    for diagnostic in result["result"]["diagnostics"]:
                        assert diagnostic["message"] in displayed
                        assert diagnostic["code"] in displayed
                        if diagnostic.get("hint"):
                            assert diagnostic["hint"] in displayed
                    assert page.locator("#output img").count() == 0
                    return {
                        "fill_ms": fill_ms,
                        "wall_ms": (time.perf_counter() - started) * 1000,
                        "worker_ms": result["check_ms"],
                    }

                for fixture in fixtures:
                    metrics = perform(fixture["text"])
                    checks.append({"name": fixture["name"], **metrics})
                for text in ("x" * 16385, "#" + "あ" * 5461 + "x"):
                    before = len(page.evaluate("window.__messages"))
                    page.locator("#input").fill(text)
                    page.locator("#check").click()
                    assert page.evaluate("window.__messages.length") == before
                    assert page.locator("#output").inner_text() == ""
                    assert "16,384" in page.locator("#status").inner_text()
                cdp = context.new_cdp_session(page)
                cdp.send("Performance.enable")
                before_heap = cdp.send("Performance.getMetrics")
                repeated = [perform('[ ] T "Synthetic"\n' * 800) for _ in range(30)]
                after_heap = cdp.send("Performance.getMetrics")
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                page.locator("#cancel").click()
                assert page.locator("#input").input_value() == ""
                assert page.locator("#output").inner_text() == ""
                perform('[ ] T "Restart"')
                page.locator("#cancel").click()
                # Force a cold package failure: browsers may satisfy offline GETs
                # from their ordinary HTTP cache (the app does not persist input).
                context.route("**/checker/core.zip", lambda route: route.abort())
                context.set_offline(True)
                page.locator("#input").fill('[ ] T "Offline failure"')
                page.locator("#check").click()
                expect(page.locator("#check")).to_be_enabled(timeout=30000)
                assert page.locator("#input").input_value() == '[ ] T "Offline failure"'
                context.set_offline(False)
                context.unroute("**/checker/core.zip")
                # Retry the retained input without another paste/fill.
                page.locator("#check").click()
                expect(page.locator("#status")).to_contain_text(
                    "完了" if lang == "ja" else "finished", timeout=30000
                )
                assert page.locator("#input").input_value() == '[ ] T "Offline failure"'
                perform('[ ] T "Online recovery"')
                storage = page.evaluate(
                    """async()=>({local:localStorage.length,session:sessionStorage.length,databases:await indexedDB.databases(),caches:await caches.keys(),registrations:(await navigator.serviceWorker.getRegistrations()).length,writes:window.__storageWrites,csp:window.__csp})"""
                )
                assert storage == {
                    "local": 0,
                    "session": 0,
                    "databases": [],
                    "caches": [],
                    "registrations": 0,
                    "writes": [],
                    "csp": [],
                }
                assert not context.cookies()
                assert all(
                    r["same_origin"]
                    and r["method"] == "GET"
                    and not r["query"]
                    and not r["body"]
                    for r in requests
                )
                assert not errors
                if screenshots:
                    screenshots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(
                        path=str(screenshots / f"checker-{lang}.png"), full_page=True
                    )
                report["languages"][lang] = {
                    "checks": checks,
                    "startup": page.evaluate(
                        "window.__messages.find(m=>m.stage==='ready')"
                    ),
                    "main_thread_ticks": page.evaluate("window.__ticks"),
                    "page_heap_before_repeats": before_heap,
                    "page_heap_after_repeats": after_heap,
                    "heap_scope": "CDP page metrics only; excludes Worker and OS peak, not leak evidence",
                    "repeated": repeated,
                    "requests": requests,
                    "storage": storage,
                    "keyboard": "Enter check passed",
                    "layout": "no horizontal overflow at 1280x900",
                    "cancel_restart_offline_recovery": "passed",
                }
                context.close()
            # Force an accelerated startup timeout only in this synthetic context.
            context = browser.new_context()
            context.add_init_script(
                "const original=setTimeout;window.setTimeout=(fn,ms,...args)=>original(fn,ms===120000?50:ms,...args)"
            )
            context.route(
                "**/checker/runtime/pyodide.mjs",
                lambda route: route.fulfill(
                    content_type="text/javascript",
                    body="await new Promise(()=>{}); export async function loadPyodide() {}",
                ),
            )
            page = context.new_page()
            page.goto(origin + "/en/check/")
            page.locator("#input").fill("# synthetic timeout")
            page.locator("#check").click()
            expect(page.locator("#check")).to_be_enabled(timeout=30000)
            assert page.locator("#input").input_value() == "# synthetic timeout"
            assert "Timed out" in page.locator("#status").inner_text()
            report["accelerated_startup_timeout_preserves_input"] = True
            # The same stalled module is cancelled before it can finish startup.
            page.locator("#input").fill("# synthetic cancellation")
            page.locator("#check").click()
            page.locator("#cancel").click()
            assert page.locator("#input").input_value() == ""
            assert page.locator("#output").inner_text() == ""
            report["cancel_during_initialization"] = True
            context.close()
            browser.close()
            report["acceptance"] = "passed_focused_only"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--chromium", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    run(args.site, args.chromium, args.output, args.screenshots)
