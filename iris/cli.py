"""命令行入口。

第一阶段只做只读能力：环境自检、设备画像、GPT 解析。写入相关命令
（plan / apply）留到 v0.3，届时统一走"先生成计划、再执行"的流程。
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from . import __version__
from .core import diag
from .core.adb import Adb
from .core.errors import IrisError
from .core.image import avb as avb_mod
from .core.image import bootimg as bootimg_mod
from .core.image import lp as lp_mod
from .core.image import payload as payload_mod
from .core.image import sparse as sparse_mod
from .core.partition import gpt as gpt_mod
from .core.profile import load_cached, probe, save


# ---- 输出辅助 -----------------------------------------------------
def _dw(text: str) -> int:
    """按终端显示宽度计算（中文占两格）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _dw(text))


def _table(rows: list[list[str]], headers: list[str] | None = None) -> str:
    rows = [[str(c) for c in row] for row in rows]
    if headers:
        rows = [[str(h) for h in headers]] + rows
    widths = [max(_dw(r[i]) for r in rows) for i in range(len(rows[0]))] if rows else []
    lines = []
    for idx, row in enumerate(rows):
        lines.append("  ".join(_pad(c, widths[i]) for i, c in enumerate(row)).rstrip())
        if headers and idx == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _emit(payload: dict | list, as_json: bool, human: str) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2) if as_json else human)


def _size(n: int) -> str:
    step = 1024.0
    val = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if val < step or unit == "TiB":
            return f"{val:.1f}{unit}" if unit != "B" else f"{int(val)}B"
        val /= step
    return f"{n}B"


# ---- 子命令 -------------------------------------------------------
def cmd_version(_args) -> int:
    print(f"iris {__version__}")
    return 0


def cmd_doctor(args) -> int:
    report = diag.run_check(adb_exe=args.adb)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        icon = {diag.OK: "✓", diag.WARN: "!", diag.FAIL: "✗"}
        rows = [[icon.get(c.status, "?"), c.name, c.detail] for c in report.checks]
        print(_table(rows, ["状态", "检查项", "结果"]))
        for c in report.checks:
            if c.hint and c.status != diag.OK:
                print(f"  ↳ {c.name}: {c.hint}")
        print()
        print(f"{len(report.failed)} 项失败，{len(report.warnings)} 项警告")
    return 1 if report.failed else 0


def _load_profile(args):
    if not args.refresh:
        cached = load_cached(args.serial) if args.serial else None
        if cached and not args.refresh:
            return cached, True
    adb = Adb(exe=args.adb, serial=args.serial)
    prof = probe(adb, serial=args.serial)
    save(prof)
    return prof, False


def cmd_info(args) -> int:
    prof, cached = _load_profile(args)

    if args.json:
        print(json.dumps(prof.to_dict(), ensure_ascii=False, indent=2))
        return 0

    rows = [
        ("序列号", prof.serial),
        ("机型", f"{prof.brand} {prof.model}".strip()),
        ("代号", prof.codename),
        ("SoC", f"{prof.soc_manufacturer} {prof.soc_model}".strip()),
        ("系统", f"Android {prof.android_release} (SDK {prof.sdk})"),
        ("架构", prof.abi),
        ("安全补丁", prof.security_patch or "未知"),
        ("A/B", f"是（槽位 {prof.slot_suffix or '?'}）" if prof.ab_update else "否（单槽位）"),
        ("ROOT", "是" if prof.root else "否"),
        ("by-name 根", prof.by_name_root or "未探测到"),
        ("块设备", prof.block_device or "未知"),
        ("已知分区", f"{len(prof.partitions)} 个" if prof.partitions else "0"),
    ]
    width = max(_dw(r[0]) for r in rows)
    for k, v in rows:
        print(f"{_pad(k, width)} : {v}")
    if args.verbose:
        print("\n探测明细：")
        print(_table([[p.name, "ok" if p.ok else "fail", p.evidence] for p in prof.probes],
                     ["探测项", "结果", "证据"]))
    print(f"\n（{'来自缓存' if cached else '刚刚探测'}，probed_at={prof.probed_at:.0f}）")
    return 0


def cmd_devices(args) -> int:
    adb = Adb(exe=args.adb)
    devs = adb.devices()
    if args.json:
        print(json.dumps([d.__dict__ for d in devs], ensure_ascii=False, indent=2))
        return 0 if devs else 0
    if not devs:
        print("没有检测到设备。运行 `iris doctor` 查看环境。")
        return 0
    print(_table([[d.serial, d.state, d.model or "-", d.product or "-"] for d in devs],
                 ["序列号", "状态", "机型", "产品"]))
    return 0


