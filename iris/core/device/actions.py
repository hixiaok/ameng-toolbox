"""设备侧只读操作与快捷指令（不需要 root）。

全部走 adb，返回结构化结果；失败带明确原因，不靠字符串猜。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ..adb import Adb
from ..errors import IrisError, NoDevice


def stats(adb: Adb) -> dict:
    """电池 + 存储，用于仪表盘环形图。"""
    adb.require_device()
    out: dict = {}

    bat = adb.shell("dumpsys", "battery")
    if bat.ok:
        for line in bat.stdout_lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip()
            if key == "level" and value.isdigit():
                out["battery_level"] = int(value)
            elif key == "voltage" and value.isdigit():
                out["battery_mv"] = int(value)
            elif key == "temperature" and value.isdigit():
                out["battery_temp"] = int(value) / 10

    df = adb.shell("df", "-k", "/data")
    if df.ok:
        for line in reversed(df.stdout_lines):
            parts = line.split()
            if len(parts) >= 4 and parts[1].isdigit() and parts[2].isdigit():
                total = int(parts[1]) * 1024
                used = int(parts[2]) * 1024
                out["disk_total"] = total
                out["disk_used"] = used
                break

    return out


@dataclass
class ActionResult:
    ok: bool
    message: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "detail": self.detail}


REBOOT_TARGETS = {
    "reboot_system": ("系统", ()),
    "reboot_recovery": ("Recovery", ("recovery",)),
    "reboot_bootloader": ("Bootloader", ("bootloader",)),
    "reboot_fastbootd": ("Fastbootd", ("fastboot",)),
}


def action(name: str, adb: Adb, *, workdir: Path) -> ActionResult:
    """执行一个快捷指令。未知指令明确报错，不静默。"""
    adb.require_device()

    if name in REBOOT_TARGETS:
        label, target = REBOOT_TARGETS[name]
        res = adb.shell("reboot", *target) if target else adb.shell("reboot")
        if res.ok:
            return ActionResult(True, f"已请求重启到 {label}")
        return ActionResult(False, f"重启到 {label} 失败", res.err or res.out)

    if name == "shutdown":
        res = adb.shell("reboot", "-p")
        return ActionResult(res.ok, "已请求关机" if res.ok else "关机失败", res.err or res.out)

    if name == "screenshot":
        workdir.mkdir(parents=True, exist_ok=True)
        remote = "/sdcard/iris-shot.png"
        cap = adb.shell("screencap", "-p", remote)
        if not cap.ok:
            return ActionResult(False, "截图失败", cap.err or cap.out)
        local = workdir / f"shot-{time.strftime('%Y%m%d-%H%M%S')}.png"
        pull = adb.pull(remote, str(local))
        adb.shell("rm", "-f", remote)
        if not pull.ok:
            return ActionResult(False, "拉取截图失败", pull.err or pull.out)
        return ActionResult(True, f"已保存截图：{local.name}", str(local))

    if name == "logcat":
        res = adb.shell("logcat", "-d", "-t", "200")
        if not res.ok:
            return ActionResult(False, "抓取日志失败", res.err or res.out)
        return ActionResult(True, f"日志 {len(res.stdout_lines)} 行", res.out[-20000:])

    raise IrisError(f"未知操作：{name}", hint="可选：reboot_system / reboot_recovery / "
                                        "reboot_bootloader / reboot_fastbootd / shutdown / "
                                        "screenshot / logcat")
