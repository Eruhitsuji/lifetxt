import argparse
import os
import tempfile
import unittest
from unittest import mock


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


if __name__ == "__main__":
    unittest.main()