def cmd_gpt(args) -> int:
    table = gpt_mod.read_path(args.image)
    if args.json:
        print(json.dumps(table.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"文件    : {Path(args.image)}")
    print(f"扇区大小: {table.sector_size}B")
    print(f"磁盘 GUID: {table.disk_guid}")
    print(f"来源    : {table.source}（CRC {'通过' if table.crc_ok else '异常'}）")
    print(f"分区数  : {len(table.partitions)}\n")
    rows = []
    for p in table.partitions:
        start, end = p.byte_range(table.sector_size)
        rows.append([p.index, p.name or "(未命名)", str(p.type_guid)[:8], start, _size(end - start)])
    print(_table(rows, ["#", "名称", "类型", "起始字节", "大小"]))
    return 0


def cmd_super(args) -> int:
    meta = lp_mod.read_path(args.image)

    if args.extract:
        part = meta.find(args.extract)
        if part is None:
            names = ", ".join(p.name for p in meta.partitions[:12])
            raise IrisError(f"分区 {args.extract} 不存在", hint=f"可选：{names}")
        out = args.out or f"{part.name}.img"
        stats = lp_mod.extract_partition(meta, part, out, src=args.image)
        print(f"已提取 {part.name} → {out}（{lp_mod.human_size(stats['bytes'])}）")
        return 0

    if args.json:
        print(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"文件  : {Path(args.image)}")
    print(f"版本  : {meta.header.major}.{meta.header.minor}（header {meta.header.header_size}B，"
          f"flags 0x{meta.header.flags:X}）")
    print(f"块大小: {meta.geometry.logical_block_size}B")
    print(f"逻辑总容量: {lp_mod.human_size(meta.logical_size)} / {len(meta.partitions)} 个分区")
    if meta.warnings:
        print("⚠ " + "；".join(meta.warnings))
    print()

    rows = []
    for p in meta.partitions:
        attrs = ",".join(a for a, on in (
            ("ro", p.readonly), ("slotsuffix", p.slot_suffixed),
            ("updated", bool(p.attributes & lp_mod.ATTR_UPDATED)),
            ("disabled", bool(p.attributes & lp_mod.ATTR_DISABLED)),
        ) if on) or "-"
        rows.append([p.name, lp_mod.human_size(p.size_bytes), len(p.extents), attrs])
    print(_table(rows, ["分区", "大小", "extent 数", "属性"]))

    if args.verbose:
        print("\nextent 明细：")
        for p in meta.partitions:
            for i, e in enumerate(p.extents):
                kind = "linear" if e.is_linear else ("zero" if e.is_zero else str(e.target_type))
                print(f"  {p.name}[{i}] {kind} sectors={e.num_sectors} "
                      f"offset={e.byte_offset} ({lp_mod.human_size(e.num_sectors * 512)})")
    print("\n提取某个分区：iris super <super.img> --extract system_a --out system.img")
    return 0


def cmd_boot(args) -> int:
    img = bootimg_mod.parse(args.image)
    if args.json:
        print(json.dumps(img.to_dict(), ensure_ascii=False, indent=2))
        return 0

    rows = [
        ("header 版本", f"v{img.header_version}"),
        ("头大小", f"{img.header_size}B"),
        ("页大小", f"{img.page_size}B"),
        ("内核", f"{lp_mod.human_size(img.kernel_size)} @ {img.kernel_offset}"),
        ("ramdisk", f"{lp_mod.human_size(img.ramdisk_size)} @ {img.ramdisk_offset}"),
        ("second", f"{lp_mod.human_size(img.second_size)}"),
        ("系统版本", img.os_version),
        ("名称", img.name or "—"),
        ("cmdline", img.cmdline or "—"),
    ]
    width = max(_dw(k) for k, _ in rows)
    for k, v in rows:
        print(f"{_pad(k, width)} : {v}")
    for note in img.notes:
        print(f"⚠ {note}")
    return 0


def cmd_avb(args) -> int:
    meta = avb_mod.parse(args.image)
    if args.json:
        print(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"版本      : {meta.version_major}.{meta.version_minor}")
    print(f"签名算法  : {meta.algorithm_name}")
    print(f"flags     : 0x{meta.flags:X}")
    print(f"verity    : {'已关闭' if meta.is_verity_disabled else '启用'}")
    print(f"校验/验证 : {', '.join(meta.flag_names) or '均启用'}")
    print(f"auth 块   : {meta.auth_size}B · aux 块 {meta.aux_size}B")
    print(f"工具版本  : {meta.release_string or '—'}")
    if meta.descriptors:
        print("\n描述符：")
        for tag, size in meta.descriptors:
            name = avb_mod.DESCRIPTOR_TAGS.get(tag, f"unknown({tag})")
            print(f"  - {name} ({size}B)")
    return 0


def cmd_sparse(args) -> int:
    blob = Path(args.image).read_bytes()
    info = sparse_mod.describe(blob)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"文件    : {Path(args.image)}")
        print(f"块大小  : {info['block_size']}B（{info['total_blocks']} 块）")
        print(f"展开后  : {lp_mod.human_size(info['expanded_size'])}")
        print(f"chunk   : {info['total_chunks']} 个 —— " +
              ", ".join(f"{k}×{v}" for k, v in info["chunk_stats"].items()))

    if args.unpack:
        stats = sparse_mod.unpack(args.image, args.unpack)
        print(f"已展开到: {args.unpack}（{lp_mod.human_size(stats['expanded_bytes'])}）")
    return 0


