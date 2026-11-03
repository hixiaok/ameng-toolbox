from __future__ import annotations

import http.client
import json
import threading
import unittest

from iris.web.server import Handler, Server

from .payload_fixture import build_payload


class TestPayloadApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = Server(("127.0.0.1", 0), Handler, quiet=True)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.token = cls.httpd.token

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        merged = {"Host": f"127.0.0.1:{self.port}", "X-Iris-Token": self.token}
        merged.update(headers or {})
        conn.request(method, path, body=body, headers=merged)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, data

    def test_upload_and_extract(self):
        boot = bytes((i * 5) % 256 for i in range(4096 * 2))
        blob = build_payload({"boot": boot, "system": b"\x22" * 4096 * 3})

        status, body = self.req("POST", "/api/upload?name=payload.bin", body=blob,
                                headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(status, 200, body[:300])
        data = json.loads(body)
        self.assertEqual(data["kind"], "payload")
        self.assertIn("ticket", data)
        self.assertEqual([p["name"] for p in data["payload"]["partitions"]], ["boot", "system"])

        ticket = data["ticket"]
        status, raw = self.req("GET", f"/api/extract?ticket={ticket}&part=boot")
        self.assertEqual(status, 200)
        self.assertEqual(raw, boot)

        status, _ = self.req("GET", f"/api/extract?ticket={ticket}&part=nope")
        self.assertEqual(status, 404)

        status, _ = self.req("GET", "/api/extract?ticket=bogus&part=boot")
        self.assertEqual(status, 410)


if __name__ == "__main__":
    unittest.main()
