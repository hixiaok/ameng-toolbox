"""root 执行层：探测 su，并把命令安全地送进设备 shell。

上游（VioletToolBox）的 root 操作大多长这样：

    ExecuteShellCommand($"su -c \"{command}\"");

看起来没问题，实际有三层引号：Windows `cmd` 解析一遍、adb 拼接一遍、设备
`sh` 再解析一遍。命令里只要带空格、单引号或重定向，就会出现"本地没报错、
设备上只执行了第一个单词"的静默失败。

这里的约定：

* 命令整体只经过**设备 sh 的一层**引号：`shlex.quote()` 之后作为 `su -c`
  的单个参数传给 adb，`adb shell` 会把 argv 用空格拼给设备 sh，而设备 sh
  解析单引号后正好还原成一条完整命令。
* 探测和执分离：`detect()` 只读、可缓存；`run()` 才真正执行，失败抛
  `PermissionDenied` 或返回 `ProcResult` 由调用方判断。
* 不在本地拼 `cmd /c`，也不经过 PowerShell。
"""

from __future__ import annotations

import shlex
import time
from dataclasses import asdict, dataclass

from .. import proc
from ..adb import Adb
from ..errors import PermissionDenied

# 已知 su 落点（Magisk / KernelSU / APatch / 老式 SuperSU）
SU_PATHS = (
    "/system/bin/su",
    "/system/xbin/su",
    "/sbin/su",
    "/su/bin/su",
    "/debug_ramdisk/su",
    "/data/adb/ksu/bin/su",
    "/data/adb/ap/bin/su",
)

# 管理器识别：命令 -> 版本行；目录探测作为兜底
MANAGER_COMMANDS = (
    ("Magisk", ("magisk", "-v")),
    ("KernelSU", ("ksud", "-V")),
    ("APatch", ("apd", "-V")),
)

MODULE_DIRS = {
    "Magisk": "/data/adb/modules",
    "KernelSU": "/data/adb/modules",
    "APatch": "/data/adb/modules",
    "未识别": "/data/adb/modules",
}


@dataclass
class RootStatus:
    """一次 root 探测的结果，保留证据便于排查。"""

    available: bool = False
    uid: str = ""
    su_path: str = ""
    manager: str = "未识别"
    version: str = ""
    method: str = ""          # adb root / su / 无
    reason: str = ""
    checked_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def require(self) -> "RootStatus":
        if not self.available:
            raise PermissionDenied(
                "当前设备没有可用的 root",
                hint=self.reason or "在手机的管理器里给本工具授权，或确认设备已 root",
            )
        return self


def _id_is_root(adb: Adb, *, su: bool) -> proc.ProcResult:
    if su:
        return adb.shell("su", "-c", "id", timeout=15)
    return adb.shell("id", timeout=8)


def _find_su(adb: Adb) -> str:
    res = adb.shell("which", "su", timeout=8)
    if res.ok and res.out.strip():
        return res.first_line().strip()
    for path in SU_PATHS:
        check = adb.shell("ls", path, timeout=8)
        if check.ok and "No such file" not in check.out and path in check.out:
            return path
    return ""


def _parse_version(text: str) -> str:
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    return line[:80]


def _detect_manager(adb: Adb) -> tuple[str, str]:
    """返回 (管理器, 版本)。识别不出来就返回 ("未识别", "")。"""
    for name, cmd in MANAGER_COMMANDS:
        res = adb.shell("su", "-c", shlex.quote(" ".join(cmd)), timeout=10)
        if res.ok and res.out.strip():
            return name, _parse_version(res.out)
    # 命令不在 PATH 时，用目录兜底
    for name, path in (("Magisk", "/data/adb/magisk"), ("KernelSU", "/data/adb/ksu"), ("APatch", "/data/adb/ap")):
        res = adb.shell("su", "-c", f"ls -d {path}", timeout=10)
        if res.ok and path in res.out:
            return name, ""
    return "未识别", ""


def detect(adb: Adb) -> RootStatus:
    """探测 root。只读，不会改动设备。"""
    status = RootStatus(checked_at=time.time())
    adb.require_device()

    # 1) 已经是 root shell（adb root / userdebug）
    me = _id_is_root(adb, su=False)
    if me.ok and "uid=0" in me.out:
        status.available = True
        status.uid = "0"
        status.method = "adb root"
        status.reason = "adb shell 本身即 root"
        manager, version = _detect_manager(adb)
        status.manager, status.version = manager, version
        return status

    # 2) 找 su
    status.su_path = _find_su(adb)
    if not status.su_path:
        status.reason = "设备上没有 su：未 root，或 root 方案没有暴露 su"
        return status

    # 3) 试授权。Magisk 首次会弹窗，用户没点就会卡住，所以给短超时。
    probe = _id_is_root(adb, su=True)
    if probe.timed_out:
        status.reason = "su 超时：手机上可能弹出了授权框，没有点允许"
        return status
    if probe.ok and "uid=0" in probe.out:
        status.available = True
        status.uid = "0"
        status.method = "su"
        status.reason = f"su -> {status.su_path}"
        manager, version = _detect_manager(adb)
        status.manager, status.version = manager, version
        return status

    detail = (probe.err or probe.out).strip().splitlines()
    status.reason = "su 存在但未授权：" + (detail[-1][:160] if detail else "权限被拒绝")
    return status


class Root:
    """绑定到一台设备的 root 句柄；探测结果缓存，执行前按需刷新。"""

    def __init__(self, adb: Adb, *, status: RootStatus | None = None):
        self.adb = adb
        self.status = status

    def refresh(self) -> RootStatus:
        self.status = detect(self.adb)
        return self.status

    def ensure(self) -> RootStatus:
        if self.status is None:
            self.refresh()
        assert self.status is not None
        return self.status.require()

    def run(self, command: str, *, timeout: float = 60.0) -> proc.ProcResult:
        """以 root 执行一条完整命令（可以带管道、重定向、`&&`）。

        命令作为单个参数交给 su，引号只过设备 sh 这一层。
        """
        status = self.ensure()
        if status.method == "adb root":
            return self.adb.shell(command, timeout=timeout)
        return self.adb.shell("su", "-c", shlex.quote(command), timeout=timeout)

    def test(self, command: str, *, timeout: float = 20.0) -> bool:
        try:
            return self.run(command, timeout=timeout).ok
        except PermissionDenied:
            return False


def require_root(adb: Adb) -> Root:
    """探测并确认 root，失败时抛 PermissionDenied（带可读原因）。"""
    root = Root(adb)
    root.ensure()
    return root
