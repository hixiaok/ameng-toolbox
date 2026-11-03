"""应用管理与 shell（免 root）。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..adb import Adb
from ..errors import IrisError

_PKG_LINE = re.compile(r"^package:(.+)$")


@dataclass
class AppInfo:
    package: str
    apk_path: str = ""

    def to_dict(self) -> dict:
        return {"package": self.package, "apk_path": self.apk_path}


def list_packages(adb: Adb, *, third_party_only: bool = True) -> list[str]:
    args = ["pm", "list", "packages"]
    if third_party_only:
        args.append("-3")
    res = adb.shell(*args)
    if not res.ok:
        raise IrisError("读取应用列表失败", hint=(res.err or res.out).strip()[:200])
    out = []
    for line in res.stdout_lines:
        m = _PKG_LINE.match(line.strip())
        if m:
            out.append(m.group(1).strip())
    return sorted(out)


def apk_path(adb: Adb, package: str) -> str:
    res = adb.shell("pm", "path", package)
    for line in res.stdout_lines:
        if line.startswith("package:"):
            return line.split(":", 1)[1].strip()
    return ""


def install(adb: Adb, apk: str, *, reinstall: bool = True) -> tuple[bool, str]:
    adb.require_device()
    args = ["install", "-r"] if reinstall else ["install"]
    res = adb.run(*args, apk, timeout=300)
    ok = res.ok and "Success" in (res.out + res.err)
    msg = "安装成功" if ok else "安装失败"
    return ok, msg + ("：" + (res.err or res.out).strip()[:300] if not ok else "")


def uninstall(adb: Adb, package: str) -> tuple[bool, str]:
    adb.require_device()
    res = adb.shell("pm", "uninstall", package)
    ok = res.ok and "Success" in (res.out + res.err)
    return ok, ("已卸载 " + package) if ok else ("卸载失败：" + (res.err or res.out).strip()[:300])


def shell(adb: Adb, command: str, *, timeout: float = 30.0) -> tuple[bool, str]:
    adb.require_device()
    res = adb.shell(command, timeout=timeout)
    text = (res.out or "") + (("\n" + res.err) if res.err else "")
    return res.ok, text.strip()
