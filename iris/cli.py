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


def cmd_app(args) -> int:
    from .core.device import apps as device_apps

    adb = Adb(exe=args.adb, serial=args.serial)
    if args.app_cmd == "list":
        pkgs = device_apps.list_packages(adb, third_party_only=not args.all)
        if args.json:
            print(json.dumps(pkgs, ensure_ascii=False, indent=2))
        else:
            for p in pkgs:
                print(p)
            print(f"\n共 {len(pkgs)} 个")
        return 0

    if args.app_cmd == "install":
        target = args.target or ""
        if not target:
            raise IrisError("缺少 APK 路径", hint="iris app install <x.apk>")
        ok, msg = device_apps.install(adb, target)
        print(("✓ " if ok else "✗ ") + msg)
        return 0 if ok else 1

    if args.app_cmd == "uninstall":
        target = args.target or ""
        if not target:
            raise IrisError("缺少包名", hint="iris app uninstall <包名>")
        ok, msg = device_apps.uninstall(adb, target)
        print(("✓ " if ok else "✗ ") + msg)
        return 0 if ok else 1

    if args.app_cmd in ("freeze", "unfreeze"):
        target = args.target or ""
        if not target:
            raise IrisError("缺少包名")
        ok, msg = device_apps.set_enabled(adb, target, args.app_cmd == "unfreeze")
        print(("✓ " if ok else "✗ ") + msg)
        return 0 if ok else 1

    if args.app_cmd == "clear":
        target = args.target or ""
        if not target:
            raise IrisError("缺少包名")
        ok, msg = device_apps.clear_data(adb, target)
        print(("✓ " if ok else "✗ ") + msg)
        return 0 if ok else 1

    if args.app_cmd == "extract":
        target = args.target or ""
        if not target:
            raise IrisError("缺少包名")
        ok, msg = device_apps.extract_apk(adb, target, args.out or ".")
        print(("✓ " if ok else "✗ ") + msg)
        return 0 if ok else 1

    raise IrisError("未知子命令", hint="list / install / uninstall / freeze / unfreeze / clear / extract")


def cmd_shell(args) -> int:
    from .core.device import apps as device_apps

    adb = Adb(exe=args.adb, serial=args.serial)
    ok, text = device_apps.shell(adb, args.command, timeout=args.timeout)
    print(text or "(无输出)")
    return 0 if ok else 1


def cmd_hash(args) -> int:
    from .core.tools import local

    result = local.hash_file(args.file)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"文件   : {result['path']}")
        print(f"大小   : {lp_mod.human_size(result['size'])}")
        for algo in ("md5", "sha1", "sha256"):
            if algo in result:
                print(f"{algo:<7}: {result[algo]}")
    return 0


def cmd_split(args) -> int:
    from .core.tools import local

    parts = local.split_file(args.file, args.size, args.out)
    print(f"已拆成 {len(parts)} 片")
    for p in parts[:8]:
        print("  " + p)
    if len(parts) > 8:
        print(f"  …… 共 {len(parts)} 片")
    return 0


def cmd_join(args) -> int:
    from .core.tools import local

    result = local.join_files(args.parts, args.out)
    print(f"已合并 {result['parts']} 片 → {args.out}（{lp_mod.human_size(result['bytes'])}）")
    return 0


def cmd_sparsepack(args) -> int:
    from .core.tools import local

    result = local.pack_sparse(args.file, args.out, block_size=args.block_size)
    print(f"已打包 → {args.out}")
    print(f"  {lp_mod.human_size(result['input_bytes'])} → {lp_mod.human_size(result['output_bytes'])}"
          f"（{result['chunks']} 个 chunk）")
    return 0


def cmd_gptxml(args) -> int:
    from .core.tools import local

    result = local.gpt_to_rawprogram(args.file, args.out)
    print(f"已生成 {args.out}（{result['partitions']} 个分区，扇区 {result['sector_size']}B）")
    return 0


