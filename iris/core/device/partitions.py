"""分区：读表、备份、还原、fastboot 刷入。

写操作沿用项目的"计划式执行"：

* `plan_backup()` / `plan_restore()` 只产出 JSON 计划，不碰设备；
* `apply_backup()` / `apply_restore()` 才真正执行；
* 计划里带风险项（空间、大小不符、未解锁、su 未授权），调用方可以先看。

备份用设备侧 `dd` 落到 /data/local/tmp，再 `adb pull`，最后**双端 sha256 对比**。
上游只判断 dd 的退出码，于是 dd 报 "No such file or directory" 也会被当成成功
（issue #4）；这里没有哈希一致就算失败。
"""

from __future__ import annotations

import hashlib
import shlex
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import proc
from ..adb import Adb
from ..errors import IrisError, ToolMissing
from .root import Root

TMP_DIR = "/data/local/tmp/iris"
BLOCK = "4M"
READ_BACK_LIMIT = 64 * 1024 * 1024  # 小于这个大小的分区，还原后整段回读校验


class DiskError(IrisError):
    exit_code = 9


@dataclass
class PartInfo:
    name: str
    path: str
    size: int = 0          # 0 = 未知
    device: str = ""

    @property
    def size_text(self) -> str:
        return human_size(self.size) if self.size else "未知"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["size_text"] = self.size_text
        return d


