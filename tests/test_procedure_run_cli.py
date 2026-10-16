import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_lifetxt import run_cli
from tests.test_procedure_definition import SAMPLE
from lifetxt.procedure_run_store import read_log


def fields(output):
    return dict(
        line.split(": ", 1)
        for line in output.splitlines()
        if ": " in line and not line.startswith("  ")
    )


class RunCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source with spaces.txt"
        self.log = self.root / "run log.txt"
        self.source.write_text(SAMPLE)
        self.seq = 0

    def invoke(self, verb, **kwargs):
        command = [
            "procedure",
            "run",
            verb,
            str(self.source),
            "--id",
            "r",
            "--log",
            str(self.log),
        ]
        for key, value in kwargs.items():
            command.append("--" + key.replace("_", "-"))
            if value is not True:
                command.append(str(value))
        return run_cli(*command)

    def mutate(self, verb, snapshot, **kwargs):
        self.seq += 1
        values = dict(
            actor="alice",
            request_id="req%d" % self.seq,
            template_revision=snapshot.get(
                "Bound template revision", snapshot["Template revision"]
            ),
            log_revision=snapshot["Log revision"],
            step=snapshot.get("Step", snapshot.get("Start step")),
            sequence=snapshot.get("Sequence", 0),
        )
        if "Run" in snapshot:
            values["run_id"] = snapshot["Run"]
        values.update(kwargs)
        out, err, code = self.invoke(verb, **values)
        self.assertEqual(0, code, err)
        return fields(out), out

    def test_show_no_writes_and_complete_noninteractive_lifecycle(self):
        out, err, code = self.invoke("show")
        self.assertEqual(0, code, err)
        self.assertEqual("<missing>", fields(out)["Log revision"])
        self.assertEqual([self.source], list(self.root.iterdir()))
        snap, _ = self.mutate("start", fields(out), allow_loops=True)
        self.assertIn("Run", snap)
        snap, out = self.mutate("next", snap)
        self.assertIn("Instruction: Result", out)
        out, err, code = self.invoke("show", run_id=snap["Run"])
        self.assertEqual(0, code, err)
        snap, out = self.mutate("choose", fields(out), choice="yes")
        self.assertEqual("active", snap["Status"])
        self.assertEqual("e", snap["Step"])
        snap, _ = self.mutate("pause", snap)
        out, err, code = self.invoke("show", run_id=snap["Run"])
        self.assertEqual("paused", fields(out)["Status"])
        snap, _ = self.mutate("resume", fields(out))
        snap, _ = self.mutate("finish", snap)
        self.assertEqual("completed", snap["Status"])
        self.assertEqual(SAMPLE, self.source.read_text())

    def test_missing_preconditions_wrong_choice_duplicate_and_terminal_refuse(self):
        out, err, code = self.invoke("start")
        self.assertNotEqual(0, code)
        self.assertEqual("", out)
        out, _, _ = self.invoke("show")
        snap, _ = self.mutate("start", fields(out), allow_loops=True)
        snap, _ = self.mutate("next", snap)
        before = self.log.read_bytes()
        values = dict(
            run_id=snap["Run"],
            actor="alice",
            request_id="bad",
            template_revision=snap["Bound template revision"],
            log_revision=snap["Log revision"],
            step=snap["Step"],
            sequence=snap["Sequence"],
            choice="YES",
        )
        out, err, code = self.invoke("choose", **values)
        self.assertEqual(("", 1), (out, code))
        self.assertIn("PR108", err)
        self.assertEqual(before, self.log.read_bytes())
        # Frozen form is not upgraded by a newer file revision.
        values["choice"] = "yes"
        out, err, code = self.invoke("choose", **values)
        self.assertEqual(0, code, err)
        out, err, code = self.invoke("choose", **values)
        self.assertEqual(("", 1), (out, code))
        self.assertIn("PR310", err)

    def test_stale_source_inspects_frozen_ids_without_new_body(self):
        out, _, _ = self.invoke("show")
        snap, _ = self.mutate("start", fields(out), allow_loops=True)
        self.source.write_text("invalid NEW_PRIVATE_CONTENT")
        out, err, code = self.invoke("show", run_id=snap["Run"])
        self.assertEqual(0, code, err)
        self.assertEqual("template changed/unavailable", fields(out)["Blocked"])
        self.assertNotIn("NEW_PRIVATE_CONTENT", out)
        paused, _ = self.mutate("pause", fields(out))
        done, _ = self.mutate("abandon", paused)
        self.assertEqual("abandoned", done["Status"])

    def test_actual_subprocess_restart_nontty_and_space_quoting(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "procedure",
                "run",
                "show",
                str(self.source),
                "--id",
                "r",
                "--log",
                str(self.log),
            ],
            capture_output=True,
            text=True,
            input="yes\n",
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(self.log.exists())
        snap, _ = self.mutate("start", fields(result.stdout), allow_loops=True)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "procedure",
                "run",
                "show",
                str(self.source),
                "--id",
                "r",
                "--log",
                str(self.log),
                "--run-id",
                snap["Run"],
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(snap["Sequence"], fields(result.stdout)["Sequence"])
        self.assertEqual(1, len(read_log(self.log).events))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO is POSIX only")
    def test_fifo_log_rejected_without_blocking(self):
        os.mkfifo(self.log)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "procedure",
                "run",
                "show",
                str(self.source),
                "--id",
                "r",
                "--log",
                str(self.log),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual("", result.stdout)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("PR301", result.stderr)

    def test_request_receipt_inspection_and_actor_config_refusals(self):
        out, _, _ = self.invoke("show")
        snap, _ = self.mutate("start", fields(out), allow_loops=True)
        before = self.log.read_bytes()
        out, err, code = self.invoke("show", request_id="req1")
        self.assertEqual(0, code, err)
        self.assertIn("Committed request: req1", out)
        self.assertEqual(before, self.log.read_bytes())
        out, err, code = self.invoke("show", request_id="absent")
        self.assertEqual(("", 1), (out, code))
        self.assertIn("PR314", err)
        config = self.root / "config.json"
        config.write_text('{"ids":{"key":"uid"}}')
        out, err, code = run_cli(
            "--config",
            str(config),
            "procedure",
            "run",
            "show",
            str(self.source),
            "--id",
            "r",
            "--log",
            str(self.log),
        )
        self.assertEqual(("", 1), (out, code))
        self.assertIn("PR397", err)

    def test_every_lifecycle_operation_survives_a_fresh_process(self):
        def process(verb, values):
            command = [
                sys.executable,
                "-m",
                "lifetxt",
                "procedure",
                "run",
                verb,
                str(self.source),
                "--id",
                "r",
                "--log",
                str(self.log),
            ]
            for key, value in values.items():
                command.append("--" + key.replace("_", "-"))
                if value is not True:
                    command.append(str(value))
            result = subprocess.run(
                command, capture_output=True, text=True, input="", timeout=10
            )
            self.assertEqual(0, result.returncode, result.stderr)
            return fields(result.stdout)

        snap = process("show", {})
        for index, verb in enumerate(
            ("start", "next", "choose", "pause", "resume", "finish")
        ):
            values = dict(
                actor="alice",
                request_id="process-%d" % index,
                template_revision=snap.get(
                    "Bound template revision", snap["Template revision"]
                ),
                log_revision=snap["Log revision"],
                step=snap.get("Step", snap.get("Start step")),
                sequence=snap.get("Sequence", 0),
            )
            if "Run" in snap:
                values["run_id"] = snap["Run"]
            if verb == "start":
                values["allow_loops"] = True
            if verb == "choose":
                values["choice"] = "yes"
            snap = process(verb, values)
        self.assertEqual("completed", snap["Status"])
        self.assertEqual(6, len(read_log(self.log).events))
        self.assertEqual(SAMPLE, self.source.read_text())
