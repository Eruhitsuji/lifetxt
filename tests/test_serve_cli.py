import argparse
import os
import tempfile
import unittest
from unittest import mock

try:
    import uvicorn
except ImportError:
    uvicorn = None


@unittest.skipIf(uvicorn is None, "web extras unavailable")
class ServeSingleWorkerTests(unittest.TestCase):
    """Covers #172: WEB_CONCURRENCY must not make `serve` crash or multi-worker."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Item id:i1\n")

    def tearDown(self):
        self.temp.cleanup()

    def args(self):
        return argparse.Namespace(
            paths=[self.path],
            host=None,
            port=0,
            write_file=None,
            config_data={},
            mcp=False,
            read_only=False,
            token_env=None,
            insecure_public=False,
        )

    def test_serve_always_passes_workers_1_to_uvicorn(self):
        from lifetxt.cli import command_serve

        with mock.patch("lifetxt.webapp.create_app", return_value=object()):
            with mock.patch("uvicorn.run") as run:
                with mock.patch.dict(os.environ, {"WEB_CONCURRENCY": "4"}):
                    command_serve(self.args())
        self.assertEqual(1, run.call_args.kwargs.get("workers"))

    def test_serve_passes_workers_1_even_without_web_concurrency_set(self):
        from lifetxt.cli import command_serve

        with mock.patch("lifetxt.webapp.create_app", return_value=object()):
            with mock.patch("uvicorn.run") as run:
                os.environ.pop("WEB_CONCURRENCY", None)
                command_serve(self.args())
        self.assertEqual(1, run.call_args.kwargs.get("workers"))


@unittest.skipIf(uvicorn is None, "web extras unavailable")
class WebCliTests(unittest.TestCase):
    """Covers #592: `web` is a thin launcher over the same `serve` runtime."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Item id:i1\n")

    def tearDown(self):
        self.temp.cleanup()

    def args(self, **overrides):
        base = dict(
            paths=[self.path],
            host=None,
            port=0,
            write_file=None,
            config_data={},
            read_only=False,
            token_env=None,
            insecure_public=False,
            no_open=True,
        )
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_web_reuses_the_same_prepare_serve_path_as_serve(self):
        from lifetxt.cli import command_web

        with mock.patch(
            "lifetxt.webapp.create_app", return_value=object()
        ) as create_app:
            with mock.patch("uvicorn.run") as run:
                command_web(self.args())
        create_app.assert_called_once()
        self.assertEqual(1, run.call_args.kwargs.get("workers"))

    def test_web_no_open_never_starts_a_browser_thread(self):
        from lifetxt.cli import command_web

        with mock.patch("lifetxt.webapp.create_app", return_value=object()):
            with mock.patch("uvicorn.run"):
                with mock.patch("threading.Thread") as thread_cls:
                    command_web(self.args(no_open=True))
        thread_cls.assert_not_called()

    def test_web_without_no_open_starts_one_daemon_readiness_thread(self):
        from lifetxt import cli as cli_module

        with mock.patch("lifetxt.webapp.create_app", return_value=object()):
            with mock.patch("uvicorn.run"):
                with mock.patch("threading.Thread") as thread_cls:
                    cli_module.command_web(
                        self.args(no_open=False, host="127.0.0.1", port=8000)
                    )
        thread_cls.assert_called_once()
        _call_args, kwargs = thread_cls.call_args
        self.assertTrue(kwargs.get("daemon"))
        self.assertIs(kwargs.get("target"), cli_module._open_browser_when_ready)
        self.assertEqual(
            ("http://127.0.0.1:8000/", "127.0.0.1", 8000), kwargs.get("args")
        )

    def test_web_missing_dependency_gives_an_actionable_message(self):
        from lifetxt.cli import command_web

        with mock.patch.dict("sys.modules", {"uvicorn": None}):
            with self.assertRaises(ValueError) as ctx:
                command_web(self.args())
        self.assertIn("Web dependencies are not installed", str(ctx.exception))


@unittest.skipIf(uvicorn is None, "web extras unavailable")
class OpenBrowserWhenReadyTests(unittest.TestCase):
    """The browser-launch call is fully mocked/isolated -- no real browser or
    network connection is ever opened by these tests."""

    def test_opens_the_browser_once_the_health_route_answers(self):
        from lifetxt import cli as cli_module

        seen_urls = []

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        def fake_urlopen(url, timeout=None):
            seen_urls.append(url)
            return _FakeResponse()

        with mock.patch.object(cli_module, "urlopen", fake_urlopen):
            with mock.patch("webbrowser.open") as open_browser:
                cli_module._open_browser_when_ready(
                    "http://127.0.0.1:8000/",
                    "127.0.0.1",
                    8000,
                    timeout=5.0,
                    interval=0.01,
                )
        self.assertTrue(any(u.endswith("/api/health") for u in seen_urls))
        open_browser.assert_called_once_with("http://127.0.0.1:8000/")

    def test_gives_up_after_the_timeout_without_opening_a_browser(self):
        from lifetxt import cli as cli_module

        def fake_urlopen(url, timeout=None):
            raise OSError("connection refused")

        with mock.patch.object(cli_module, "urlopen", fake_urlopen):
            with mock.patch("webbrowser.open") as open_browser:
                cli_module._open_browser_when_ready(
                    "http://127.0.0.1:8000/",
                    "127.0.0.1",
                    8000,
                    timeout=0.05,
                    interval=0.01,
                )
        open_browser.assert_not_called()

    def test_browser_reachable_host_substitutes_wildcard_bind_addresses(self):
        from lifetxt import cli as cli_module

        self.assertEqual("127.0.0.1", cli_module._browser_reachable_host("0.0.0.0"))
        self.assertEqual("::1", cli_module._browser_reachable_host("::"))
        self.assertEqual("127.0.0.1", cli_module._browser_reachable_host(None))
        self.assertEqual(
            "example.internal", cli_module._browser_reachable_host("example.internal")
        )

    def test_web_ui_url_uses_loopback_for_a_wildcard_host(self):
        from lifetxt import cli as cli_module

        self.assertEqual(
            "http://127.0.0.1:8000/", cli_module._web_ui_url("0.0.0.0", 8000)
        )
        self.assertEqual(
            "http://192.168.1.5:9000/", cli_module._web_ui_url("192.168.1.5", 9000)
        )


if __name__ == "__main__":
    unittest.main()
