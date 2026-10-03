import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "contrib" / "openwrt" / "lifetxt-wan-event"


@unittest.skipUnless(shutil.which("sh"), "POSIX shell unavailable")
class OpenWrtWanAdapterTests(unittest.TestCase):
    def run_adapter(self, event, life, state, mini):
        env = os.environ.copy()
        env.update(
            LIFETXT_FILE=str(life),
            LIFETXT_WAN_STATE_FILE=str(state),
            LIFETXT_MINI=str(mini),
            LIFETXT_CALLS=str(state) + ".calls",
        )
        return subprocess.run(
            ["sh", str(ADAPTER), event],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_transition_and_duplicate_suppression(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            life = directory / "life.txt"
            life.write_text("[ ] T \"seed\" id:seed\n", encoding="utf-8")
            state = directory / "state"
            calls = pathlib.Path(str(state) + ".calls")
            mini = directory / "mini"
            mini.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$LIFETXT_CALLS\"\n",
                encoding="utf-8",
            )
            mini.chmod(0o755)
            first = self.run_adapter("WAN_UP", life, state, mini)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertFalse(calls.exists())
            self.assertEqual("stable=WAN_UP\n", state.read_text()[: len("stable=WAN_UP\n")])

            down = self.run_adapter("WAN_DOWN", life, state, mini)
            self.assertEqual(0, down.returncode, down.stderr)
            repeat = self.run_adapter("WAN_DOWN", life, state, mini)
            self.assertEqual(0, repeat.returncode, repeat.stderr)
            self.assertEqual(1, len(calls.read_text().splitlines()))
            self.assertIn("WAN disconnected", calls.read_text())

            up = self.run_adapter("WAN_UP", life, state, mini)
            self.assertEqual(0, up.returncode, up.stderr)
            self.assertEqual(2, len(calls.read_text().splitlines()))
            self.assertIn("WAN restored", calls.read_text())

    def test_invalid_input_is_rejected_without_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            result = self.run_adapter(
                "WAN_REBOOT", directory / "life.txt", directory / "state", directory / "missing-mini"
            )
            self.assertEqual(2, result.returncode)
            self.assertIn("usage:", result.stderr)

    def test_mini_failure_does_not_advance_state(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            life = directory / "life.txt"
            life.write_text("", encoding="utf-8")
            state = directory / "state"
            mini = directory / "mini"
            mini.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            mini.chmod(0o755)
            result = self.run_adapter("WAN_DOWN", life, state, mini)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