def cmd_gui(args) -> int:
    from .web import serve

    return serve(port=args.port, open_browser=not args.no_browser, quiet=args.quiet)


def cmd_export(args) -> int:
    from .web.export import export

    path = export(args.out, image=args.image)
    print(f"已导出单文件界面：{path}")
    print("双击即可打开（快照，不能刷新；实时功能请用 iris gui / 启动.bat）")
    return 0


def cmd_payload(args) -> int:
    pay = payload_mod.parse(args.image)

    if args.extract:
        part = pay.find(args.extract)
        if part is None:
            names = ", ".join(p.name for p in pay.partitions[:12])
            raise IrisError(f"分区 {args.extract} 不存在", hint=f"可选：{names}")
        out = args.out or f"{part.name}.img"
        stats = payload_mod.extract(pay, part, out, src=args.image)
        print(f"已提取 {part.name} → {out}（{lp_mod.human_size(stats['bytes'])}）")
        return 0

    if args.json:
        print(json.dumps(pay.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"文件  : {Path(args.image)}")
    print(f"版本  : {pay.version} · 块大小 {pay.block_size}B · {len(pay.partitions)} 个分区\n")
    rows = [[p.name, lp_mod.human_size(p.blocks * pay.block_size), len(p.operations),
             ",".join(sorted({op.type_name for op in p.operations}))] for p in pay.partitions]
    print(_table(rows, ["分区", "解包后大小", "操作数", "类型"]))
    print("\n提取某个分区：iris payload <payload.bin> --extract boot --out boot.img")
    return 0


# ---- 解析器 -------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iris", description="Iris —— Android 设备工具链")
    p.add_argument("--version", action="version", version=f"iris {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--adb", help="adb 可执行文件路径（默认走 PATH / IRIS_ADB）")
        sp.add_argument("--serial", help="指定设备序列号")
        sp.add_argument("--json", action="store_true", help="输出 JSON")

    sp = sub.add_parser("doctor", help="环境自检")
    add_common(sp)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("devices", help="列出设备")
    add_common(sp)
    sp.set_defaults(func=cmd_devices)

    sp = sub.add_parser("info", help="设备画像（机型/SoC/槽位/分区路径）")
    add_common(sp)
    sp.add_argument("--refresh", action="store_true", help="忽略缓存重新探测")
    sp.add_argument("--verbose", action="store_true", help="显示探测明细")
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("gpt", help="解析 GPT 分区表（离线，支持 .img/.bin）")
    sp.add_argument("image", help="磁盘镜像文件")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.set_defaults(func=cmd_gpt)

    sp = sub.add_parser("super", help="解析 super 动态分区元数据（离线）")
    sp.add_argument("image", help="super 镜像文件")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.add_argument("--verbose", action="store_true", help="显示 extent 明细")
    sp.add_argument("--extract", metavar="PART", help="提取指定分区")
    sp.add_argument("--out", metavar="FILE", help="提取输出路径")
    sp.set_defaults(func=cmd_super)

    sp = sub.add_parser("boot", help="解析 boot.img / init_boot.img 头")
    sp.add_argument("image", help="boot 镜像文件")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.set_defaults(func=cmd_boot)

    sp = sub.add_parser("avb", help="解析 vbmeta / AVB 签名信息")
    sp.add_argument("image", help="vbmeta 镜像文件")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.set_defaults(func=cmd_avb)

    sp = sub.add_parser("sparse", help="识别/展开 Android sparse 镜像")
    sp.add_argument("image", help="sparse 镜像文件")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.add_argument("--unpack", metavar="OUT", help="展开到指定 raw 文件")
    sp.set_defaults(func=cmd_sparse)

    sp = sub.add_parser("payload", help="解析/提取 OTA payload.bin 里的分区")
    sp.add_argument("image", help="payload.bin 文件")
    sp.add_argument("--json", action="store_true", help="输出 JSON")
    sp.add_argument("--extract", metavar="PART", help="提取指定分区")
    sp.add_argument("--out", metavar="FILE", help="提取输出路径")
    sp.set_defaults(func=cmd_payload)

    sp = sub.add_parser("gui", help="启动本地 Web 界面")
    sp.add_argument("--port", type=int, default=0, help="端口（默认随机）")
    sp.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    sp.add_argument("--quiet", action="store_true", help="不打印访问日志")
    sp.set_defaults(func=cmd_gui)

    sp = sub.add_parser("export", help="导出单文件 HTML 快照（无需服务，双击可看）")
    sp.add_argument("out", help="输出 html 路径")
    sp.add_argument("--image", help="顺带把一个镜像的分析结果嵌进快照")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("version", help="显示版本")
    sp.set_defaults(func=cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except IrisError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        if exc.hint:
            print(f"  建议：{exc.hint}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
