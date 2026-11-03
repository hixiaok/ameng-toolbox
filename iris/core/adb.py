"""ADB 封装：只负责"把命令跑对、把结果结构化"，不做业务判断。

与上游的差别：设备侧命令一律以参数列表透传（`adb shell dd if=... of=...`），
不拼 `su -c "..."` 这种三层引号字符串——那玩意儿在 Windows 上换行符和引号
处理几乎是必炸的。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import proc
from .errors import NoDevice, ToolMissing


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    product: str = ""
    model: str = ""
    device: str = ""
    transport_id: str = ""

    @property
    def usable(self) -> bool:
        return self.state == "device"


def candidates(exe: str | None = None) -> list[str]:
    """按优先级给出候选 adb 路径。

    除了 PATH 和 IRIS_ADB，还会往上层目录找 `platform-tools/adb.exe`——
    大多数人就是把 platform-tools 解压在项目旁边的。
    """
    out: list[str] = []
    if exe:
        out.append(exe)
    env = os.environ.get("IRIS_ADB")
    if env:
        out.append(env)
    found = proc.which("adb")
    if found:
        out.append(found)

    roots = list(Path(__file__).resolve().parents) + [Path.cwd()]
    for base in roots:
        for rel in ("platform-tools/adb.exe", "platform-tools/adb", "adb.exe", "adb"):
            out.append(str(base / rel))
    return out


def find_adb(exe: str | None = None) -> str | None:
    """返回第一个真实存在的 adb 路径；都没有则 None。"""
    for cand in candidates(exe):
        if cand == "adb" or Path(cand).is_file():
            return cand
    return None


class Adb:
    def __init__(self, exe: str | None = None, serial: str | None = None, timeout: float = 30.0):
        self.exe = find_adb(exe) or "adb"
        self.serial = serial
        self.timeout = timeout

    # ---- 基础设施 -------------------------------------------------
    def _argv(self, *args: str) -> list[str]:
        argv = [self.exe]
        if self.serial:
            argv += ["-s", self.serial]
        argv += list(args)
        return argv

    def _run(self, *args: str, timeout: float | None = None) -> proc.ProcResult:
        res = proc.run(self._argv(*args), timeout=timeout or self.timeout)
        if res.code == proc.EXIT_NOT_FOUND:
            raise ToolMissing(
                f"未找到 adb（尝试过：{self.exe}）",
                hint="安装 Android Platform Tools，或设置环境变量 IRIS_ADB 指向 adb.exe",
            )
        return res

    # ---- 设备 -----------------------------------------------------
    def version(self) -> proc.ProcResult:
        return self._run("version")

    def devices(self) -> list[Device]:
        res = self._run("devices", "-l")
        if not res.ok:
            return []
        out: list[Device] = []
        for line in res.stdout_lines[1:]:  # 跳过 "List of devices attached"
            parts = line.split()
            if len(parts) < 2:
                continue
            fields = {}
            for token in parts[2:]:
                if ":" in token:
                    k, v = token.split(":", 1)
                    fields[k] = v
            out.append(
                Device(
                    serial=parts[0],
                    state=parts[1],
                    product=fields.get("product", ""),
                    model=fields.get("model", ""),
                    device=fields.get("device", ""),
                    transport_id=fields.get("transport_id", ""),
                )
            )
        return out

    def require_device(self) -> Device:
        """取当前设备：指定的 serial 优先，否则要求恰好一台在线。"""
        devs = self.devices()
        if self.serial:
            for d in devs:
                if d.serial == self.serial:
                    if not d.usable:
                        raise NoDevice(
                            f"设备 {d.serial} 状态为 {d.state}",
                            hint="unauthorized 请在手机上确认 RSA 授权；offline 尝试重新插拔",
                        )
                    return d
            raise NoDevice(f"找不到设备 {self.serial}", hint="执行 `iris device list` 查看在线设备")

        usable = [d for d in devs if d.usable]
        if not usable:
            raise NoDevice(
                "没有处于 device 状态的设备",
                hint="检查 USB 调试是否开启；`iris doctor` 可看完整环境",
            )
        if len(usable) > 1:
            names = ", ".join(d.serial for d in usable)
            raise NoDevice(f"检测到多台设备（{names}）", hint="用 --serial 指定其中一台")
        self.serial = usable[0].serial
        return usable[0]

    # ---- 执行 -----------------------------------------------------
    def run(self, *args: str, timeout: float | None = None) -> proc.ProcResult:
        """通用透传（不经过 shell），用于 adb install / push 这类子命令。"""
        return self._run(*args, timeout=timeout)

    def shell(self, *args: str, timeout: float | None = None) -> proc.ProcResult:
        """在设备上执行命令。参数列表透传，不经过本地 shell。"""
        return self._run("shell", *args, timeout=timeout)

    def shell_su(self, *args: str, timeout: float | None = None) -> proc.ProcResult:
        """以 root 执行。需要设备已 root，否则 su 自身会报错。"""
        return self.shell("su", "-c", " ".join(args), timeout=timeout)

    def getprop(self, name: str) -> str:
        res = self.shell("getprop", name)
        return res.out.strip() if res.ok else ""

    def props(self) -> dict[str, str]:
        """一次性拉全部属性，比逐个 getprop 快一个数量级。"""
        res = self.shell("getprop")
        out: dict[str, str] = {}
        if not res.ok:
            return out
        for line in res.stdout_lines:
            # 形如 [ro.product.model]: [Pixel 8]
            if not line.startswith("["):
                continue
            try:
                key, rest = line[1:].split("]: [", 1)
                val = rest[:-1] if rest.endswith("]") else rest
            except ValueError:
                continue
            out[key] = val
        return out

    def pull(self, remote: str, local: str, timeout: float | None = None) -> proc.ProcResult:
        return self._run("pull", remote, local, timeout=timeout)

    def push(self, local: str, remote: str, timeout: float | None = None) -> proc.ProcResult:
        return self._run("push", local, remote, timeout=timeout)
