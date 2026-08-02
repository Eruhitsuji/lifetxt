import os, tempfile, unittest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None
from lifetxt.webapp import create_app


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteWebTests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_ALICE"] = "secret"
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "life.txt")
        open(self.path, "w").write(
            "[ ] T Fix_remote record:ticket id:T-1 project:web ticket_status:new\n"
        )
        self.config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "editor",
                        "token_env": "REMOTE_ALICE",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    }
                ],
                "allow_loopback_http": True,
            }
        }
        self.client = TestClient(
            create_app(paths=[self.path], writable_path=self.path, config=self.config)
        )
        self.headers = {"Authorization": "Bearer secret"}

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("REMOTE_ALICE", None)

    def test_auth_required(self):
        self.assertEqual(self.client.get("/api/remote/v1/session").status_code, 401)

    def test_capability_session_snapshot(self):
        self.assertEqual(
            self.client.get(
                "/api/remote/v1/capabilities", headers=self.headers
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/remote/v1/session", headers=self.headers).json()[
                "principal"
            ]["id"],
            "alice",
        )
        snap = self.client.get("/api/remote/v1/snapshot", headers=self.headers).json()
        self.assertEqual(snap["tickets"][0]["id"], "T-1")

    def test_write_requires_revision(self):
        r = self.client.post(
            "/api/remote/v1/write-check", headers=self.headers, json={}
        )
        self.assertIn(r.status_code, (409, 428))
        rev = self.client.get("/api/remote/v1/snapshot", headers=self.headers).json()[
            "revision"
        ]
        r = self.client.post(
            "/api/remote/v1/write-check",
            headers=dict(self.headers, **{"If-Match": rev}),
            json={"operation": "test"},
        )
        self.assertEqual(r.status_code, 200)
