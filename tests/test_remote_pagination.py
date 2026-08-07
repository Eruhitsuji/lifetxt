import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None

from lifetxt.webapp import create_app

_TICKET_COUNT = 12


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteTicketsPaginationRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_READER_PAGINATION"] = "reader-pagination"
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.writelines(
                "[ ] T Ticket_%02d record:ticket id:TK-%02d project:web "
                "visibility:shared ticket_status:new\n" % (index, index)
                for index in range(_TICKET_COUNT)
            )
        self.config = {
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": "reader",
                        "role": "reader",
                        "token_env": "REMOTE_READER_PAGINATION",
                        "projects": ["web"],
                        "visibilities": ["public", "shared"],
                    }
                ],
                "allow_loopback_http": True,
            },
        }
        self.client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=None,
                config=self.config,
                read_only=True,
            )
        )
        self.headers = {
            "Authorization": "Bearer reader-pagination",
            "X-Lifetxt-Remote-Version": "2",
        }

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("REMOTE_READER_PAGINATION", None)

    def _page(self, params):
        response = self.client.get(
            "/api/remote/v1/resources/tickets",
            headers=self.headers,
            params=params,
        )
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def test_paginating_through_the_real_route_visits_every_ticket_once(self):
        seen = []
        cursor = None
        for _ in range(_TICKET_COUNT + 3):
            params = {"limit": 5}
            if cursor:
                params["cursor"] = cursor
            body = self._page(params)
            seen.extend(row["id"] for row in body["data"]["tickets"])
            if not body["data"]["has_more"]:
                self.assertIsNone(body["data"]["next_cursor"])
                break
            cursor = body["data"]["next_cursor"]
        else:
            self.fail("pagination did not terminate")
        self.assertEqual(_TICKET_COUNT, len(seen))
        self.assertEqual(sorted(set(seen)), sorted(seen))

    def test_stale_since_revision_is_refused_through_the_real_route(self):
        first = self._page({"limit": 5})
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(
                "[ ] T Another_ticket record:ticket id:TK-NEW project:web "
                "visibility:shared ticket_status:new\n"
            )
        stale = self.client.get(
            "/api/remote/v1/resources/tickets",
            headers=self.headers,
            params={"since_revision": first["revision"]},
        )
        self.assertEqual(409, stale.status_code, stale.text)
        self.assertEqual("REMOTE_RESOURCE_REVISION_CHANGED", stale.json()["error"])


if __name__ == "__main__":
    unittest.main()
