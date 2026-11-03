"""本地 Web 界面：标准库 http.server + 单页应用，零第三方依赖。

安全约束（本地工具也要守）：
* 只监听 127.0.0.1，不对外。
* 校验 Host 头，防 DNS rebinding。
* 每个请求要带启动时生成的随机 token（页面内嵌，非法页面拿不到）。
* 上传流式落盘，限制单文件大小，解析完立即删除。
"""

from __future__ import annotations

import json
import os
import secrets
import struct
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import __version__
from ..core import diag
from ..core.adb import Adb
from ..core.errors import IrisError
from ..core.image import lp as lp_mod
from ..core.image import sparse as sparse_mod
from ..core.partition import gpt as gpt_mod
from ..core.profile import load_cached, probe, save

BASE = Path(__file__).parent
STATIC = BASE / "static"
MAX_UPLOAD = 16 * 1024 * 1024 * 1024  # 单文件上限 16GB

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

LP_GEOMETRY_MAGIC = 0x616C4467


def detect_and_parse(path: Path) -> dict:
    """看头部 magic 决定用哪个解析器。"""
    size = path.stat().st_size
    with path.open("rb") as f:
        head = f.read(8192)

    if len(head) >= 520 and (head[512:520] == b"EFI PART" or (len(head) >= 4104 and head[4096:4104] == b"EFI PART")):
        return {"kind": "gpt", "table": gpt_mod.read_path(path).to_dict()}

    if len(head) >= 4100 and struct.unpack_from("<I", head, 4096)[0] == LP_GEOMETRY_MAGIC:
        return {"kind": "lp", "metadata": lp_mod.read_path(path).to_dict()}

    if sparse_mod.is_sparse(head):
        return {"kind": "sparse", "info": sparse_mod.describe_path(path)}

    raise IrisError(
        f"无法识别镜像格式（{size} 字节）：不是 GPT / super / sparse",
        hint="确认文件没有被截断；部分厂商的 .bin 需要先合并分段",
    )


class Handler(BaseHTTPRequestHandler):
    server_version = f"iris/{__version__}"
    protocol_version = "HTTP/1.1"

    # ---- 基础 ----
    def log_message(self, fmt: str, *args) -> None:
        if self.server.quiet:  # type: ignore[attr-defined]
            return
        print(f"  {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload: dict, code: int = 200) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _fail(self, code: int, message: str, hint: str = "") -> None:
        self._json({"error": message, "hint": hint}, code)

    # ---- 安全 ----
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost", "[::1]")

    def _token_ok(self) -> bool:
        token = self.headers.get("X-Iris-Token")
        return bool(token) and secrets.compare_digest(token, self.server.token)  # type: ignore[attr-defined]

    # ---- 路由 ----
    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._fail(403, "只接受 localhost 访问")
            return

        url = urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_text("utf-8").replace("__TOKEN__", self.server.token)  # type: ignore[attr-defined]
            self._send(200, html.encode("utf-8"), CONTENT_TYPES[".html"])
            return

        if path.startswith("/static/"):
            self._static(path)
            return

        if path.startswith("/api/"):
            if not self._token_ok():
                self._fail(401, "缺少或错误的 X-Iris-Token")
                return
            self._api_get(path, parse_qs(url.query))
            return

        self._fail(404, "not found")

    def _static(self, path: str) -> None:
        rel = path[len("/static/") :]
        target = (STATIC / rel).resolve()
        try:
            target.relative_to(STATIC.resolve())
        except ValueError:
            self._fail(403, "非法路径")
            return
        if not target.is_file():
            self._fail(404, "not found")
            return
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def _api_get(self, path: str, query: dict) -> None:
        try:
            if path == "/api/doctor":
                self._json(diag.run_check().to_dict())
                return

            if path == "/api/devices":
                adb = Adb(serial=(query.get("serial") or [None])[0])
                self._json({"devices": [d.__dict__ for d in adb.devices()]})
                return

            if path == "/api/info":
                serial = (query.get("serial") or [None])[0]
                refresh = (query.get("refresh") or ["0"])[0] == "1"
                cached = None if refresh else (load_cached(serial) if serial else None)
                if cached is not None:
                    self._json(cached.to_dict())
                    return
                prof = probe(Adb(serial=serial))
                save(prof)
                self._json(prof.to_dict())
                return

            if path == "/api/analyze":
                raw = (query.get("path") or [""])[0]
                if not raw:
                    self._fail(400, "缺少 path 参数")
                    return
                self._json(detect_and_parse(Path(unquote(raw))))
                return

            self._fail(404, "unknown endpoint")
        except IrisError as exc:
            self._fail(400, str(exc), exc.hint or "")
        except Exception as exc:  # noqa: BLE001
            self._fail(500, f"内部错误：{type(exc).__name__}: {exc}")

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._fail(403, "只接受 localhost 访问")
            return
        if not self._token_ok():
            self._fail(401, "缺少或错误的 X-Iris-Token")
            return

        url = urlparse(self.path)
        if url.path != "/api/upload":
            self._fail(404, "unknown endpoint")
            return

        name = unquote((parse_qs(url.query).get("name") or ["upload.bin"])[0])
        suffix = Path(name).suffix or ".bin"
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._fail(400, "Content-Length 非法")
            return
        if length <= 0:
            self._fail(400, "空请求体")
            return
        if length > MAX_UPLOAD:
            self._fail(413, f"文件超过上限（{MAX_UPLOAD // 1024**3}GB）")
            return

        tmp = tempfile.NamedTemporaryFile(prefix="iris-upload-", suffix=suffix, delete=False)
        tmp_path = Path(tmp.name)
        try:
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                tmp.write(chunk)
                remaining -= len(chunk)
            tmp.close()

            if remaining:
                self._fail(400, "上传不完整")
                return

            self._json(detect_and_parse(tmp_path))
        except IrisError as exc:
            self._fail(400, str(exc), exc.hint or "")
        except Exception as exc:  # noqa: BLE001
            self._fail(500, f"内部错误：{type(exc).__name__}: {exc}")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, *, quiet: bool = False):
        super().__init__(addr, handler)
        self.token = secrets.token_urlsafe(24)
        self.quiet = quiet


def serve(port: int = 0, *, open_browser: bool = True, quiet: bool = False) -> int:
    httpd = Server(("127.0.0.1", port), Handler, quiet=quiet)
    host, real_port = httpd.server_address[0], httpd.server_address[1]
    url = f"http://{host}:{real_port}/"

    print(f"Iris 界面已启动：{url}")
    print(f"（令牌已内嵌在页面里；只监听 127.0.0.1，按 Ctrl+C 退出）")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
    return 0
