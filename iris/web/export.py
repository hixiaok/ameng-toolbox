"""导出单文件快照。

关键点：**服务端预渲染**。早期版本只把数据塞进 JS，页面内容全靠脚本现场生成，
脚本一挂就是一片空白（"功能界面啥都没有"）。现在所有区块在导出时就已经写进
DOM，JS 只负责交互增强——即使脚本报错，页面依然是完整的。
"""

from __future__ import annotations

import html as html_mod
import json
from pathlib import Path

from ..core import diag
from ..core.adb import Adb
from ..core.errors import IrisError
from ..core.profile import probe

from .server import STATIC, detect_and_parse


def _e(value) -> str:
    return html_mod.escape(str(value if value is not None else "—"), quote=True)


def _human(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    v = float(n)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{int(v)}B" if i == 0 else f"{v:.1f}{units[i]}"


# ---- 各区块的静态 HTML --------------------------------------------
def render_doctor(report: dict) -> str:
    out = []
    for c in report.get("checks", []):
        hint = ""
        if c.get("hint") and c.get("status") != "ok":
            hint = f'<div class="hint">{_e(c["hint"])}</div>'
        out.append(
            f'<div class="row {_e(c.get("status"))}"><i class="dot"></i>'
            f'<div class="k">{_e(c.get("name"))}</div>'
            f'<div class="v">{_e(c.get("detail"))}</div>{hint}</div>'
        )
    return "".join(out)


def render_chips(report: dict) -> str:
    def count(s):
        return sum(1 for c in report.get("checks", []) if c.get("status") == s)

    return (
        f'<span class="chip fail"><i></i>{count("fail")} 失败</span>'
        f'<span class="chip warn"><i></i>{count("warn")} 警告</span>'
        f'<span class="chip ok"><i></i>{count("ok")} 通过</span>'
    )


def render_fields(profile: dict) -> str:
    rows = [
        ("序列号", profile.get("serial")),
        ("机型", f'{profile.get("brand", "")} {profile.get("model", "")}'.strip()),
        ("代号", profile.get("codename")),
        ("SoC", f'{profile.get("soc_manufacturer", "")} {profile.get("soc_model", "")}'.strip()),
        ("系统", f'Android {profile.get("android_release") or "?"} · SDK {profile.get("sdk") or "?"}'),
        ("架构", profile.get("abi")),
        ("安全补丁", profile.get("security_patch")),
        ("槽位", f'A/B（{profile.get("slot_suffix") or "?"}）' if profile.get("ab_update") else "单槽位"),
        ("ROOT", "是" if profile.get("root") else "否"),
        ("by-name 根", profile.get("by_name_root") or "未探测到"),
        ("块设备", profile.get("block_device") or "未知"),
        ("已知分区", f'{len(profile.get("partitions") or {})} 个'),
    ]
    return "".join(
        f'<div class="field"><em>{_e(k)}</em><b>{_e(v)}</b></div>' for k, v in rows
    )


def render_probes(profile: dict) -> str:
    rows = []
    for p in profile.get("probes", []):
        mark = '<span style="color:var(--ok)">✓</span>' if p.get("ok") else '<span style="color:var(--fail)">✗</span>'
        rows.append(
            f'<tr><td class="mono">{_e(p.get("name"))}</td><td>{mark}</td>'
            f'<td class="mono" style="color:var(--muted)">{_e(p.get("evidence"))}</td></tr>'
        )
    return (
        "<table><thead><tr><th>探测项</th><th>结果</th><th>证据</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_image(analysis: dict) -> str:
    kind = analysis.get("kind")

    if kind == "gpt":
        t = analysis["table"]
        rows = "".join(
            f'<tr><td style="color:var(--muted)">{p["index"]}</td>'
            f'<td class="mono">{_e(p["name"]) or "(未命名)"}</td>'
            f'<td class="mono" style="color:var(--muted)">{p["type"][:8]}</td>'
            f'<td class="mono">{p["first_lba"]}</td>'
            f'<td>{_human(p["sectors"] * t["sector_size"])}</td></tr>'
            for p in t["partitions"]
        )
        meta = (
            f'<p class="meta">扇区 <b>{t["sector_size"]}B</b> · '
            f'{"主表" if t["source"] == "primary" else "备份表"} · '
            f'CRC <b>{"通过" if t["crc_ok"] else "异常"}</b> · 磁盘 <b>{_e(t["disk_guid"])}</b></p>'
        )
        table = (
            '<div class="table-wrap"><table><thead><tr><th>#</th><th>名称</th><th>类型</th>'
            '<th>起始 LBA</th><th>大小</th></tr></thead><tbody>'
            f"{rows}</tbody></table></div>"
        )
        return meta + table

    if kind == "lp":
        m = analysis["metadata"]
        rows = "".join(
            f'<tr><td class="mono">{_e(p["name"])}</td><td>{p["size_human"]}</td>'
            f'<td style="color:var(--muted)">{p["extent_count"]}</td>'
            f'<td style="color:var(--muted)">{p["group_index"]}</td></tr>'
            for p in m["partitions"]
        )
        warn = ""
        if m.get("warnings"):
            warn = f' · <b style="color:var(--warn)">{_e("；".join(m["warnings"]))}</b>'
        meta = (
            f'<p class="meta">版本 <b>{m["header"]["version"]}</b> · '
            f'header <b>{m["header"]["header_size"]}B</b> · '
            f'块大小 <b>{m["geometry"]["logical_block_size"]}B</b> · '
            f'逻辑容量 <b>{_human(m["logical_size"])}</b>{warn}</p>'
        )
        table = (
            '<div class="table-wrap"><table><thead><tr><th>分区</th><th>大小</th>'
            '<th>extent 数</th><th>组</th></tr></thead><tbody>'
            f"{rows}</tbody></table></div>"
        )
        return meta + table

    if kind == "sparse":
        s = analysis["info"]
        stats = "，".join(f"{k} ×{v}" for k, v in s["chunk_stats"].items())
        return (
            f'<p class="meta">块大小 <b>{s["block_size"]}B</b> · <b>{s["total_blocks"]}</b> 块 · '
            f'展开后 <b>{_human(s["expanded_size"])}</b> · <b>{s["total_chunks"]}</b> 个 chunk'
            f"（{_e(stats)}）</p>"
        )

    return '<p class="meta">未识别的镜像格式</p>'


def render_about(version: str) -> str:
    rows = [
        ("版本", f"v{version}"),
        ("许可证", "GPL-3.0"),
        ("运行时", "Python 标准库，无第三方依赖"),
        ("数据", "全程本地处理，不上传"),
        ("第三方二进制", "不打包"),
        ("前端", "单页 HTML/CSS/JS + http.server"),
    ]
    return "".join(f'<div class="field"><em>{_e(k)}</em><b>{_e(v)}</b></div>' for k, v in rows)


def _inline(html: str) -> str:
    css = (STATIC / "style.css").read_text("utf-8")
    js = (STATIC / "app.js").read_text("utf-8")
    html = html.replace('<link rel="stylesheet" href="/static/style.css">', f"<style>\n{css}\n</style>")
    html = html.replace('<script src="/static/app.js"></script>', f"<script>\n{js}\n</script>")
    return html


def build_snapshot(image: str | None = None, version: str = "0.2.0") -> str:
    from .. import __version__

    version = __version__
    data: dict = {}
    data["/api/doctor"] = diag.run_check().to_dict()

    profile = None
    try:
        profile = probe(Adb()).to_dict()
        data["/api/info"] = profile
    except IrisError as exc:
        data["/api/info_error"] = str(exc)

    analysis = None
    if image:
        analysis = detect_and_parse(Path(image))
        data["/api/analyze"] = analysis

    page = (STATIC / "index.html").read_text("utf-8").replace("__TOKEN__", "snapshot")

    # ---- 预渲染注入 ----
    page = page.replace(
        '<span class="group-chips" id="doctor-chips"></span>',
        f'<span class="group-chips" id="doctor-chips">{render_chips(data["/api/doctor"])}</span>',
    )
    page = page.replace('<div class="rows" id="doctor-list"></div>',
                        f'<div class="rows" id="doctor-list">{render_doctor(data["/api/doctor"])}</div>')

    if profile:
        page = page.replace('<div id="device-empty" class="empty">',
                            '<div id="device-empty" class="empty hidden">')
        page = page.replace('<div id="device-content" class="hidden">', '<div id="device-content">')
        page = page.replace('<div class="fields" id="device-fields"></div>',
                            f'<div class="fields" id="device-fields">{render_fields(profile)}</div>')
        page = page.replace('<div class="table-wrap" id="probe-table"></div>',
                            f'<div class="table-wrap" id="probe-table">{render_probes(profile)}</div>')
    else:
        msg = data.get("/api/info_error", "没有检测到设备")
        page = page.replace("<b>没有检测到设备</b>", f"<b>{_e(msg)}</b>")

    if analysis:
        name = Path(image).name if image else "镜像"
        page = page.replace(
            '<span class="path" id="file-name">未选择 · 也可以把文件直接拖进窗口</span>',
            f'<span class="path" id="file-name">{_e(name)}</span>',
        )
        page = page.replace('<div id="image-result" class="hidden">', '<div id="image-result">')
        page = page.replace('<span class="tag" id="image-kind">-</span>',
                            f'<span class="tag" id="image-kind">'
                            f'{ {"gpt": "GPT 分区表", "lp": "super 元数据", "sparse": "sparse 镜像"}.get(analysis["kind"], analysis["kind"]) }</span>')
        page = page.replace('<span class="group-note" id="image-name"></span>',
                            f'<span class="group-note" id="image-name">{_e(name)}</span>')
        page = page.replace('<div id="image-body"></div>',
                            f'<div id="image-body">{render_image(analysis)}</div>')

    page = page.replace('<div class="fields" id="about-fields"></div>',
                        f'<div class="fields" id="about-fields">{render_about(version)}</div>')

    page = _inline(page)
    payload = json.dumps(data, ensure_ascii=False)
    page = page.replace("</head>", f"<script>window.__IRIS_DATA__ = {payload};</script>\n</head>")
    return page


def export(out: str | Path, image: str | None = None) -> Path:
    target = Path(out)
    target.write_text(build_snapshot(image), "utf-8")
    return target
