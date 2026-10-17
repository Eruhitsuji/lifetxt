"""Actual Firefox/WebKit PoC matrix; blocked is never passed (#1364)."""

import argparse
from functools import partial
import hashlib
import http.server
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from contrib.browser_check_poc.browser_probe import Handler


def check_engine(pw, engine, origin, fixtures, driver=None):
    if driver is None:
        from playwright import sync_api as driver

    PlaywrightError, expect = driver.Error, driver.expect

    evidence = {"engine": engine, "status": "blocked", "physical_device": False}
    try:
        options = {"headless": True}
        if engine == "chromium" and os.environ.get("LIFETXT_BROWSER_BIN"):
            options.update(
                executable_path=os.environ["LIFETXT_BROWSER_BIN"],
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        browser = getattr(pw, engine).launch(**options)
    except PlaywrightError as error:
        evidence["reason"] = "Engine launch failed before page creation"
        evidence["missing_libraries"] = sorted(
            set(re.findall(r"lib[\w+.-]+\.so(?:\.\d+)*", str(error)))
        )
        evidence["error_type"] = type(error).__name__
        return evidence
    page_created = False
    try:
        evidence["version"] = browser.version
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page_created = True
        requests, errors = [], []
        context.on(
            "request",
            lambda r: requests.append(
                {
                    "path": urlsplit(r.url).path,
                    "origin_ok": r.url.startswith(origin + "/"),
                    "method": r.method,
                    "query": urlsplit(r.url).query,
                    "has_body": r.post_data is not None,
                }
            ),
        )
        page.on("pageerror", lambda e: errors.append(type(e).__name__))
        page.on(
            "console",
            lambda m: errors.append("console error") if m.type == "error" else None,
        )
        assert page.goto(origin).status == 200
        page.wait_for_load_state("networkidle")
        initial = len(requests)
        page.get_by_label("life.txt sample").fill(
            '[ ] T "Synthetic NO_UPLOAD_SENTINEL"'
        )
        assert len(requests) == initial and not page.workers
        assert not any("/runtime/" in r["path"] for r in requests)
        evidence["lazy_load"] = True

        def perform(text, keyboard=False):
            page.locator("#input").fill(text)
            started = time.perf_counter()
            if keyboard:
                page.locator("#check").focus()
                page.keyboard.press("Enter")
            else:
                page.locator("#check").click()
            expect(page.get_by_role("status")).to_have_text(
                "Finished (parser-only scope).", timeout=30000
            )
            raw = page.locator("#output").inner_text()
            result = json.JSONDecoder().raw_decode(
                raw[raw.rfind("\n{") + 1 :] if "\n{" in raw else raw
            )[0]
            return result, (time.perf_counter() - started) * 1000

        _, cold_ms = perform(fixtures[1]["text"], keyboard=True)
        assert len(page.workers) == 1
        evidence["cold_interaction_ms"] = cold_ms
        count = len(requests)
        cases = []
        for fixture in fixtures:
            result, wall = perform(fixture["text"])
            match = result["result"] == fixture["expected"]
            cases.append(
                {
                    "name": fixture["name"],
                    "match": match,
                    "check_ms": result["check_ms"],
                    "wall_ms": wall,
                }
            )
            assert match, fixture["name"]
        evidence["cases"] = cases
        assert len(requests) == count
        evidence["warm_no_http"] = True
        context.set_offline(True)
        result, _ = perform('[ ] T "Offline synthetic"')
        assert result["result"]["valid"]
        context.set_offline(False)
        evidence["offline_warm"] = True
        perform('[ ] T "Read" <img>:x')
        assert "<img>" in page.locator("#output").inner_text()
        assert page.locator("#output img, #output script").count() == 0
        evidence["text_only"] = True
        page.locator("#input").fill("あ" * 22000)
        page.locator("#check").click()
        expect(page.get_by_role("status")).to_have_text(
            "Input exceeds 65536 UTF-8 bytes."
        )
        assert len(requests) == count
        evidence["oversize_no_http"] = True
        widths = []
        for width in (1280, 640, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            assert not page.evaluate(
                "document.documentElement.scrollWidth > innerWidth"
            )
            widths.append(width)
        evidence["no_overflow_widths"] = widths
        page.locator("#input").focus()
        page.keyboard.press("Tab")
        assert page.locator("#check").evaluate("e=>e===document.activeElement")
        outline = page.locator("#check").evaluate("e=>getComputedStyle(e).outline")
        assert "3px" in outline
        evidence["keyboard_focus"] = outline
        storage = page.evaluate("""async () => ({
          local:Object.keys(localStorage), session:Object.keys(sessionStorage),
          indexedDB: typeof indexedDB.databases === 'function' ? (await indexedDB.databases()).map(x=>x.name) : 'not exposed',
          caches:await caches.keys(), serviceWorkers:(await navigator.serviceWorker.getRegistrations()).length,
          cookies:document.cookie
        })""")
        assert storage["local"] == storage["session"] == storage["caches"] == []
        assert storage["indexedDB"] in ([], "not exposed")
        assert storage["cookies"] == "" and storage["serviceWorkers"] == 0
        evidence["storage"] = storage
        page.locator("#cancel").click()
        expect(page.locator("#input")).to_have_value("")
        expect(page.locator("#output")).to_have_text("")
        perform('[ ] T "Restart"')
        evidence["cancel_clear_restart"] = True
        evidence["requests"] = requests
        assert all(
            r["origin_ok"]
            and r["method"] == "GET"
            and not r["query"]
            and not r["has_body"]
            for r in requests
        )
        assert not errors, errors
        evidence["success_context_errors"] = errors
        for path, mime in (
            ("runtime/pyodide.asm.wasm", "application/wasm"),
            ("worker.mjs", "javascript"),
        ):
            assert (
                mime in context.request.get(origin + "/" + path).headers["content-type"]
            )
        evidence["mime"] = True
        context.close()
        # Separate negative-test context, never weaken or bypass the app CSP.
        negative = browser.new_context()
        p = negative.new_page()
        p.goto(origin)
        blocked = False
        try:
            p.add_script_tag(
                content="document.documentElement.dataset.inlineProbe='executed'"
            )
        except PlaywrightError:
            blocked = True
        assert (
            blocked
            and p.evaluate("document.documentElement.dataset.inlineProbe") is None
        )
        evidence["csp_inline_blocked"] = True
        negative.close()
        evidence["status"] = "passed"
    except Exception as error:
        evidence["status"] = "failed" if page_created else "blocked"
        evidence["error_type"] = type(error).__name__
        evidence["reason"] = (
            "Acceptance assertion or operation failed; inspect local test output"
            if page_created
            else "Engine launched but page creation failed before acceptance"
        )
        traceback.print_exc()
    finally:
        browser.close()
    return evidence


def run(site, engines, output):
    from playwright.sync_api import sync_playwright

    if (
        not engines
        or len(set(engines)) != len(engines)
        or any(e not in ("chromium", "firefox", "webkit") for e in engines)
    ):
        raise ValueError("Choose chromium, firefox and/or webkit")
    site = site.resolve()
    fixtures = json.loads((site / "fixtures.json").read_text())
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, directory=str(site))
    )
    server.cancelled_transfers = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    evidence = {
        "issue": 1364,
        "playwright": version("playwright"),
        "kind": "actual headless desktop engines over loopback HTTP",
        "manifest_sha256": hashlib.sha256(
            (site / "manifest.json").read_bytes()
        ).hexdigest(),
        "manifest": json.loads((site / "manifest.json").read_text()),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "safari_iphone_android_screen_reader_desktop_zoom": "not tested",
        "engines": [],
    }
    try:
        with sync_playwright() as pw:
            for engine in engines:
                evidence["engines"].append(
                    check_engine(
                        pw, engine, f"http://127.0.0.1:{server.server_port}", fixtures
                    )
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def matrix_passed(evidence, engines):
    results = evidence["engines"]
    return (
        bool(engines)
        and [e["engine"] for e in results] == list(engines)
        and all(
            e["status"] == "passed"
            and len(e.get("cases", [])) == 16
            and all(c["match"] for c in e["cases"])
            for e in results
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument(
        "--engines",
        nargs="+",
        choices=("chromium", "firefox", "webkit"),
        default=["firefox", "webkit"],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.site, args.engines, args.output)
    print(
        json.dumps([{k: e[k] for k in ("engine", "status")} for e in result["engines"]])
    )
    raise SystemExit(not matrix_passed(result, args.engines))
