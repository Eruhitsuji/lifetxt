"""Bounded desktop measurements for #1366; never physical-device acceptance."""

import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
import http.server
from importlib.metadata import version
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from contrib.browser_check_poc.adapter import check_text
from contrib.browser_check_poc.browser_probe import Handler

PROFILES = (("loopback", 0, 0), ("simulated_slow", 0.15, 524288))
REPEATS = 30


class RateHandler(Handler):
    """Per-response pacing, NOT an aggregate cellular bandwidth simulation."""

    def do_GET(self):
        time.sleep(self.server.latency)
        super().do_GET()

    def copyfile(self, source, outputfile):
        if not self.server.rate:
            return super().copyfile(source, outputfile)
        started, total = time.monotonic(), 0
        try:
            while chunk := source.read(16384):
                total += len(chunk)
                time.sleep(
                    max(0, total / self.server.rate - (time.monotonic() - started))
                )
                outputfile.write(chunk)
                outputfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            self.server.cancelled_transfers += 1


def boundary_text():
    return '[ ] T "' + "x" * (65536 - 8) + '"'


def measurement_passed(evidence):
    """Partial output must never serve as completed bounded measurements."""
    profiles = evidence.get("profiles", [])
    return (
        evidence.get("status") == "passed"
        and evidence.get("physical_device") is False
        and [p.get("name") for p in profiles] == [p[0] for p in PROFILES]
        and all(
            p.get("status") == "passed"
            and p.get("boundary_bytes") == 65536
            and p.get("repeat_matches") == REPEATS
            and p.get("diagnostic_limit") == 100
            and p.get("diagnostics_truncated") is True
            and p.get("warm_no_http") is True
            and p.get("oversize_refused") is True
            and p.get("cancel_restart") is True
            and p.get("storage_empty") is True
            and p.get("network_bounded") is True
            and p.get("ax_semantics") is True
            for p in profiles
        )
    )


