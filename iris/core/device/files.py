"""文件传输、root 浏览、录屏、无线调试。

非 root 路径只用 adb push/pull（走 adbd 的 shell 身份）；需要读 /data 之类
受保护目录时，先 `su cp` 到 /data/local/tmp 再 pull——不让 adb 直接去啃权限，
因为 adbd 以 shell 身份运行时 pull 会被 SELinux 拒掉，报错还很难懂。
"""

from __future__ import annotations

import shlex
import time
from pathlib import Path

from ..adb import Adb
from ..errors import IrisError
from .root import Root

ROOT_TMP = "/data/local/tmp/iris"
MAX_READ = 512 * 1024  # 文本预览上限，再大就让用户先 pull


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


def pull_root(adb: Adb, remote: str, local: str, root: Root | None = None) -> tuple[bool, str]:
    """以 root 复制到临时目录再 pull，适用于 /data 下的文件。"""
    root = root or Root(adb)
    root.ensure()
    dest = Path(local)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{ROOT_TMP}/pull-{int(time.time())}-{Path(remote).name}"
    cp = root.run(f"mkdir -p {ROOT_TMP} && cp -f {shlex.quote(remote)} {shlex.quote(tmp)}", timeout=300)
    if not cp.ok:
        return False, (cp.err or cp.out).strip()[:300]
    res = adb.pull(tmp, str(dest), timeout=600)
    root.run(f"rm -f {shlex.quote(tmp)}", timeout=30)
    ok = res.ok and dest.exists()
    return ok, (str(dest) if ok else (res.err or res.out).strip()[:300])


def push_root(adb: Adb, local: str, remote: str, root: Root | None = None, *, mode: str = "644") -> tuple[bool, str]:
    """把文件塞进受保护目录：先 push 到 /data/local/tmp，再 su cp + chmod。"""
    src = Path(local)
    if not src.is_file():
        raise IrisError(f"本地文件不存在：{src}")
    root = root or Root(adb)
    root.ensure()
    tmp = f"{ROOT_TMP}/push-{int(time.time())}-{src.name}"
    root.run(f"mkdir -p {ROOT_TMP}", timeout=30)
    res = adb.push(str(src), tmp, timeout=600)
    if not res.ok:
        return False, (res.err or res.out).strip()[:300]
    cmd = (
        f"cp -f {shlex.quote(tmp)} {shlex.quote(remote)} && "
        f"chmod {mode} {shlex.quote(remote)} && "
        f"rm -f {shlex.quote(tmp)}"
    )
    out = root.run(cmd, timeout=120)
    if not out.ok:
        root.run(f"rm -f {shlex.quote(tmp)}", timeout=30)
        return False, (out.err or out.out).strip()[:300]
    return True, remote


def ls(adb: Adb, remote: str = "/sdcard", root: Root | None = None) -> list[dict]:
    adb.require_device()
    if root is not None:
        res = root.run(f"ls -la {shlex.quote(remote)}", timeout=45)
    else:
        res = adb.shell("ls", "-la", remote)
    if not res.ok:
        hint = (res.err or res.out).strip()[:200]
        if not root:
            hint += "；该目录可能需要 root，打开上面的「以 root 浏览」再试"
        raise IrisError(f"读取 {remote} 失败", hint=hint)
    items = []
    for line in res.stdout_lines[1:]:
        if line.startswith("total "):
            continue
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        name = parts[7]
        if name in (".", ".."):
            continue
        items.append({
            "perm": parts[0],
            "size": parts[4],
            "name": name,
            "dir": parts[0].startswith("d"),
        })
    items.sort(key=lambda i: (not i["dir"], i["name"].lower()))
    return items


def read_text(adb: Adb, remote: str, root: Root | None = None, *, max_bytes: int = MAX_READ) -> dict:
    """读取文本文件用于预览；超过上限截断并标记。"""
    adb.require_device()
    limit = max(1024, min(int(max_bytes), MAX_READ))
    if root is not None:
        res = root.run(f"head -c {limit} {shlex.quote(remote)}", timeout=45)
    else:
        res = adb.shell("head", "-c", str(limit), remote, timeout=45)
    if not res.ok:
        raise IrisError(f"读取 {remote} 失败", hint=(res.err or res.out).strip()[:200])
    size_res = adb.shell("stat", "-c", "%s", remote, timeout=20)
    size = int(size_res.out.strip()) if size_res.ok and size_res.out.strip().isdigit() else 0
    return {
        "path": remote,
        "text": res.out,
        "truncated": bool(size and size > limit),
        "size": size,
    }


def mkdir(adb: Adb, remote: str, root: Root | None = None) -> tuple[bool, str]:
    if root is not None:
        res = root.run(f"mkdir -p {shlex.quote(remote)}", timeout=30)
    else:
        res = adb.shell("mkdir", "-p", remote, timeout=30)
    return res.ok, (res.err or res.out).strip()[:200] or remote


def remove(adb: Adb, remote: str, root: Root | None = None) -> tuple[bool, str]:
    if root is not None:
        res = root.run(f"rm -f {shlex.quote(remote)}", timeout=30)
    else:
        res = adb.shell("rm", "-f", remote, timeout=30)
    return res.ok, (res.err or res.out).strip()[:200] or remote


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
