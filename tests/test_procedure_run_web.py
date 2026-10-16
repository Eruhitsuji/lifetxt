"""Authenticated HTTP run lifecycle, ownership, CAS and receipt boundaries."""

import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from tests.test_procedure_definition import SAMPLE


@unittest.skipIf(TestClient is None, "Web extras unavailable")
class ProcedureRunWebTests(unittest.TestCase):
    def setUp(self):
        from lifetxt import bootstrap_legacy_surfaces

        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app
        from lifetxt.procedure_web import _token

        self.create_app = create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "life.txt"
        self.path.write_text(SAMPLE, encoding="utf-8")
        self.log = Path(str(self.path) + ".procedure-runs.txt")
        self.config = {
            "api": {"token": "test-run-token"},
            "web": {"revision_mode": "required"},
        }
        self.app = create_app(
            [str(self.path)], writable_path=str(self.path), config=self.config
        )
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.source = _token(self.path)
        self.headers = {
            "Authorization": "Bearer test-run-token",
            "Origin": "http://testserver",
            "Sec-Fetch-Site": "same-origin",
        }
        self.counter = 0

    def snapshot(self, run_id=None, request_id=None, client=None):
        query = {"source": self.source, "root_id": "r"}
        if run_id is not None:
            query["run_id"] = run_id
        if request_id is not None:
            query["request_id"] = request_id
        response = (client or self.client).get(
            "/api/procedure-runs", params=query, headers=self.headers
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def payload(self, snap, operation="start", **extra):
        self.counter += 1
        value = {
            "source": self.source,
            "root_id": "r",
            "operation": operation,
            "request_id": "req-%d" % self.counter,
            "template_revision": snap["template_revision"],
            "log_revision": snap["log_revision"],
            "step": snap["step"],
            "sequence": snap["sequence"],
        }
        if operation != "start":
            value["run_id"] = snap["run_id"]
        else:
            value["allow_loops"] = True
        return dict(value, **extra)

    def send(self, snap, operation="start", expected=200, **extra):
        response = self.client.post(
            "/api/procedure-runs",
            json=self.payload(snap, operation, **extra),
            headers=dict(
                self.headers, **{"If-Match": '"' + snap["source_revision"] + '"'}
            ),
        )
        self.assertEqual(expected, response.status_code, response.text)
        return response.json()

    def test_lifecycle_is_explicit_and_keeps_templates_and_tasks_unchanged(self):
        before = self.path.read_bytes()
        snap = self.snapshot()
        self.assertFalse(self.log.exists())
        self.assertEqual("not_started", snap["status"])
        snap = self.send(snap)
        self.assertEqual(
            ("active", "a", 1), (snap["status"], snap["step"], snap["sequence"])
        )
        run = snap["run_id"]
        self.assertEqual("start", snap["receipt"]["event"])
        self.assertEqual("active", self.snapshot(run)["status"])
        snap = self.send(snap, "pause")
        self.assertEqual("paused", snap["status"])
        snap = self.send(snap, "resume")
        snap = self.send(snap, "next")
        self.assertEqual("q", snap["step"])
        self.assertEqual(
            {"yes", "no"},
            {a["choice"] for a in snap["actions"] if a["operation"] == "choose"},
        )
        snap = self.send(snap, "choose", choice="yes")
        self.assertEqual("e", snap["step"])
        snap = self.send(snap, "finish")
        self.assertEqual("completed", snap["status"])
        self.assertEqual([], snap["actions"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertNotIn(str(self.path), json.dumps(snap))
        self.assertNotIn("test-run-token", self.log.read_text())
        from lifetxt.procedure_run_store import read_log

        self.assertEqual(
            {"web-shared"}, {s.actor for s in read_log(self.log).states.values()}
        )

    def test_token_readonly_remote_and_public_shell(self):
        self.assertEqual(200, self.client.get("/procedures").status_code)
        self.assertEqual(401, self.client.get("/api/procedures").status_code)
        query = {"source": self.source, "root_id": "r"}
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            self.assertEqual(
                401,
                self.client.get(
                    "/api/procedure-runs", params=query, headers=headers
                ).status_code,
            )
        snap = self.send(self.snapshot())
        for config, readonly in (
            ({}, False),
            (self.config, True),
            (dict(self.config, remote={"enabled": False}), False),
        ):
            with TestClient(
                self.create_app(
                    [str(self.path)],
                    writable_path=str(self.path),
                    config=config,
                    read_only=readonly,
                )
            ) as client:
                if not config:
                    self.assertEqual(
                        403, client.get("/api/procedure-runs", params=query).status_code
                    )
                elif readonly:
                    data = self.snapshot(snap["run_id"], client=client)
                    self.assertEqual("READ_ONLY", data["read_only_reason"])
                    self.assertEqual([], data["actions"])
                    self.assertEqual(
                        403,
                        client.post(
                            "/api/procedure-runs", json={}, headers=self.headers
                        ).status_code,
                    )
        self.app.state.config["remote"] = {"enabled": True}
        self.assertEqual(
            403,
            self.client.get(
                "/api/procedure-runs", params=query, headers=self.headers
            ).status_code,
        )

    def test_origin_json_closed_payload_and_missing_if_match(self):
        snap = self.snapshot()
        value = self.payload(snap)
        valid = dict(self.headers, **{"If-Match": '"' + snap["source_revision"] + '"'})
        for bad in (
            {"Origin": "https://other.example"},
            {"Origin": "null"},
            {"Sec-Fetch-Site": "cross-site"},
            {"Origin": ""},
        ):
            self.assertEqual(
                403,
                self.client.post(
                    "/api/procedure-runs", json=value, headers=dict(valid, **bad)
                ).status_code,
            )
        self.assertEqual(
            415,
            self.client.post(
                "/api/procedure-runs",
                content=json.dumps(value),
                headers=dict(valid, **{"Content-Type": "text/plain"}),
            ).status_code,
        )
        for bad in (
            dict(value, actor="cli"),
            dict(value, log="private"),
            dict(value, operation={}),
            dict(value, sequence=True),
            dict(value, allow_loops="yes"),
            {},
        ):
            self.assertEqual(
                422,
                self.client.post(
                    "/api/procedure-runs", json=bad, headers=valid
                ).status_code,
            )
        self.assertEqual(
            428,
            self.client.post(
                "/api/procedure-runs", json=value, headers=self.headers
            ).status_code,
        )
        self.assertEqual(
            413,
            self.client.post(
                "/api/procedure-runs",
                content=b" " * 8193,
                headers=dict(valid, **{"Content-Type": "application/json"}),
            ).status_code,
        )
        duplicate = json.dumps(value)[:-1] + ',"operation":"start"}'
        self.assertEqual(
            422,
            self.client.post(
                "/api/procedure-runs",
                content=duplicate,
                headers=dict(valid, **{"Content-Type": "application/json"}),
            ).status_code,
        )
        self.assertFalse(self.log.exists())

    def test_two_runs_tab_cas_duplicate_and_original_receipt(self):
        first = self.send(self.snapshot())
        second = self.send(self.snapshot())
        old = self.snapshot(first["run_id"])
        value = self.payload(old, "next")
        headers = dict(self.headers, **{"If-Match": '"' + old["source_revision"] + '"'})

        def post(_):
            return self.client.post(
                "/api/procedure-runs", json=value, headers=headers
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual([200, 409], sorted(pool.map(post, (1, 2))))
        self.assertEqual(409, post(3))
        self.assertEqual(2, self.snapshot(first["run_id"])["sequence"])
        self.assertEqual(1, self.snapshot(second["run_id"])["sequence"])
        receipt = self.snapshot(request_id=value["request_id"])
        self.assertEqual(2, receipt["receipt"]["sequence"])
        self.assertEqual("next", receipt["receipt"]["event"])
        self.assertIsNone(self.snapshot(request_id="never-committed")["receipt"])

    def test_foreign_actor_source_root_request_and_task_state_refuse(self):
        from lifetxt.procedure_run_store import inspect_run, write_run

        base = inspect_run(self.path, "r", self.log)
        foreign = write_run(
            self.path,
            "r",
            self.log,
            "start",
            actor="cli-alice",
            request_id="foreign-request",
            expected_template_revision=base.template_revision,
            expected_log_revision=base.log_revision,
            expected_step=base.start_step,
            expected_sequence=0,
            allow_loops=True,
        )
        run = foreign.state.run_id
        before = self.log.read_bytes()
        self.assertEqual([], self.snapshot()["runs"])
        for extra in ({"run_id": run}, {"request_id": "foreign-request"}):
            response = self.client.get(
                "/api/procedure-runs",
                params=dict(source=self.source, root_id="r", **extra),
                headers=self.headers,
            )
            self.assertEqual(404, response.status_code)
            self.assertNotIn("cli-alice", response.text)
        payload = self.payload(self.snapshot(), "next", run_id=run, sequence=1)
        response = self.client.post(
            "/api/procedure-runs",
            json=payload,
            headers=dict(
                self.headers, **{"If-Match": '"' + base.template_revision + '"'}
            ),
        )
        self.assertEqual(404, response.status_code)
        self.assertEqual(before, self.log.read_bytes())
        self.assertEqual(
            404,
            self.client.get(
                "/api/procedure-runs",
                params={"source": "other", "root_id": "r"},
                headers=self.headers,
            ).status_code,
        )

    def test_changed_missing_source_allows_only_disposition(self):
        run = self.send(self.snapshot())["run_id"]
        self.path.write_text("invalid changed source", encoding="utf-8")
        snap = self.snapshot(run)
        self.assertTrue(snap["blocked"])
        self.assertIsNone(snap["instruction"])
        self.assertEqual(
            {"pause", "abandon"}, {a["operation"] for a in snap["actions"]}
        )
        self.send(snap, "next", expected=409)
        snap = self.send(snap, "pause")
        self.path.unlink()
        snap = self.snapshot(run)
        snap = self.send(snap, "abandon")
        self.assertEqual("abandoned", snap["status"])
        self.assertFalse(self.path.exists())

    def test_readonly_source_and_restart_sidecar_is_not_an_item(self):
        run = self.send(self.snapshot())
        from lifetxt.procedure_web import _token

        other = Path(self.temp.name) / "other.txt"
        other.write_text("[ ] T Other id:other\n", encoding="utf-8")
        with TestClient(
            self.create_app(
                [str(self.path), str(other), str(self.log)],
                writable_path=str(self.path),
                config=self.config,
            )
        ) as client:
            data = client.get("/api/items", headers=self.headers).json()
            self.assertNotIn("procedure_event", json.dumps(data))
            response = client.get(
                "/api/procedure-runs",
                params={"source": _token(other), "root_id": "r"},
                headers=self.headers,
            )
            self.assertEqual(403, response.status_code)
        self.assertEqual(run["run_id"], self.snapshot(run["run_id"])["run_id"])

    def test_generated_readonly_and_post_inspection_ownership_change(self):
        from dataclasses import replace
        from lifetxt.procedure_run_store import inspect_run

        data = self.send(self.snapshot())
        self.path.chmod(0o444)
        self.assertEqual(
            "SOURCE_READ_ONLY", self.snapshot(data["run_id"])["read_only_reason"]
        )
        self.send(self.snapshot(data["run_id"]), "next", expected=403)
        self.path.chmod(0o644)
        self.app.state.config["generated_paths"] = [str(self.path)]
        self.assertEqual([], self.snapshot(data["run_id"])["actions"])
        self.app.state.config.pop("generated_paths")
        original = inspect_run(self.path, "r", self.log, data["run_id"])
        foreign = replace(
            original, state=replace(original.state, actor="other-operator")
        )
        with patch("lifetxt.procedure_run_web.inspect_run", return_value=foreign):
            response = self.client.get(
                "/api/procedure-runs",
                params={
                    "source": self.source,
                    "root_id": "r",
                    "run_id": data["run_id"],
                },
                headers=self.headers,
            )
        self.assertEqual(404, response.status_code)
        self.assertNotIn("other-operator", response.text)

    def test_uncertain_outcome_receipt_and_pending_journal_refuse_retry(self):
        from lifetxt.procedure_run_store import write_run

        snap = self.snapshot()
        value = self.payload(snap)

        def committed_but_uncertain(*args, **kwargs):
            write_run(*args, **kwargs)
            raise OSError("private storage path")

        with patch(
            "lifetxt.procedure_run_web.write_run", side_effect=committed_but_uncertain
        ):
            result = self.client.post(
                "/api/procedure-runs",
                json=value,
                headers=dict(
                    self.headers, **{"If-Match": '"' + snap["source_revision"] + '"'}
                ),
            )
        self.assertEqual(409, result.status_code)
        self.assertNotIn("private storage", result.text)
        found = self.snapshot(request_id=value["request_id"])
        self.assertEqual(1, found["sequence"])
        self.assertEqual("start", found["receipt"]["event"])
        from lifetxt.multi_target import MultiTargetError

        with patch(
            "lifetxt.procedure_run_web.write_run",
            side_effect=MultiTargetError("private journal"),
        ):
            self.send(found, "next", expected=409)
        self.assertEqual(1, self.snapshot(found["run_id"])["sequence"])

        # Exercise actual corrupt durable evidence through the real store admission.
        from lifetxt.transaction_journal import journal_directory

        journal = (
            Path(journal_directory(self.app.state.config, writable_path=self.log))
            / "corrupt-fixture"
            / "journal.json"
        )
        journal.parent.mkdir(parents=True)
        journal.write_text("{invalid json", encoding="utf-8")
        before = self.log.read_bytes()
        error = self.send(self.snapshot(found["run_id"]), "next", expected=409)
        self.assertEqual(before, self.log.read_bytes())
        self.assertNotIn(str(journal), json.dumps(error))
        self.assertTrue(journal.exists())