def cmd_bootunpack(args) -> int:
    result = bootimg_mod.extract(bootimg_mod.parse(args.file), args.file, args.out)
    print(f"已解包到 {result['output_dir']}")
    print(f"  kernel  {lp_mod.human_size(result['kernel_bytes'])}")
    if result["ramdisk_bytes"]:
        print(f"  ramdisk {lp_mod.human_size(result['ramdisk_bytes'])}")
    return 0


def cmd_push(args) -> int:
    from .core.device import files as device_files

    ok, msg = device_files.push(Adb(exe=args.adb, serial=args.serial), args.local, args.remote)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


def cmd_pull(args) -> int:
    from .core.device import files as device_files

    ok, msg = device_files.pull(Adb(exe=args.adb, serial=args.serial), args.remote, args.local)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


def cmd_ls(args) -> int:
    from .core.device import files as device_files

    items = device_files.ls(Adb(exe=args.adb, serial=args.serial), args.path)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    for it in items:
        print(f"{it['perm']:<12} {it['size']:>10}  {it['name']}")
    return 0


def cmd_record(args) -> int:
    from .core.device import files as device_files

    ok, msg = device_files.record(Adb(exe=args.adb, serial=args.serial), args.seconds, args.out)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


def cmd_tcpip(args) -> int:
    from .core.device import files as device_files

    ok, msg = device_files.tcpip(Adb(exe=args.adb, serial=args.serial), args.port)
    print(("✓ " if ok else "✗ ") + msg)
    if ok:
        print("接着执行： iris connect <手机IP>")
    return 0 if ok else 1


def cmd_connect(args) -> int:
    from .core.device import files as device_files

    ok, msg = device_files.connect(args.host, args.port)
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


def cmd_root(args) -> int:
    from .core.device import root as device_root

    status = device_root.detect(Adb(exe=args.adb, serial=args.serial))
    if args.json:
        print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
        return 0 if status.available else 5
    rows = [
        ("ROOT", "是" if status.available else "否"),
        ("方式", status.method or "—"),
        ("管理器", f"{status.manager} {status.version}".strip()),
        ("su", status.su_path or "—"),
        ("说明", status.reason or "—"),
    ]
    width = max(_dw(r[0]) for r in rows)
    for k, v in rows:
        print(f"{_pad(k, width)} : {v}")
    return 0 if status.available else 5


def cmd_part(args) -> int:
    from .core.device import partitions

    adb = Adb(exe=args.adb, serial=args.serial)

    if args.part_cmd == "list":
        parts = partitions.table(adb)
        if args.json:
            print(json.dumps([p.to_dict() for p in parts], ensure_ascii=False, indent=2))
            return 0
        print(_table([[p.name, p.size_text, p.path] for p in parts], ["分区", "大小", "设备路径"]))
        print(f"\n共 {len(parts)} 个分区")
        return 0

    if args.part_cmd == "backup":
        plan = partitions.plan_backup(adb, args.name, args.dir)
        if args.json and args.dry_run:
            print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            return 0
        print(f"计划：备份 {plan.partition} → {plan.local_path}")
        for w in plan.warnings:
            print(f"  ! {w}")
        for b in plan.blockers:
            print(f"  ✗ {b}")
        if args.dry_run or not plan.executable:
            return 0 if plan.executable else 8
        result = partitions.apply_backup(adb, plan)
        print(f"✓ 已备份到 {result['local_path']}（{result['size_text']}）")
        print(f"  sha256 {result['sha256']}  双端校验：{'通过' if result['verified'] else '设备缺少 sha256sum'}")
        return 0

    if args.part_cmd == "restore":
        plan = partitions.plan_restore(adb, args.name, args.image)
        print(f"计划：用 {plan.local_path} 覆盖 {plan.partition}（{plan.partition_size_text}）")
        for w in plan.warnings:
            print(f"  ! {w}")
        for b in plan.blockers:
            print(f"  ✗ {b}")
        if args.dry_run or not plan.executable:
            return 0 if plan.executable else 8
        if not args.yes:
            raise IrisError("还原会覆盖分区，确认请加 --yes", hint="先用 --dry-run 看计划")
        result = partitions.apply_restore(adb, plan)
        ok = result.get("ok", False)
        print(("✓ 已写入 " if ok else "✗ 写入后校验失败 ") + plan.partition)
        return 0 if ok else 1

    if args.part_cmd == "flash":
        result = partitions.fastboot_flash(args.name, args.image, adb=adb, dry_run=args.dry_run)
        if args.dry_run:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if not args.yes:
            raise IrisError("fastboot 刷写不可撤销，确认请加 --yes")
        print(("✓ " if result.get("ok") else "✗ ") + result.get("output", ""))
        return 0 if result.get("ok") else 1
    return 1


