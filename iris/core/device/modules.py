"""Magisk / KernelSU / APatch 模块管理。

三个管理器共用 `/data/adb/modules` 的目录约定：

* 每个子目录一个模块，`module.prop` 是 key=value；
* 目录里出现 `disable` 文件 = 禁用，出现 `remove` = 重启后卸载，
  `update` = 下次开机执行模块自带的 update-binary。

差别只在安装和日志：Magisk 用 `magisk --install-module`，KernelSU 用
`ksud module install`，APatch 用 `apd module install`。安装前先把 zip 推到
`/data/local/tmp`，装完删掉，避免在用户存储里留垃圾。
"""

from __future__ import annotations

import shlex
import time
from dataclasses import asdict, dataclass, field

from ..adb import Adb
from ..errors import IrisError
from .root import Root, RootStatus

MODULES_DIR = "/data/adb/modules"

INSTALL_CMDS = {
    "Magisk": "magisk --install-module {zip}",
    "KernelSU": "ksud module install {zip}",
    "APatch": "apd module install {zip}",
}

LOG_PATHS = {
    "Magisk": "/cache/magisk.log",
    "KernelSU": "/data/adb/ksu/logs/",
    "APatch": "/data/adb/ap/logs/",
}


class ModuleError(IrisError):
    exit_code = 10


@dataclass
class Module:
    name: str
    version: str = ""
    version_code: str = ""
    author: str = ""
    description: str = ""
    enabled: bool = True
    pending_remove: bool = False
    pending_update: bool = False
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Manager:
    name: str = "未识别"
    version: str = ""
    modules_dir: str = MODULES_DIR
    can_install: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _script() -> str:
    # 一次 su 调用把所有模块的元数据取回来；=== 作为分隔符
    return (
        f'for d in {MODULES_DIR}/*; do '
        f'[ -d "$d" ] || continue; n=$(basename "$d"); echo "=== $n"; '
        f'cat "$d/module.prop" 2>/dev/null; '
        f'[ -e "$d/disable" ] && echo "__DISABLE__"; '
        f'[ -e "$d/remove" ] && echo "__REMOVE__"; '
        f'[ -e "$d/update" ] && echo "__UPDATE__"; '
        f'done'
    )


def _parse(dump: str) -> list[Module]:
    modules: list[Module] = []
    cur: Module | None = None
    props: dict[str, str] = {}

    def flush() -> None:
        nonlocal cur, props
        if cur is None:
            return
        cur.version = props.get("version", "")
        cur.version_code = props.get("versionCode", "")
        cur.author = props.get("author", "")
        cur.description = props.get("description", "")
        prop_name = props.get("name", "")
        if prop_name:
            cur.name = prop_name
        modules.append(cur)
        cur, props = None, {}

    for raw in dump.splitlines():
        line = raw.strip()
        if line.startswith("=== "):
            flush()
            cur = Module(name=line[4:].strip())
            continue
        if cur is None:
            continue
        if line == "__DISABLE__":
            cur.enabled = False
        elif line == "__REMOVE__":
            cur.pending_remove = True
        elif line == "__UPDATE__":
            cur.pending_update = True
        elif "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
    flush()
    modules.sort(key=lambda m: (m.enabled, m.name.lower()))
    return modules


def manager(adb: Adb, root: Root | None = None, status: RootStatus | None = None) -> Manager:
    root = root or Root(adb)
    st = status or root.refresh()
    st.require()
    mgr = Manager(name=st.manager, version=st.version)
    mgr.can_install = st.manager in INSTALL_CMDS

    if st.manager == "未识别":
        # 有些设备管理器命令不在 PATH，但目录在
        for name, path in (("Magisk", "/data/adb/magisk"), ("KernelSU", "/data/adb/ksu"), ("APatch", "/data/adb/ap")):
            if root.test(f"ls -d {path}"):
                mgr.name, mgr.can_install = name, name in INSTALL_CMDS
                break
        if mgr.name == "未识别":
            mgr.notes.append("检测到 su，但没认出是哪个管理器：模块功能可能不可用")
    if mgr.name != "未识别" and not mgr.can_install:
        mgr.notes.append(f"{mgr.name} 不支持命令行安装模块")
    return mgr


