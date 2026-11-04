"""环境自检。

上游用户最常见的求助是"设备连不上"，而工具本身不告诉你问题出在哪一层。
这里把依赖、驱动、授权、端口逐项检查，每项给出可执行的处理建议。
"""

from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass, field

from . import proc

OK = "ok"
WARN = "warn"
FAIL = "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    hint: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail, "hint": self.hint}


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, *args, **kwargs) -> None:
        self.checks.append(Check(*args, **kwargs))

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.status == WARN]

    def to_dict(self) -> dict:
        return {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "checks": [c.to_dict() for c in self.checks],
        }


def _find_fastboot(adb_path: str | None) -> str | None:
    """adb 同目录优先（便携版就是这样），再退 PATH。"""
    from pathlib import Path

    if adb_path:
        exe = Path(adb_path)
        sibling = exe.with_name("fastboot.exe" if exe.suffix.lower() == ".exe" else "fastboot")
        if sibling.is_file():
            return str(sibling)
    found = shutil.which("fastboot")
    if found:
        return found
    for rel in ("platform-tools/fastboot.exe", "platform-tools/fastboot"):
        for base in (Path.cwd(), *Path(__file__).resolve().parents):
            cand = base / rel
            if cand.is_file():
                return str(cand)
    return None


def run_check(*, adb_exe: str | None = None) -> Report:
    from .adb import Adb, find_adb
    from .errors import ToolMissing

    r = Report()
    r.add("python", OK if sys.version_info >= (3, 10) else WARN, sys.version.split()[0])
    r.add("os", OK, f"{platform.system()} {platform.release()}")

    adb_path = find_adb(adb_exe)
    if adb_path:
        res = proc.run([adb_path, "version"], timeout=10)
        if res.ok:
            r.add("adb", OK, f"{adb_path} | {res.first_line()}")
        else:
            r.add("adb", WARN, f"{adb_path} 存在但调用失败：{res.describe()}", "确认 adb 未被安全软件拦截")
    else:
        r.add("adb", FAIL, "未找到 adb", "安装 Android Platform Tools，放到 platform-tools/ 或设置 IRIS_ADB")

    fastboot = _find_fastboot(adb_path)
    if fastboot:
        res = proc.run([fastboot, "--version"], timeout=10)
        r.add("fastboot", OK if res.ok else WARN, f"{fastboot} | {res.first_line() or res.describe()}")
    else:
        r.add("fastboot", WARN, "未找到 fastboot", "把 platform-tools 解压到项目旁边，或加入 PATH")

    if adb_path:
        try:
            adb = Adb(exe=adb_exe)
            devs = adb.devices()
        except ToolMissing as exc:
            r.add("adb server", FAIL, str(exc), "确认 adb 可执行文件路径正确")
        else:
            if not devs:
                r.add(
                    "devices",
                    WARN,
                    "没有检测到设备",
                    "检查 USB 调试、数据线、驱动；Fastboot 模式请用 `iris fastboot` 相关命令",
                )
            else:
                for d in devs:
                    status = OK if d.usable else WARN
                    hint = ""
                    if d.state == "unauthorized":
                        hint = "在手机屏幕上点「允许 USB 调试」"
                    elif d.state == "offline":
                        hint = "重新插拔，或 adb kill-server 后重试"
                    r.add(
                        f"device {d.serial}",
                        status,
                        f"state={d.state} model={d.model or '?'} product={d.product or '?'}",
                        hint,
                    )

    if platform.system() == "Windows":
        r.add(
            "windows driver",
            WARN,
            "驱动问题无法自动检测",
            "设备管理器里出现黄色感叹号时装 Google USB Driver 或厂商驱动",
        )
    return r
