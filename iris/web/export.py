"""导出单文件快照。

场景：沙箱/服务器进程起的端口，本机浏览器不一定能连上（Windows 沙箱会把
监听套接字限制在受限令牌内）。这时把页面连同数据一起导出成一个 .html，
双击就能看，不需要任何服务。

代价：快照是"拍下来的"，不能刷新。要实时用，还是走 `iris gui`。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core import diag
from ..core.adb import Adb
from ..core.errors import IrisError
from ..core.profile import probe

from .server import STATIC, detect_and_parse


def _inline(html: str) -> str:
    css = (STATIC / "style.css").read_text("utf-8")
    js = (STATIC / "app.js").read_text("utf-8")
    html = html.replace('<link rel="stylesheet" href="/static/style.css">', f"<style>\n{css}\n</style>")
    html = html.replace('<script src="/static/app.js"></script>', f"<script>\n{js}\n</script>")
    return html


def build_snapshot(image: str | None = None) -> str:
    data: dict = {}

    data["/api/doctor"] = diag.run_check().to_dict()

    try:
        data["/api/info"] = probe(Adb()).to_dict()
    except IrisError as exc:
        data["/api/info_error"] = str(exc)

    if image:
        data["/api/analyze"] = detect_and_parse(Path(image))

    html = (STATIC / "index.html").read_text("utf-8").replace("__TOKEN__", "snapshot")
    payload = json.dumps(data, ensure_ascii=False)
    html = _inline(html)
    html = html.replace(
        "</head>",
        f"<script>window.__IRIS_DATA__ = {payload};</script>\n</head>",
    )
    return html


def export(out: str | Path, image: str | None = None) -> Path:
    target = Path(out)
    target.write_text(build_snapshot(image), "utf-8")
    return target