def cmd_module(args) -> int:
    from .core.device import modules

    adb = Adb(exe=args.adb, serial=args.serial)

    if args.module_cmd == "list":
        mgr = modules.manager(adb)
        items = modules.list_modules(adb)
        if args.json:
            print(json.dumps({"manager": mgr.to_dict(), "modules": [m.to_dict() for m in items]},
                             ensure_ascii=False, indent=2))
            return 0
        print(f"管理器：{mgr.name} {mgr.version}".strip())
        if not items:
            print("没有已安装模块")
            return 0
        print(_table(
            [["✓" if m.enabled else "✗", m.name, m.version, m.author or "-",
              ("待卸载" if m.pending_remove else "")] for m in items],
            ["启用", "模块", "版本", "作者", "状态"],
        ))
        return 0

    if args.module_cmd == "install":
        ok, msg = modules.install(adb, args.target)
    elif args.module_cmd in ("enable", "disable"):
        ok, msg = modules.toggle(adb, args.target, args.module_cmd == "enable")
    elif args.module_cmd == "remove":
        ok, msg = modules.mark_remove(adb, args.target)
    elif args.module_cmd == "log":
        print(modules.logs(adb, lines=args.lines))
        return 0
    else:
        return 1
    print(("✓ " if ok else "✗ ") + msg)
    return 0 if ok else 1


