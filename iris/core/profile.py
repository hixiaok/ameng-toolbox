"""设备画像（device profile）。

上游最典型的一类 bug：每个功能各自硬编码分区路径。玄戒 SoC 上没有
`/dev/block/bootdevice/by-name`，"备份字库"整片失败，而同工具里的"回读分区"
用的是自动探测路径，所以正常工作（上游 issue #4）。

这里的做法：开机状态下探测一次，把所有"因设备而异"的事实固化成 profile，
功能模块只读 profile，不再各自猜路径。

探测全部走只读命令，未 root、未解锁 BL 也能拿到大半信息。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# 常见 by-name 目录，按命中概率排序
BY_NAME_CANDIDATES = (
    "/dev/block/by-name",
    "/dev/block/bootdevice/by-name",
    "/dev/block/platform/soc/1d84000.ufshc/by-name",
    "/dev/block/platform/soc/1d84000.ufs/by-name",
    "/dev/block/platform/13500000.ufs/by-name",
)

_PART_LINE = re.compile(r"^\s*\d+\s+\d+\s+(\d+)\s+(\S+)$")


@dataclass
class Probe:
    """一次探测的记录，保留证据便于事后排查。"""

    name: str
    ok: bool
    value: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeviceProfile:
    serial: str = ""
    model: str = ""
    brand: str = ""
    codename: str = ""
    soc_model: str = ""
    soc_manufacturer: str = ""
    android_release: str = ""
    sdk: str = ""
    abi: str = ""
    build_fingerprint: str = ""
    build_display: str = ""
    security_patch: str = ""
    slot_suffix: str = ""
    ab_update: bool = False

    root: bool = False
    root_evidence: str = ""

    by_name_root: str | None = None
    block_device: str | None = None
    partitions: dict[str, int] = field(default_factory=dict)

    probed_at: float = 0.0
    probes: list[Probe] = field(default_factory=list)

    # ---- 便捷判定 -------------------------------------------------
    @property
    def can_read_partitions(self) -> bool:
        return self.by_name_root is not None or bool(self.partitions)

    @property
    def can_write(self) -> bool:
        """是否能对分区做写操作：需要 root + 已知 by-name 根。"""
        return self.root and self.by_name_root is not None

    def partition_path(self, name: str) -> str | None:
        """给出某个分区在设备上的绝对路径，未探测到则返回 None。"""
        if not self.by_name_root:
            return None
        return f"{self.by_name_root}/{name}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["probes"] = [p.to_dict() for p in self.probes]
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> "DeviceProfile":
        probes = [Probe(**p) for p in raw.pop("probes", [])]
        obj = cls(**raw)
        obj.probes = probes
        return obj


# ---- 缓存 ---------------------------------------------------------
def cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    d = root / "iris" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(serial: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", serial) or "unknown"
    return cache_dir() / f"{safe}.json"


def load_cached(serial: str) -> DeviceProfile | None:
    p = cache_path(serial)
    if not p.is_file():
        return None
    try:
        return DeviceProfile.from_dict(json.loads(p.read_text("utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def save(profile: DeviceProfile) -> Path:
    p = cache_path(profile.serial)
    p.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), "utf-8")
    return p


# ---- 探测 ---------------------------------------------------------
def _truthy_prop(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes")


def _read_proc_partitions(adb) -> tuple[dict[str, int], str]:
    res = adb.shell("cat", "/proc/partitions")
    parts: dict[str, int] = {}
    if not res.ok:
        return parts, res.describe()
    for line in res.out.splitlines():
        m = _PART_LINE.match(line)
        if m:
            parts[m.group(2)] = int(m.group(1)) * 1024
    return parts, f"/proc/partitions -> {len(parts)} 项"


def _probe_by_name(adb, use_su: bool) -> tuple[str | None, list[Probe]]:
    """依次试候选目录，返回第一个可列出的 by-name 根。"""
    probes: list[Probe] = []
    for path in BY_NAME_CANDIDATES:
        if use_su:
            res = adb.shell_su("ls", path)
        else:
            res = adb.shell("ls", path)
        ok = res.ok and "No such file" not in res.out and "Permission denied" not in res.out
        probes.append(Probe(f"by_name{':su' if use_su else ''}", ok, path, res.describe()))
        if ok:
            return path, probes
    return None, probes


def probe(adb, *, serial: str | None = None, allow_su: bool = True) -> DeviceProfile:
    """探测当前设备。`adb` 只要有 `.props()` / `.shell()` / `.shell_su()` 即可。

    这层抽象同时也是 mock 后端的接入点：传入一个回放脚本的假 adb 就能离线跑。
    """
    dev = adb.require_device()
    prof = DeviceProfile(serial=serial or dev.serial, probed_at=time.time())

    props = adb.props()
    prof.probes.append(Probe("getprop", bool(props), f"{len(props)} 条属性"))

    def gp(*names: str) -> str:
        for n in names:
            if props.get(n):
                return props[n]
        return ""

    prof.model = gp("ro.product.model", "ro.product.vendor.model")
    prof.brand = gp("ro.product.brand", "ro.product.vendor.brand")
    prof.codename = gp("ro.product.device", "ro.product.vendor.device")
    prof.soc_model = gp("ro.soc.model", "ro.board.platform", "ro.hardware")
    prof.soc_manufacturer = gp("ro.soc.manufacturer", "ro.board.vendor")
    prof.android_release = gp("ro.build.version.release")
    prof.sdk = gp("ro.build.version.sdk")
    prof.abi = gp("ro.product.cpu.abi")
    prof.build_fingerprint = gp("ro.build.fingerprint", "ro.system.build.fingerprint")
    prof.build_display = gp("ro.build.display.id", "ro.system.build.id")
    prof.security_patch = gp("ro.build.version.security_patch")
    prof.slot_suffix = gp("ro.boot.slot_suffix", "ro.boot.slot")
    prof.ab_update = _truthy_prop(gp("ro.build.ab_update")) or bool(prof.slot_suffix)

    # root：先看 id，再看 su 是否存在
    ident = adb.shell("id")
    if ident.ok and "uid=0" in ident.out:
        prof.root, prof.root_evidence = True, "id -> uid=0"
    else:
        su = adb.shell("which", "su")
        prof.root = su.ok and bool(su.out.strip())
        prof.root_evidence = f"which su -> {su.out.strip() or '不存在'}"
    prof.probes.append(Probe("root", prof.root, prof.root_evidence))

    # by-name：先用非 root 探；不行且允许时用 su 再探
    root_path, probes = _probe_by_name(adb, use_su=False)
    prof.probes.extend(probes)
    if root_path is None and allow_su:
        root_path, probes = _probe_by_name(adb, use_su=True)
        prof.probes.extend(probes)
    prof.by_name_root = root_path

    # 块设备与分区大小：/proc/partitions 无需 root
    parts, evidence = _read_proc_partitions(adb)
    prof.probes.append(Probe("proc_partitions", bool(parts), evidence))
    if parts:
        prof.partitions = parts
        prof.block_device = _guess_block_device(parts)

    return prof


def _guess_block_device(parts: dict[str, int]) -> str | None:
    """从 /proc/partitions 里猜整盘设备名（mmcblk0 / sda / sdd ...）。"""
    disks = [n for n in parts if not n[-1].isdigit()]
    if not disks:
        return None
    disks.sort(key=lambda n: parts[n], reverse=True)
    return f"/dev/block/{disks[0]}"
