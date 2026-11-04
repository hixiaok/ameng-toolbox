"""回放式假设备：给 root / 分区 / 模块测试用。

不是通用 adb 模拟器，只实现被测代码实际发出的那几条命令。要加新命令时，
在 `shell()` 里补一个分支，并在测试里断言 `calls` 记录了它。
"""

from __future__ import annotations

import hashlib
import shlex
from pathlib import Path

from iris.core.adb import Device
from iris.core.proc import ProcResult


def res(code=0, out="", err="", timed_out=False):
    return ProcResult(argv=("fake",), code=code, out=out, err=err, duration=0.01, timed_out=timed_out)


def unquote(token: str) -> str:
    """还原 `shlex.quote()` 产出的单参数。"""
    try:
        parts = shlex.split(token)
    except ValueError:
        return token
    return parts[0] if len(parts) == 1 else token


class FakeAndroid:
    def __init__(
        self,
        *,
        root: bool = True,
        su_present: bool = True,
        granted: bool = True,
        manager: str = "Magisk",
        partitions: dict[str, int] | None = None,
        modules: dict[str, str] | None = None,
        files: dict[str, bytes] | None = None,
        serial: str = "FAKE123",
    ):
        self.has_root = root
        self.su_present = su_present
        self.granted = granted
        self.manager = manager
        self.partitions = partitions or {"boot_a": 64 * 1024 * 1024, "super": 8 * 1024 * 1024 * 1024}
        self.modules = modules or {}
        self.files = files or {}
        self.serial = serial
        self.calls: list[tuple[str, ...]] = []
        self.tmp: dict[str, bytes] = {}

    # ---- adb 接口 -------------------------------------------------
    def require_device(self):
        return Device(serial=self.serial, state="device")

    def shell(self, *args, timeout=None):
        self.calls.append(tuple(args))
        if len(args) >= 2 and args[0] == "su" and args[1] == "-c":
            return self._as_root(unquote(args[2]))
        return self._exec(" ".join(str(a) for a in args))

    def shell_su(self, *args, timeout=None):
        return self.shell("su", "-c", " ".join(str(a) for a in args))

    def pull(self, remote, local, timeout=None):
        self.calls.append(("pull", remote, local))
        data = self.tmp.get(remote) or self.files.get(remote)
        if data is None:
            return res(1, "", f"remote object '{remote}' does not exist")
        Path(local).write_bytes(data)
        return res(0, f"1 file pulled")

    def push(self, local, remote, timeout=None):
        self.calls.append(("push", local, remote))
        data = Path(local).read_bytes()
        self.tmp[remote] = data
        return res(0, f"1 file pushed")

    # ---- 回放 -----------------------------------------------------
    def _as_root(self, cmd: str):
        if not self.granted:
            return res(1, "", "su: permission denied")
        if cmd == "id":
            return res(0, "uid=0(root) gid=0(root)\n")
        return self._exec(cmd)

    def _exec(self, cmd: str):
        cmd = cmd.strip()

        if cmd == "id":
            return res(0, "uid=0(root) gid=0(root)\n" if self.has_root else "uid=2000(shell) gid=2000(shell)\n")
        if cmd == "which su":
            return res(0 if self.su_present else 1, "/system/bin/su\n" if self.su_present else "")
        if cmd.startswith("ls -d "):
            return res(0, cmd.split()[-1] + "\n")
        if cmd in ("magisk -v", "ksud -V", "apd -V"):
            name = {"magisk -v": "Magisk", "ksud -V": "KernelSU", "apd -V": "APatch"}[cmd]
            if name == self.manager:
                return res(0, {"Magisk": "27.0:MAGISK\n", "KernelSU": "1.0.3\n", "APatch": "0.10\n"}[name])
            return res(1, "", "not found")
        if "blockdev --getsize64" in cmd:
            lines = [f"{n} /dev/block/by-name/{n} {s}" for n, s in self.partitions.items()]
            return res(0, "\n".join(lines) + "\n")
        if cmd.startswith("df -B1"):
            return res(0, "Filesystem 1B-blocks Used Available Use% Mounted on\n/dev/block/dm-4 107374182400 1 96636764160 1% /data\n")
        if "module.prop" in cmd:
            return res(0, self._module_dump())
        if "head -c" in cmd and "sha256sum" in cmd:
            # 还原后校验：先用同一条命令里的 dd 填充临时文件，再截断算哈希
            import re

            dd = re.search(r"dd if='?([^'\s]+)'? of='?([^'\s;]+)'?", cmd)
            if dd:
                self.tmp[dd.group(2)] = self.files.get(dd.group(1), self.tmp.get(dd.group(1), b""))
            m = re.search(r"head -c (\d+) '?([^'\s|]+)'?", cmd)
            if not m:
                return res(1, "", "fake: cannot parse verify command")
            limit, path = int(m.group(1)), m.group(2)
            data = self.tmp.get(path, b"")[:limit]
            return res(0, hashlib.sha256(data).hexdigest() + "\n")
        if cmd.startswith("dd if="):
            import re

            m = re.match(r"dd if='?([^'\s]+)'? of='?([^'\s;]+)'?", cmd)
            if m and m.group(2):
                src = self.files.get(m.group(1))
                if src is None:
                    src = self.tmp.get(m.group(1), b"FAKE-DISK-IMAGE")
                self.tmp[m.group(2)] = src
            return res(0, "")
        if cmd.startswith("sha256sum "):
            path = cmd.split(maxsplit=1)[1].strip().strip("'")
            data = self.tmp.get(path)
            if data is None:
                data = self.files.get(path)
            if data is None:
                return res(1, "", "No such file or directory")
            return res(0, hashlib.sha256(data).hexdigest() + "  " + path + "\n")
        if cmd.startswith("head -c "):
            parts = cmd.split()
            limit = int(parts[2])
            path = parts[3].strip("'")
            data = self.files.get(path, b"")
            return res(0, data[:limit].decode("utf-8", "replace"))
        if cmd.startswith("stat -c"):
            path = cmd.split()[-1]
            data = self.files.get(path, b"")
            return res(0, f"{len(data)}\n")
        if cmd.startswith(("mkdir", "rm ", "touch ", "cp ")):
            return res(0, "")
        if cmd == "sync":
            return res(0, "")
        if cmd.startswith("tail "):
            return res(0, "magisk log line\n")
        if "install-module" in cmd or "module install" in cmd:
            self.installed = cmd
            return res(0, "- Installing module\n- Done\n")
        return res(1, "", f"fake: unsupported command: {cmd[:80]}")

    def _module_dump(self) -> str:
        chunks = []
        for name, prop in self.modules.items():
            chunks.append(f"=== {name}\n{prop}\n")
        return "".join(chunks)