def list_modules(adb: Adb, root: Root | None = None) -> list[Module]:
    root = root or Root(adb)
    root.ensure()
    res = root.run(_script(), timeout=45)
    if not res.ok:
        raise ModuleError("读取模块列表失败", hint=(res.err or res.out).strip()[:300])
    return _parse(res.out)


def toggle(adb: Adb, name: str, enabled: bool, root: Root | None = None) -> tuple[bool, str]:
    _check_name(name)
    root = root or Root(adb)
    root.ensure()
    flag = f"{MODULES_DIR}/{name}/disable"
    cmd = f"rm -f {shlex.quote(flag)}" if enabled else f"touch {shlex.quote(flag)}"
    res = root.run(cmd, timeout=20)
    action = "启用" if enabled else "禁用"
    if not res.ok:
        return False, f"{action}失败：{(res.err or res.out).strip()[:200]}"
    return True, f"已{action} {name}（重启后完全生效）"


def mark_remove(adb: Adb, name: str, root: Root | None = None) -> tuple[bool, str]:
    """标准做法是放 remove 标记，重启由管理器真正删除。"""
    _check_name(name)
    root = root or Root(adb)
    root.ensure()
    res = root.run(f"touch {shlex.quote(MODULES_DIR + '/' + name + '/remove')}", timeout=20)
    if not res.ok:
        return False, "标记卸载失败：" + (res.err or res.out).strip()[:200]
    return True, f"已标记卸载 {name}，重启后生效"


def install(adb: Adb, zip_path: str, root: Root | None = None, status: RootStatus | None = None) -> tuple[bool, str]:
    from pathlib import Path

    src = Path(zip_path)
    try:
        exists = src.is_file()
    except OSError:
        exists = False
    if not exists:
        raise ModuleError(f"模块包不存在：{src}")
    if src.suffix.lower() != ".zip":
        raise ModuleError("模块必须是 .zip 包")
    root = root or Root(adb)
    st = status or root.refresh()
    st.require()
    mgr = manager(adb, root, st)
    if not mgr.can_install:
        raise ModuleError(
            f"{mgr.name} 不支持命令行安装模块",
            hint="改用管理器 App 手动安装，或确认 magisk / ksud 在 PATH 中",
        )

    remote = f"/data/local/tmp/iris-{int(time.time())}-{src.name}"
    push = adb.push(str(src), remote, timeout=600)
    if not push.ok:
        raise ModuleError("推送模块失败", hint=(push.err or push.out).strip()[:300])

    cmd = INSTALL_CMDS[mgr.name].format(zip=shlex.quote(remote))
    try:
        res = root.run(cmd, timeout=600)
    finally:
        root.run(f"rm -f {shlex.quote(remote)}", timeout=30)
    text = (res.out + "\n" + res.err).strip()
    ok = res.ok and "fail" not in text.lower() and "error" not in text.lower()
    if ok:
        return True, f"已安装到 {mgr.name}，重启后生效"
    return False, text[-500:] or "安装失败"


def logs(adb: Adb, root: Root | None = None, status: RootStatus | None = None, lines: int = 200) -> str:
    root = root or Root(adb)
    st = status or root.refresh()
    st.require()
    mgr = manager(adb, root, st)
    lines = max(20, min(int(lines), 1000))
    if mgr.name == "KernelSU":
        cmd = "ls -t /data/adb/ksu/logs/ 2>/dev/null | head -n 1"
        res = root.run(cmd, timeout=20)
        newest = res.out.strip().splitlines()[0] if res.ok and res.out.strip() else ""
        if newest:
            res = root.run(f"tail -n {lines} {shlex.quote('/data/adb/ksu/logs/' + newest)}", timeout=30)
            return res.out.strip()
    if mgr.name == "APatch":
        res = root.run(f"tail -n {lines} /data/adb/ap/logs/* 2>/dev/null", timeout=30)
        return res.out.strip()
    res = root.run(f"tail -n {lines} /cache/magisk.log 2>/dev/null", timeout=30)
    return res.out.strip() or "没有读到日志（文件不存在，或管理器不是 Magisk）"


def _check_name(name: str) -> None:
    if not name or "/" in name or name in (".", "..") or "\\" in name:
        raise ModuleError(f"非法模块名：{name!r}")