def inspect_profile(browser, site, name, latency, rate):
    from playwright.sync_api import expect

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(RateHandler, directory=str(site))
    )
    server.latency, server.rate, server.cancelled_transfers = latency, rate, 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    result = {
        "name": name,
        "status": "failed",
        "response_latency_seconds": latency,
        "bytes_per_second_per_response": rate,
    }
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    stage = "initial_page"
    print(f"{name}: starting", flush=True)
    try:
        page = context.new_page()
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
        assert page.goto(origin).status == 200
        page.wait_for_load_state("networkidle")
        cdp = context.new_cdp_session(page)

        def perform(text):
            edit_started = time.perf_counter()
            page.locator("#input").fill(text)
            edit_ms = (time.perf_counter() - edit_started) * 1000
            started = time.perf_counter()
            page.locator("#check").click()
            expect(page.locator("#status")).to_have_text(
                "Finished (parser-only scope).", timeout=115000
            )
            raw = page.locator("#output").inner_text()
            decoder = json.JSONDecoder()
            first, end = decoder.raw_decode(raw)
            last = (
                decoder.raw_decode(raw[end:].lstrip())[0]
                if raw[end:].strip()
                else first
            )
            assert last["result"] == check_text(text), "native result mismatch"
            last["automation_fill_ms"] = edit_ms
            return last, (time.perf_counter() - started) * 1000, first

        cold, wall, startup = perform('[ ] T "Synthetic cold"')
        result["cold"] = {
            "wall_ms": wall,
            "check_ms": cold["check_ms"],
            "startup_ms": startup["startup_ms"],
            "startup_wasm_heap_capacity_bytes": startup["runtime"]["wasm_heap_bytes"],
        }
        count = len(requests)
        stage = "boundary_and_repeats"
        result["page_js_heap_before"] = cdp.send("Runtime.getHeapUsage")
        text = boundary_text()
        last, wall, _ = perform(text)
        result["boundary_bytes"] = len(text.encode())
        result["boundary"] = {
            "check_ms": last["check_ms"],
            "wall_ms": wall,
            "automation_fill_ms": last["automation_fill_ms"],
        }
        assert last["result"]["valid"] and last["result"]["items"] == 1
        result["repeats"] = []
        repeated = '[ ] T "Synthetic repeated"\n' * 2000
        for index in range(REPEATS):
            last, wall, _ = perform(repeated)
            result["repeats"].append(
                {
                    "check_ms": last["check_ms"],
                    "wall_ms": wall,
                    "automation_fill_ms": last["automation_fill_ms"],
                }
            )
            if (index + 1) % 10 == 0:
                print(f"{name}: {index + 1} repeated comparisons", flush=True)
        result["repeat_matches"] = len(result["repeats"])
        last, _, _ = perform('[ ] T "Synthetic warning" due:wrong\n' * 500)
        result["diagnostic_limit"] = len(last["result"]["diagnostics"])
        result["diagnostic_count"] = last["result"]["diagnostic_count"]
        result["diagnostics_truncated"] = last["result"]["truncated"]
        assert result["diagnostic_limit"] == 100 and result["diagnostic_count"] >= 500
        result["page_js_heap_after"] = cdp.send("Runtime.getHeapUsage")
        result["warm_no_http"] = len(requests) == count
        assert result["warm_no_http"]
        page.locator("#input").fill(text + "x")
        page.locator("#check").click()
        expect(page.locator("#status")).to_have_text("Input exceeds 65536 UTF-8 bytes.")
        assert len(requests) == count
        result["oversize_refused"] = True
        stage = "accessibility_and_storage"

        # Actual accessibility tree semantics, not a screen-reader audit.
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        roles = [
            (n.get("role", {}).get("value"), n.get("name", {}).get("value"))
            for n in nodes
            if not n.get("ignored")
        ]
        assert ("textbox", "life.txt sample") in roles and ("button", "Check") in roles
        assert any(role == "status" for role, _ in roles)
        result["ax_semantics"] = True
        result["font_family"] = page.locator("#input").evaluate(
            "e=>getComputedStyle(e).fontFamily"
        )
        page.locator("#input").focus()
        page.keyboard.press("Tab")
        assert page.locator("#check").evaluate("e=>e===document.activeElement")
        result["focus_outline"] = page.locator("#check").evaluate(
            "e=>getComputedStyle(e).outline"
        )
        assert "3px" in result["focus_outline"]
        storage = page.evaluate("""async () => ({
          local:Object.keys(localStorage), session:Object.keys(sessionStorage),
          indexedDB:(await indexedDB.databases()).map(x=>x.name),
          caches:await caches.keys(), serviceWorkers:(await navigator.serviceWorker.getRegistrations()).length,
          cookies:document.cookie
        })""")
        assert storage == {
            "local": [],
            "session": [],
            "indexedDB": [],
            "caches": [],
            "serviceWorkers": 0,
            "cookies": "",
        }
        result["storage_empty"] = True
        page.locator("#cancel").click()
        expect(page.locator("#input")).to_have_value("")
        expect(page.locator("#output")).to_have_text("")
        stage = "clear_gc_and_restart"
        result["page_js_heap_after_clear"] = cdp.send("Runtime.getHeapUsage")
        # Diagnostic observation; forced GC is separate from normal interaction.
        cdp.send("HeapProfiler.collectGarbage")
        result["page_js_heap_after_forced_gc"] = cdp.send("Runtime.getHeapUsage")
        perform('[ ] T "Synthetic recovery"')
        result["cancel_restart"] = True
        assert not errors
        assert all(
            r["origin_ok"]
            and r["method"] == "GET"
            and not r["query"]
            and not r["has_body"]
            for r in requests
        )
        result["requests"] = requests
        result["network_bounded"] = True
        result["status"] = "passed"
        print(f"{name}: bounded measurements passed", flush=True)
    except Exception as error:
        result["error_type"] = type(error).__name__
        result["failed_stage"] = stage
        result["reason"] = (
            "Measurement failed; inspect local run, no acceptance inferred"
        )
        print(f"{name}: {type(error).__name__}", file=sys.stderr)
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return result


def run(site, executable, output):
    from playwright.sync_api import sync_playwright

    site = site.resolve()
    manifest = json.loads((site / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        data = (site / name).read_bytes()
        if (
            len(data) != expected["bytes"]
            or hashlib.sha256(data).hexdigest() != expected["sha256"]
        ):
            raise ValueError("Artifact integrity mismatch")
    evidence = {
        "issue": 1366,
        "status": "blocked",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "physical_device": False,
        "playwright": version("playwright"),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(
            (site / "manifest.json").read_bytes()
        ).hexdigest(),
        "manifest": manifest,
        "unverified": [
            "physical devices",
            "Safari/Firefox/WebKit acceptance",
            "screen reader",
            "desktop 200% zoom",
            "CJK visual quality",
            "peak total memory and low-memory behavior",
            "complete binary attribution and source delivery",
            "adoption/publication",
        ],
        "memory_scope": "Page CDP JS heap snapshots exclude Worker WASM and process peak; startup WASM capacity is not usage",
        "profiles": [],
    }
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(executable.resolve()),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            evidence["chromium"] = browser.version
            try:
                for profile in PROFILES:
                    evidence["profiles"].append(
                        inspect_profile(browser, site, *profile)
                    )
            finally:
                browser.close()
        evidence["status"] = "passed"
        if not measurement_passed(evidence):
            evidence["status"] = "failed"
    except Exception as error:
        evidence["error_type"] = type(error).__name__
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--chromium", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.site, args.chromium, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "profiles": [p["status"] for p in result["profiles"]],
            }
        )
    )
    raise SystemExit(not measurement_passed(result))