def cmd_supermake(args) -> int:
    from .core.image import superbuild

    parts: list[tuple[str, str]] = []
    for item in args.part:
        if "=" not in item:
            raise IrisError(f"--part 格式应为 名字=文件：{item}")
        name, path = item.split("=", 1)
        parts.append((name.strip(), path.strip()))
    if not parts:
        raise IrisError("至少给一个 --part", hint="例：--part system_a=system.img")

    size = None
    if args.size:
        from .core.tools import local

        size = local._parse_size(args.size)

    result = superbuild.merge(parts, args.out, total_size=size)
    print(f"已生成 {args.out}（{lp_mod.human_size(result['out_bytes'])}）")
    for p in result["partitions"]:
        print(f"  {p['name']:<16} {lp_mod.human_size(p['size']):>10}  offset={p['offset']}")
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

    sp = sub.add_parser("app", help="应用管理：list / install / uninstall")
    add_common(sp)
    sp.add_argument("app_cmd", choices=["list", "install", "uninstall", "freeze", "unfreeze", "clear", "extract"])
    sp.add_argument("target", nargs="?", help="APK 路径或包名")
    sp.add_argument("--all", action="store_true", help="列表包含系统应用")
    sp.add_argument("--out", help="提取 APK 时的输出目录")
    sp.set_defaults(func=cmd_app)

    sp = sub.add_parser("shell", help="在设备上执行 shell 命令")
    sp.add_argument("command", help="要执行的命令")
    sp.add_argument("--timeout", type=float, default=30.0, help="超时秒数")
    add_common(sp)
    sp.set_defaults(func=cmd_shell)

    sp = sub.add_parser("root", help="检测 root 与管理器（Magisk / KernelSU / APatch）")
    add_common(sp)
    sp.set_defaults(func=cmd_root)

    sp = sub.add_parser("part", help="分区：list / backup / restore / flash")
    add_common(sp)
    sp.add_argument("part_cmd", choices=["list", "backup", "restore", "flash"])
    sp.add_argument("name", nargs="?", help="分区名，如 boot_a")
    sp.add_argument("image", nargs="?", help="还原/刷写用的本地镜像")
    sp.add_argument("--dir", default="backups", help="备份保存目录")
    sp.add_argument("--dry-run", action="store_true", help="只输出计划，不执行")
    sp.add_argument("--yes", action="store_true", help="确认执行写操作")
    sp.set_defaults(func=cmd_part)

    sp = sub.add_parser("module", help="模块：list / install / enable / disable / remove / log")
    add_common(sp)
    sp.add_argument("module_cmd", choices=["list", "install", "enable", "disable", "remove", "log"])
    sp.add_argument("target", nargs="?", help="模块名或 zip 路径")
    sp.add_argument("--lines", type=int, default=200, help="日志行数")
    sp.set_defaults(func=cmd_module)

    sp = sub.add_parser("push", help="把本地文件推到设备")
    sp.add_argument("local", help="本地路径")
    sp.add_argument("remote", help="设备路径")
    add_common(sp)
    sp.set_defaults(func=cmd_push)

    sp = sub.add_parser("pull", help="把设备文件拉到本地")
    sp.add_argument("remote", help="设备路径")
    sp.add_argument("local", help="本地路径")
    add_common(sp)
    sp.set_defaults(func=cmd_pull)

    sp = sub.add_parser("ls", help="列出设备目录")
    sp.add_argument("path", nargs="?", default="/sdcard", help="设备路径")
    add_common(sp)
    sp.set_defaults(func=cmd_ls)

    sp = sub.add_parser("record", help="录屏")
    sp.add_argument("--seconds", type=int, default=15, help="时长（1-180 秒）")
    sp.add_argument("--out", default="shots", help="保存目录")
    add_common(sp)
    sp.set_defaults(func=cmd_record)

    sp = sub.add_parser("tcpip", help="开启无线调试端口")
    sp.add_argument("--port", type=int, default=5555)
    add_common(sp)
    sp.set_defaults(func=cmd_tcpip)

    sp = sub.add_parser("connect", help="连接无线调试设备")
    sp.add_argument("host", help="手机 IP")
    sp.add_argument("--port", type=int, default=5555)
    add_common(sp)
    sp.set_defaults(func=cmd_connect)

    sp = sub.add_parser("hash", help="计算文件 MD5 / SHA1 / SHA256")
    sp.add_argument("file", help="文件路径")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_hash)

    sp = sub.add_parser("split", help="按大小拆分文件（如 2G / 512M）")
    sp.add_argument("file", help="文件路径")
    sp.add_argument("--size", required=True, help="每片大小，例如 2G")
    sp.add_argument("--out", help="输出目录（默认同目录）")
    sp.set_defaults(func=cmd_split)

    sp = sub.add_parser("join", help="合并分片")
    sp.add_argument("parts", help="分片目录、前缀或通配符")
    sp.add_argument("--out", required=True, help="输出文件")
    sp.set_defaults(func=cmd_join)

    sp = sub.add_parser("sparsepack", help="把 raw 镜像打包成 sparse")
    sp.add_argument("file", help="raw 镜像")
    sp.add_argument("--out", required=True, help="输出 sparse 文件")
    sp.add_argument("--block-size", type=int, default=4096, dest="block_size")
    sp.set_defaults(func=cmd_sparsepack)

    sp = sub.add_parser("gptxml", help="由 GPT 生成 rawprogram.xml（9008 用）")
    sp.add_argument("file", help="带 GPT 的磁盘镜像")
    sp.add_argument("--out", required=True, help="输出 xml")
    sp.set_defaults(func=cmd_gptxml)

    sp = sub.add_parser("bootunpack", help="拆出 boot.img 的内核与 ramdisk")
    sp.add_argument("file", help="boot 镜像")
    sp.add_argument("--out", required=True, help="输出目录")
    sp.set_defaults(func=cmd_bootunpack)

    sp = sub.add_parser("supermake", help="把散包合并成 super.img")
    sp.add_argument("--part", action="append", default=[], help="名字=文件，可重复")
    sp.add_argument("--out", required=True, help="输出 super.img")
    sp.add_argument("--size", help="总大小，例如 8G（默认按数据量算）")
    sp.set_defaults(func=cmd_supermake)

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
