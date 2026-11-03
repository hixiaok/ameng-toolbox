"""文件传输、录屏、无线调试（免 root）。"""

from __future__ import annotations

import time
from pathlib import Path

from ..adb import Adb
from ..errors import IrisError


def push(adb: Adb, local: str, remote: str) -> tuple[bool, str]:
    adb.require_device()
    src = Path(local)
    if not src.exists():
        raise IrisError(f"本地路径不存在：{src}")
    res = adb.push(str(src), remote, timeout=600)
    return res.ok, (res.out or res.err).strip()[:400]


def pull(adb: Adb, remote: str, local: str) -> tuple[bool, str]:
    adb.require_device()
    dest = Path(local)
    dest.parent.mkdir(parents=True, exist_ok=True)
    res = adb.pull(remote, str(dest), timeout=600)
    ok = res.ok and dest.exists()
    return ok, (str(dest) if ok else (res.err or res.out).strip()[:400])


def ls(adb: Adb, remote: str = "/sdcard") -> list[dict]:
    adb.require_device()
    res = adb.shell("ls", "-la", remote)
    if not res.ok:
        raise IrisError(f"读取 {remote} 失败", hint=(res.err or res.out).strip()[:200])
    items = []
    for line in res.stdout_lines[1:]:
        parts = line.split()
        if len(parts) < 8:
            continue
        items.append({
            "perm": parts[0],
            "size": parts[4],
            "name": " ".join(parts[7:]),
        })
    return items


def record(adb: Adb, seconds: int, out_dir: str) -> tuple[bool, str]:
    """录屏：设备内录到临时文件再拉回。"""
    adb.require_device()
    seconds = max(1, min(int(seconds), 180))
    remote = f"/sdcard/iris-rec-{int(time.time())}.mp4"
    rec = adb.shell("screenrecord", "--time-limit", str(seconds), remote, timeout=seconds + 30)
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / Path(remote).name
    pull_res = adb.pull(remote, str(dest), timeout=600)
    adb.shell("rm", "-f", remote)
    if rec.ok and pull_res.ok and dest.exists():
        return True, str(dest)
    return False, (rec.err or pull_res.err or "录屏失败").strip()[:300]


def tcpip(adb: Adb, port: int = 5555) -> tuple[bool, str]:
    """开启无线调试端口。设备与电脑需在同一网络。"""
    adb.require_device()
    res = adb.run("tcpip", str(port), timeout=30)
    ok = res.ok and "restarting" in (res.out + res.err).lower()
    return ok, (f"已在端口 {port} 开启无线调试" if ok else (res.err or res.out).strip()[:200])


def connect(host: str, port: int = 5555) -> tuple[bool, str]:
    from .adb import Adb as _Adb

    adb = _Adb()
    res = adb.run("connect", f"{host}:{port}", timeout=20)
    ok = res.ok and ("connected" in (res.out + res.err).lower())
    return ok, (res.out or res.err).strip()[:200]
