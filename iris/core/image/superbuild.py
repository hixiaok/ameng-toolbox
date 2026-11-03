"""super（动态分区）合并：把散包写成合法的 super.img。

只写数据，不做压缩。布局：

    0            保留 4096
    4096         geometry（52 字节，占 1 个 4096 块）
    8192         primary metadata（header + 4 张表，槽位预留）
    data_start   align(8192 + slot 预留, 1MiB) 起，每个分区按 1MiB 对齐

checksum 全部按 AOSP 规则算：hash 前把 checksum 字段本身置零。
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import IrisError

GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030
GEOMETRY_SIZE = 4096
SECTOR = 512
NAME_LEN = 36
ALIGN = 1024 * 1024
METADATA_MAX = 65536
METADATA_SLOTS = 2
GEOMETRY_OFF = 4096
METADATA_OFF = GEOMETRY_OFF + GEOMETRY_SIZE


def _align_up(value: int, align: int) -> int:
    return (value + align - 1) // align * align


def _name_bytes(name: str) -> bytes:
    raw = name.encode("utf-8")
    if len(raw) >= NAME_LEN:
        raise IrisError(f"分区名过长（最多 {NAME_LEN - 1} 字节）：{name}")
    return raw.ljust(NAME_LEN, b"\x00")


@dataclass
class SourcePartition:
    name: str
    path: Path
    size: int = 0
    offset: int = 0
    readonly: bool = True


@dataclass
class MergePlan:
    parts: list[SourcePartition] = field(default_factory=list)
    data_start: int = 0
    total_size: int = 0
    group_name: str = "default"

    def summary(self) -> dict:
        return {
            "data_start": self.data_start,
            "total_size": self.total_size,
            "partitions": [
                {"name": p.name, "size": p.size, "offset": p.offset} for p in self.parts
            ],
        }


def plan(
    partitions: list[tuple[str, str | Path]],
    *,
    total_size: int | None = None,
    group_name: str = "default",
) -> MergePlan:
    """计算布局。total_size 不给就按数据量自动算。"""
    if not partitions:
        raise IrisError("至少要给一个分区")

    reserved = METADATA_OFF + METADATA_MAX * METADATA_SLOTS
    cursor = _align_up(reserved, ALIGN)

    plan_obj = MergePlan(data_start=cursor, group_name=group_name)
    seen: set[str] = set()

    for name, path in partitions:
        if name in seen:
            raise IrisError(f"分区名重复：{name}")
        seen.add(name)
        p = Path(path)
        if not p.is_file():
            raise IrisError(f"分区文件不存在：{p}")
        size = p.stat().st_size
        if size == 0:
            raise IrisError(f"分区文件为空：{p}")

        plan_obj.parts.append(SourcePartition(name=name, path=p, size=size, offset=cursor))
        cursor = _align_up(cursor + size, ALIGN)

    if total_size is not None and total_size < cursor:
        raise IrisError(f"指定的总大小不够：需要至少 {cursor} 字节，你给了 {total_size}")
    plan_obj.total_size = total_size if total_size else cursor
    return plan_obj


def _geometry(data_start: int, total_size: int) -> bytes:
    geom = bytearray(52)
    struct.pack_into("<II", geom, 0, GEOMETRY_MAGIC, 52)
    struct.pack_into("<III", geom, 40, METADATA_MAX, METADATA_SLOTS, 4096)
    geom[8:40] = hashlib.sha256(bytes(geom)).digest()
    return bytes(geom) + b"\x00" * (GEOMETRY_SIZE - 52)


def build_metadata(p: MergePlan) -> bytes:
    """生成 header + 四张表。"""
    n_parts = len(p.parts)
    part_tbl = bytearray()
    ext_tbl = bytearray()
    for i, src in enumerate(p.parts):
        attrs = 1 if src.readonly else 0          # LP_PARTITION_ATTR_READONLY
        part_tbl += _name_bytes(src.name) + struct.pack("<IIII", attrs, i, 1, 0)
        sectors = _align_up(src.size, SECTOR) // SECTOR
        ext_tbl += struct.pack("<QIQI", sectors, 0, src.offset // SECTOR, 0)

    grp_tbl = _name_bytes(p.group_name) + struct.pack("<IQ", 0, 0)

    blk_tbl = (
        struct.pack("<QIIQ", p.data_start // SECTOR, ALIGN, 0, p.total_size)
        + _name_bytes("super")
        + struct.pack("<I", 0)
    )

    tables = bytes(part_tbl) + bytes(ext_tbl) + bytes(grp_tbl) + blk_tbl
    descs = (
        (0, n_parts, 52),
        (len(part_tbl), n_parts, 24),
        (len(part_tbl) + len(ext_tbl), 1, 48),
        (len(part_tbl) + len(ext_tbl) + len(grp_tbl), 1, 64),
    )

    header = bytearray(256)
    struct.pack_into("<IHHI", header, 0, HEADER_MAGIC, 10, 2, 256)
    header[12:44] = b"\x00" * 32
    struct.pack_into("<I", header, 44, len(tables))
    struct.pack_into("<I", header, 128, 0)
    header[48:80] = hashlib.sha256(tables).digest()
    for i, (off, num, esize) in enumerate(descs):
        struct.pack_into("<III", header, 80 + i * 12, off, num, esize)
    header[12:44] = hashlib.sha256(bytes(header)).digest()
    return bytes(header) + tables


def merge(
    partitions: list[tuple[str, str | Path]],
    out: str | Path,
    *,
    total_size: int | None = None,
    group_name: str = "default",
) -> dict:
    """把散包合并成 super.img。"""
    p = plan(partitions, total_size=total_size, group_name=group_name)
    target = Path(out)

    with target.open("wb") as f:
        f.truncate(p.total_size)
        f.seek(GEOMETRY_OFF)
        f.write(_geometry(p.data_start, p.total_size))
        f.seek(METADATA_OFF)
        f.write(build_metadata(p))

        for src in p.parts:
            f.seek(src.offset)
            with src.path.open("rb") as s:
                while chunk := s.read(4 << 20):
                    f.write(chunk)

    return {
        "output": str(target),
        "out_bytes": target.stat().st_size,
        "data_start": p.data_start,
        "partitions": [{"name": s.name, "size": s.size, "offset": s.offset} for s in p.parts],
    }
