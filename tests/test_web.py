from __future__ import annotations

import http.client
import json
import threading
import unittest

from iris.web.server import Handler, Server

from .gpt_fixture import build as build_gpt
from .image_fixture import build_sparse, build_super


class TestWeb(unittest.TestCase):
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

    def req(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        merged = {"Host": f"127.0.0.1:{self.port}"}
        merged.update(headers or {})
        conn.request(method, path, body=body, headers=merged)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, data

    def auth(self) -> dict:
        return {"X-Iris-Token": self.token}

    def test_index_served_with_token(self):
        status, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        text = body.decode("utf-8")
        self.assertIn("Iris", text)
        self.assertIn(self.token, text)

    def test_static_js(self):
        status, body = self.req("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"IRIS_TOKEN", body)

    def test_api_requires_token(self):
        status, body = self.req("GET", "/api/doctor")
        self.assertEqual(status, 401)
        self.assertIn("token", body.decode("utf-8").lower())

    def test_index_has_version(self):
        from iris import __version__

        status, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(f"v{__version__}".encode(), body)

    def test_root_endpoint_reports_no_device(self):
        status, body = self.req("GET", "/api/root", headers=self.auth())
        self.assertEqual(status, 400)
        data = json.loads(body)
        self.assertIn("设备", data["error"])
        self.assertTrue(data["hint"])

    def test_post_part_plan_requires_name(self):
        status, body = self.req(
            "POST", "/api/part/plan", body=json.dumps({"action": "backup"}).encode(),
            headers={**self.auth(), "Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertIn("分区名", json.loads(body)["error"])

    def test_post_bad_json(self):
        status, body = self.req(
            "POST", "/api/modules/toggle", body=b"not json",
            headers={**self.auth(), "Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertIn("JSON", json.loads(body)["error"])

    def test_post_unknown_endpoint(self):
        status, _ = self.req(
            "POST", "/api/nope", body=b"{}",
            headers={**self.auth(), "Content-Type": "application/json"},
        )
        self.assertEqual(status, 404)

    def test_api_doctor_ok(self):
        status, body = self.req("GET", "/api/doctor", headers=self.auth())
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("checks", data)
        self.assertTrue(data["checks"])

    def test_static_traversal_blocked(self):
        status, _ = self.req("GET", "/static/../server.py")
        self.assertIn(status, (403, 404))

    def test_bad_host_rejected(self):
        status, _ = self.req("GET", "/api/doctor", headers={**self.auth(), "Host": "evil.example:80"})
        self.assertEqual(status, 403)

    def _upload(self, payload: bytes, name: str):
        return self.req(
            "POST",
            f"/api/upload?name={name}",
            body=payload,
            headers={**self.auth(), "Content-Type": "application/octet-stream"},
        )

    def test_upload_gpt(self):
        status, body = self._upload(build_gpt(["boot_a", "super"]), "gpt.bin")
        self.assertEqual(status, 200, body[:200])
        data = json.loads(body)
        self.assertEqual(data["kind"], "gpt")
        self.assertEqual(len(data["table"]["partitions"]), 2)

    def test_upload_super(self):
        img = build_super([{"name": "system_a", "extents": [(2048, 1024)]}])
        status, body = self._upload(img, "super.img")
        self.assertEqual(status, 200, body[:200])
        data = json.loads(body)
        self.assertEqual(data["kind"], "lp")
        self.assertEqual(data["metadata"]["partitions"][0]["name"], "system_a")

    def test_upload_sparse(self):
        img = build_sparse(bytes(range(256)) * 64)
        status, body = self._upload(img, "system.img")
        self.assertEqual(status, 200, body[:200])
        data = json.loads(body)
        self.assertEqual(data["kind"], "sparse")
        self.assertEqual(data["info"]["chunk_stats"]["raw"], 2)

    def test_upload_unknown_format(self):
        status, body = self._upload(b"\x00" * 8192, "junk.bin")
        self.assertEqual(status, 400)
        self.assertIn("无法识别", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