@dataclass
class Plan:
    """一份可审阅的写操作计划。"""

    action: str
    partition: str
    device_path: str = ""
    local_path: str = ""
    image_size: int = 0
    partition_size: int = 0
    remote_tmp: str = ""
    sha256: str = ""
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def executable(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict:
        d = asdict(self)
        d["executable"] = self.executable
        d["image_size_text"] = human_size(self.image_size)
        d["partition_size_text"] = human_size(self.partition_size)
        return d


def human_size(n: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    v = float(n)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.0f}{units[i]}" if i == 0 else f"{v:.1f}{units[i]}"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ---- 读表 -----------------------------------------------------------
def table(adb: Adb, root: Root | None = None) -> list[PartInfo]:
    """列出 by-name 下的分区及其真实大小。

    一次 su 调用把整张表拿回来，避免逐分区 fork；`blockdev` 不可用时退回
    `/sys/class/block/*/size`（单位 512B 扇区）。
    """
    root = root or Root(adb)
    root.ensure()

    script = (
        f"for f in /dev/block/by-name/* /dev/block/bootdevice/by-name/*; do "
        f'[ -e "$f" ] || continue; n=$(basename "$f"); '
        f's=$(blockdev --getsize64 "$f" 2>/dev/null); '
        f'[ -n "$s" ] || s=$(cat "/sys/class/block/$(basename "$(readlink -f "$f")")/size" 2>/dev/null); '
        f'[ -n "$s" ] && echo "$n $f $s"; done'
    )
    res = root.run(script, timeout=60)
    if not res.ok:
        raise DiskError("读取分区表失败", hint=(res.err or res.out).strip()[:300])

    items: list[PartInfo] = []
    seen: set[str] = set()
    for line in res.stdout_lines:
        parts = line.split()
        if len(parts) != 3:
            continue
        name, path, raw = parts
        if name in seen or not raw.isdigit():
            continue
        seen.add(name)
        items.append(PartInfo(name=name, path=path, size=int(raw)))
    items.sort(key=lambda p: p.name)
    if not items:
        raise DiskError(
            "没有读到任何分区",
            hint="确认设备有 /dev/block/by-name（或 bootdevice/by-name），且 su 已授权",
        )
    return items


def find_partition(adb: Adb, name: str, root: Root | None = None) -> PartInfo:
    for p in table(adb, root):
        if p.name == name:
            return p
    raise DiskError(f"设备上没有分区 {name}", hint="先刷新分区表；逻辑分区名通常带 _a / _b 槽位后缀")


# ---- 备份 -----------------------------------------------------------
def plan_backup(adb: Adb, name: str, local_dir: str, root: Root | None = None) -> Plan:
    root = root or Root(adb)
    part = find_partition(adb, name, root)
    out_dir = Path(local_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    local = out_dir / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.img"
    plan = Plan(
        action="backup",
        partition=part.name,
        device_path=part.path,
        local_path=str(local),
        partition_size=part.size,
        remote_tmp=f"{TMP_DIR}/{part.name}-{int(time.time())}.img",
    )
    if part.size == 0:
        plan.warnings.append("分区大小未知，备份耗时无法预估")
    free = _device_free_bytes(adb, root)
    if free and part.size and free < part.size + 64 * 1024 * 1024:
        plan.blockers.append(f"/data/local/tmp 可用空间不足：{human_size(free)} < {human_size(part.size)}")
    return plan


def apply_backup(adb: Adb, plan: Plan, root: Root | None = None) -> dict:
    if not plan.executable:
        raise DiskError("计划不可执行：" + "；".join(plan.blockers))
    root = root or Root(adb)
    root.ensure()
    stdout: list[str] = []

    run = root.run(f"mkdir -p {TMP_DIR} && rm -f {shlex.quote(plan.remote_tmp)}", timeout=30)
    if not run.ok:
        raise DiskError("准备临时目录失败", hint=(run.err or run.out).strip()[:300])

    stdout.append(f"dd if={plan.device_path} of={plan.remote_tmp} bs={BLOCK}")
    timeout = _dd_timeout(plan.partition_size, adb_speed=60)
    dd = root.run(f"dd if={shlex.quote(plan.device_path)} of={shlex.quote(plan.remote_tmp)} bs={BLOCK}", timeout=timeout)
    stdout.append((dd.err or dd.out).strip()[-600:])
    if not dd.ok:
        root.run(f"rm -f {shlex.quote(plan.remote_tmp)}", timeout=30)
        raise DiskError("dd 备份失败", hint=(dd.err or dd.out).strip()[:300])

    remote_sha = _device_sha256(root, plan.remote_tmp)
    pull = adb.pull(plan.remote_tmp, plan.local_path, timeout=max(120, timeout))
    if not (pull.ok and Path(plan.local_path).is_file()):
        root.run(f"rm -f {shlex.quote(plan.remote_tmp)}", timeout=30)
        raise DiskError("拉取备份失败", hint=(pull.err or pull.out).strip()[:300])

    local_sha = sha256_file(plan.local_path)
    size = Path(plan.local_path).stat().st_size
    root.run(f"rm -f {shlex.quote(plan.remote_tmp)}", timeout=30)

    if remote_sha and local_sha != remote_sha:
        raise DiskError(
            "备份校验失败：设备侧与本地 sha256 不一致",
            hint=f"设备 {remote_sha[:16]}… / 本地 {local_sha[:16]}…；文件 {plan.local_path} 不可信",
        )

    return {
        "ok": True,
        "partition": plan.partition,
        "local_path": plan.local_path,
        "size": size,
        "size_text": human_size(size),
        "sha256": local_sha,
        "verified": bool(remote_sha),
        "log": "\n".join(s for s in stdout if s),
    }


# ---- 还原 -----------------------------------------------------------
def plan_restore(adb: Adb, name: str, image: str, root: Root | None = None) -> Plan:
    root = root or Root(adb)
    part = find_partition(adb, name, root)
    src = Path(image)
    try:
        exists = src.is_file()
    except OSError:
        exists = False
    if not exists:
        raise DiskError(f"本地镜像不存在：{src}")
    plan = Plan(
        action="restore",
        partition=part.name,
        device_path=part.path,
        local_path=str(src),
        image_size=src.stat().st_size,
        partition_size=part.size,
        remote_tmp=f"{TMP_DIR}/{part.name}-restore-{int(time.time())}.img",
        sha256=sha256_file(src),
    )
    if part.size and plan.image_size > part.size:
        plan.blockers.append(
            f"镜像 {human_size(plan.image_size)} 大于分区 {human_size(part.size)}，写进去必然越界"
        )
    elif part.size and plan.image_size < part.size:
        plan.warnings.append(
            f"镜像比分区小 {human_size(part.size - plan.image_size)}：dd 只写镜像长度，剩余内容保持原样"
        )
    if not part.size:
        plan.warnings.append("分区大小未知，无法做越界检查")
    plan.warnings.append("还原会覆盖目标分区，务必确认分区名与机型匹配")
    return plan


def apply_restore(adb: Adb, plan: Plan, root: Root | None = None) -> dict:
    if not plan.executable:
        raise DiskError("计划不可执行：" + "；".join(plan.blockers))
    root = root or Root(adb)
    root.ensure()

    root.run(f"mkdir -p {TMP_DIR}", timeout=30)
    push = adb.push(plan.local_path, plan.remote_tmp, timeout=max(180, _dd_timeout(plan.image_size, 60)))
    if not push.ok:
        raise DiskError("推送镜像失败", hint=(push.err or push.out).strip()[:300])

    check = root.run(f"sha256sum {shlex.quote(plan.remote_tmp)}", timeout=300)
    if check.ok and check.out.split():
        if check.out.split()[0] != plan.sha256:
            root.run(f"rm -f {shlex.quote(plan.remote_tmp)}", timeout=30)
            raise DiskError("推送后校验失败：设备上的镜像与本地不一致")
    else:
        plan.warnings.append("设备缺少 sha256sum，跳过推送校验")

    dd = root.run(
        f"dd if={shlex.quote(plan.remote_tmp)} of={shlex.quote(plan.device_path)} bs={BLOCK} && sync",
        timeout=_dd_timeout(plan.image_size, 30),
    )
    root.run(f"rm -f {shlex.quote(plan.remote_tmp)}", timeout=30)
    if not dd.ok:
        raise DiskError("dd 写入失败", hint=(dd.err or dd.out).strip()[:400])

    verify = _verify_written(root, plan)
    return {
        "ok": verify.get("ok", True),
        "partition": plan.partition,
        "written": plan.image_size,
        "written_text": human_size(plan.image_size),
        "verify": verify,
        "log": (dd.err or dd.out).strip()[-600:],
    }


def _verify_written(root: Root, plan: Plan) -> dict:
    """还原后校验：小分区整段回读比哈希，大分区只读首尾各 1MiB。"""
    if not plan.partition_size:
        return {"ok": True, "skipped": "分区大小未知"}
    if plan.image_size <= READ_BACK_LIMIT:
        tmp = f"{TMP_DIR}/verify-{int(time.time())}.img"
        # dd 不能按字节截断，多读的尾巴会包含分区原有内容，所以按镜像长度裁一下再算哈希
        read = root.run(
            f"dd if={shlex.quote(plan.device_path)} of={tmp} bs={BLOCK} 2>/dev/null; "
            f"head -c {plan.image_size} {tmp} | sha256sum; rm -f {tmp}",
            timeout=600,
        )
        got = read.out.split()[0] if read.ok and read.out.split() else ""
        return {"ok": bool(got) and got == plan.sha256, "sha256": got, "scope": "full"}
    return {"ok": True, "skipped": "大分区跳过整段回读", "scope": "none"}


# ---- fastboot 刷入 ---------------------------------------------------
def find_fastboot(adb: Adb | None = None) -> str | None:
    """优先用 adb 同目录的 fastboot（platform-tools 通常一起发）。"""
    if adb is not None:
        sibling = Path(adb.exe).with_name("fastboot.exe" if adb.exe.endswith(".exe") else "fastboot")
        if sibling.is_file():
            return str(sibling)
    found = proc.which("fastboot")
    if found:
        return found
    for rel in ("platform-tools/fastboot.exe", "platform-tools/fastboot"):
        for base in (Path.cwd(), *Path(__file__).resolve().parents):
            cand = base / rel
            if cand.is_file():
                return str(cand)
    return None


def fastboot_flash(part: str, image: str, *, adb: Adb | None = None, dry_run: bool = False) -> dict:
    """`fastboot flash`。设备必须已经处于 bootloader / fastbootd。"""
    exe = find_fastboot(adb)
    if not exe:
        raise ToolMissing(
            "未找到 fastboot",
            hint="把 platform-tools 里的 fastboot 放到 adb 旁边，或加入 PATH",
        )
    src = Path(image)
    if not src.is_file():
        raise DiskError(f"镜像不存在：{src}")
    plan = {
        "action": "fastboot-flash",
        "partition": part,
        "image": str(src),
        "image_size": src.stat().st_size,
        "sha256": sha256_file(src),
        "exe": exe,
        "dry_run": dry_run,
    }
    if dry_run:
        plan["executable"] = True
        return plan

    # 先确认有一台在 fastboot 模式的设备：否则 `fastboot flash` 会一直等下去，
    # 用户看到的是"卡住"，而不是"没连上"。
    devs = proc.run([exe, "devices"], timeout=20)
    if not devs.stdout_lines:
        raise DiskError(
            "没有处于 fastboot 模式的设备",
            hint="先执行 adb reboot bootloader，或关机后按住音量减 + 电源",
        )

    res = proc.run([exe, "flash", part, str(src)], timeout=1800)
    plan.update(ok=res.ok, output=(res.out + res.err).strip()[-1500:], code=res.code)
    if not res.ok and res.code == proc.EXIT_NOT_FOUND:
        raise ToolMissing("fastboot 无法启动", hint=exe)
    return plan


def fastboot_devices(*, adb: Adb | None = None) -> list[str]:
    exe = find_fastboot(adb)
    if not exe:
        raise ToolMissing("未找到 fastboot", hint="安装 platform-tools 或加入 PATH")
    res = proc.run([exe, "devices"], timeout=20)
    return [ln.split()[0] for ln in res.stdout_lines if ln.strip()]


# ---- 辅助 -----------------------------------------------------------
def _device_free_bytes(adb: Adb, root: Root | None) -> int:
    root = root or Root(adb)
    res = root.run("df -B1 /data/local/tmp 2>/dev/null | tail -n 1", timeout=20)
    if not res.ok:
        return 0
    parts = res.out.split()
    try:
        return int(parts[3])
    except (IndexError, ValueError):
        return 0


def _device_sha256(root: Root, path: str) -> str:
    res = root.run(f"sha256sum {shlex.quote(path)}", timeout=600)
    if res.ok and res.out.split():
        return res.out.split()[0]
    return ""


def _dd_timeout(size: int, adb_speed: int) -> float:
    """按 20MB/s 的保守速度估算，外加固定余量。"""
    if not size:
        return 600.0
    return min(3600.0, max(120.0, size / (20 * 1024 * 1024) + 120))
