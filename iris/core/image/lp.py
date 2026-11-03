"""Android 动态分区（super）LP 元数据解析。

格式对齐 AOSP `liblp/metadata_format.h`，字段尺寸以上游
`EdlDynamicSuper/LpMake/LpMakeConstants.cs` 与 `EdlVersionInfo/LpMetadataParser.cs`
交叉核对过：

    geometry  52 字节（实际占 4096 区块）
    header    v10 128 字节 / v12 256 字节
    partition 52 / extent 24 / group 48 / block_device 64
    四张表：partitions, extents, groups, block_devices

与上游的区别：
* 不硬编码 metadata 起始偏移，而是扫描 4096 对齐的 magic —— 厂商镜像的
  预留区大小并不统一（上游代码里用的是 4096*3，实测不是所有机器都这样）。
* 校验和只产生告警，不中断解析 —— 部分厂商镜像的 checksum 本身就不对，
  直接抛错会导致整片功能不可用。
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import InvalidImage

GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030
GEOMETRY_SIZE = 4096
SECTOR_SIZE = 512
NAME_LEN = 36

TARGET_LINEAR = 0
TARGET_ZERO = 1

ATTR_READONLY = 1 << 0
ATTR_SLOT_SUFFIXED = 1 << 1
ATTR_UPDATED = 1 << 2
ATTR_DISABLED = 1 << 3

TABLE_NAMES = ("partitions", "extents", "groups", "block_devices")

# 扫描上限：正常 super 的元数据都在前 8MB 内
SCAN_LIMIT = 8 * 1024 * 1024


@dataclass(frozen=True)
class Extent:
    num_sectors: int
    target_type: int
    target_data: int
    target_source: int

    @property
    def is_linear(self) -> bool:
        return self.target_type == TARGET_LINEAR

    @property
    def is_zero(self) -> bool:
        return self.target_type == TARGET_ZERO

    @property
    def byte_offset(self) -> int:
        """在 super 内的字节偏移（target_data 以逻辑扇区计）。"""
        return self.target_data * SECTOR_SIZE

    def to_dict(self) -> dict:
        return {
            "num_sectors": self.num_sectors,
            "target_type": "linear" if self.is_linear else ("zero" if self.is_zero else str(self.target_type)),
            "target_data": self.target_data,
            "target_source": self.target_source,
            "byte_offset": self.byte_offset,
        }


@dataclass
class Partition:
    name: str
    attributes: int
    first_extent_index: int
    num_extents: int
    group_index: int
    extents: list[Extent] = field(default_factory=list)

    @property
    def size_bytes(self) -> int:
        return sum(e.num_sectors for e in self.extents) * SECTOR_SIZE

    @property
    def readonly(self) -> bool:
        return bool(self.attributes & ATTR_READONLY)

    @property
    def slot_suffixed(self) -> bool:
        return bool(self.attributes & ATTR_SLOT_SUFFIXED)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "size_human": human_size(self.size_bytes),
            "attributes": self.attributes,
            "group_index": self.group_index,
            "extent_count": len(self.extents),
            "extents": [e.to_dict() for e in self.extents],
        }


@dataclass
class Group:
    name: str
    flags: int
    maximum_size: int

    def to_dict(self) -> dict:
        return {"name": self.name, "flags": self.flags, "maximum_size": self.maximum_size}


@dataclass
class BlockDevice:
    first_logical_sector: int
    alignment: int
    alignment_offset: int
    size: int
    partition_name: str
    flags: int

    def to_dict(self) -> dict:
        return {
            "partition_name": self.partition_name,
            "size": self.size,
            "first_logical_sector": self.first_logical_sector,
            "alignment": self.alignment,
            "flags": self.flags,
        }


@dataclass
class Geometry:
    metadata_max_size: int
    metadata_slot_count: int
    logical_block_size: int
    offset: int

    def to_dict(self) -> dict:
        return {
            "offset": self.offset,
            "metadata_max_size": self.metadata_max_size,
            "metadata_slot_count": self.metadata_slot_count,
            "logical_block_size": self.logical_block_size,
        }


@dataclass
class Header:
    major: int
    minor: int
    header_size: int
    tables_size: int
    flags: int
    offset: int
    table_descriptors: list[tuple[int, int, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "offset": self.offset,
            "version": f"{self.major}.{self.minor}",
            "header_size": self.header_size,
            "tables_size": self.tables_size,
            "flags": self.flags,
        }


@dataclass
class Metadata:
    geometry: Geometry
    header: Header
    partitions: list[Partition] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    block_devices: list[BlockDevice] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "primary"

    def find(self, name: str) -> Partition | None:
        for p in self.partitions:
            if p.name == name:
                return p
        return None

    @property
    def logical_size(self) -> int:
        return sum(p.size_bytes for p in self.partitions)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "geometry": self.geometry.to_dict(),
            "header": self.header.to_dict(),
            "warnings": self.warnings,
            "partition_count": len(self.partitions),
            "logical_size": self.logical_size,
            "groups": [g.to_dict() for g in self.groups],
            "block_devices": [b.to_dict() for b in self.block_devices],
            "partitions": [p.to_dict() for p in self.partitions],
        }


def human_size(n: int) -> str:
    val = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if val < 1024 or unit == "TiB":
            return f"{val:.1f}{unit}" if unit != "B" else f"{int(val)}B"
        val /= 1024
    return f"{n}B"


# ---- 定位 ---------------------------------------------------------
def _u32(blob: bytes, off: int) -> int:
    return struct.unpack_from("<I", blob, off)[0]


def find_geometry(blob: bytes) -> Geometry:
    """扫描 4096 对齐处找 geometry magic。"""
    limit = min(len(blob), SCAN_LIMIT)
    for off in range(0, limit - GEOMETRY_SIZE, GEOMETRY_SIZE):
        if _u32(blob, off) != GEOMETRY_MAGIC:
            continue
        struct_size = _u32(blob, off + 4)
        if struct_size != 52:
            continue
        return Geometry(
            metadata_max_size=_u32(blob, off + 40),
            metadata_slot_count=_u32(blob, off + 44),
            logical_block_size=_u32(blob, off + 48),
            offset=off,
        )
    raise InvalidImage("未找到 LP geometry（magic 0x616C4467）")


def find_header(blob: bytes, *, after: int = 0) -> int:
    limit = min(len(blob), SCAN_LIMIT)
    for off in range(after, limit - 4, GEOMETRY_SIZE):
        if _u32(blob, off) == HEADER_MAGIC:
            return off
    raise InvalidImage("未找到 LP metadata header（magic 0x414C5030）")


# ---- 校验 ---------------------------------------------------------
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_geometry(blob: bytes, geom: Geometry, warnings: list[str]) -> None:
    raw = bytearray(blob[geom.offset : geom.offset + 52])
    stored = bytes(raw[8:40])
    raw[8:40] = b"\x00" * 32
    if hashlib.sha256(bytes(raw)).digest() != stored:
        warnings.append("geometry checksum 不匹配")


def _check_header(blob: bytes, hdr: Header, warnings: list[str]) -> None:
    raw = bytearray(blob[hdr.offset : hdr.offset + hdr.header_size])
    if len(raw) != hdr.header_size:
        warnings.append("header 数据不完整")
        return
    stored = bytes(raw[12:44])
    raw[12:44] = b"\x00" * 32
    if hashlib.sha256(bytes(raw)).digest() != stored:
        warnings.append("header checksum 不匹配")

    tables = blob[hdr.offset + hdr.header_size : hdr.offset + hdr.header_size + hdr.tables_size]
    stored_tables = blob[hdr.offset + 48 : hdr.offset + 80]
    if len(tables) != hdr.tables_size:
        warnings.append("tables 数据不完整")
    elif hashlib.sha256(tables).digest() != stored_tables:
        warnings.append("tables checksum 不匹配")


# ---- 解析 ---------------------------------------------------------
def _parse_name(raw: bytes) -> str:
    return raw.split(b"\x00")[0].decode("ascii", "replace").strip()


def parse(blob: bytes) -> Metadata:
    geom = find_geometry(blob)
    warnings: list[str] = []
    _check_geometry(blob, geom, warnings)

    hdr_off = find_header(blob, after=geom.offset + GEOMETRY_SIZE)
    major, minor = struct.unpack_from("<HH", blob, hdr_off + 4)
    header_size, tables_size = struct.unpack_from("<II", blob, hdr_off + 8)[0], _u32(blob, hdr_off + 44)
    flags = _u32(blob, hdr_off + 128) if header_size >= 132 else 0

    descs = [struct.unpack_from("<III", blob, hdr_off + 80 + i * 12) for i in range(4)]
    hdr = Header(
        major=major, minor=minor, header_size=header_size, tables_size=tables_size,
        flags=flags, offset=hdr_off, table_descriptors=[tuple(d) for d in descs],
    )
    _check_header(blob, hdr, warnings)

    base = hdr_off + header_size

    def table(idx: int) -> tuple[int, int, int]:
        off, num, size = descs[idx]
        return base + off, num, size

    # extents
    ext_off, ext_num, ext_size = table(1)
    extents: list[Extent] = []
    for i in range(ext_num):
        o = ext_off + i * ext_size
        if o + 24 > len(blob):
            warnings.append("extents 表被截断")
            break
        num_sectors = struct.unpack_from("<Q", blob, o)[0]
        target_type = _u32(blob, o + 8)
        target_data = struct.unpack_from("<Q", blob, o + 12)[0]
        target_source = _u32(blob, o + 20)
        extents.append(Extent(num_sectors, target_type, target_data, target_source))

    # partitions
    p_off, p_num, p_size = table(0)
    partitions: list[Partition] = []
    for i in range(p_num):
        o = p_off + i * p_size
        if o + 52 > len(blob):
            warnings.append("partitions 表被截断")
            break
        name = _parse_name(blob[o : o + NAME_LEN])
        attributes, first_extent, num_extents, group_index = struct.unpack_from("<IIII", blob, o + 36)
        p = Partition(name, attributes, first_extent, num_extents, group_index)
        for idx in range(first_extent, min(first_extent + num_extents, len(extents))):
            p.extents.append(extents[idx])
        partitions.append(p)

    # groups
    g_off, g_num, g_size = table(2)
    groups: list[Group] = []
    for i in range(g_num):
        o = g_off + i * g_size
        if o + 48 > len(blob):
            break
        name = _parse_name(blob[o : o + NAME_LEN])
        gflags = _u32(blob, o + 36)
        max_size = struct.unpack_from("<Q", blob, o + 40)[0]
        groups.append(Group(name, gflags, max_size))

    # block devices
    b_off, b_num, b_size = table(3)
    devices: list[BlockDevice] = []
    for i in range(b_num):
        o = b_off + i * b_size
        if o + 64 > len(blob):
            break
        first_sector = struct.unpack_from("<Q", blob, o)[0]
        alignment, alignment_offset = struct.unpack_from("<II", blob, o + 8)
        size = struct.unpack_from("<Q", blob, o + 16)[0]
        part_name = _parse_name(blob[o + 24 : o + 24 + NAME_LEN])
        bflags = _u32(blob, o + 60)
        devices.append(BlockDevice(first_sector, alignment, alignment_offset, size, part_name, bflags))

    return Metadata(geom, hdr, partitions, groups, devices, warnings)


def read_path(path: str | Path) -> Metadata:
    p = Path(path)
    if not p.is_file():
        raise InvalidImage(f"文件不存在：{p}")
    with p.open("rb") as f:
        blob = f.read(SCAN_LIMIT)
    return parse(blob)


def extract_partition(
    meta: Metadata, partition: Partition, out: str | Path, *, src: str | Path
) -> dict:
    """把 super 里的某个逻辑分区按 extent 切出来（linear 直接拷，zero 补零）。"""
    bad = [e for e in partition.extents if not (e.is_linear or e.is_zero)]
    if bad:
        raise InvalidImage(f"{partition.name} 含有不支持的 extent 类型（target_type={bad[0].target_type}）")

    written = 0
    try:
        with open(src, "rb") as fh, open(out, "wb") as dst:
            for e in partition.extents:
                size = e.num_sectors * SECTOR_SIZE
                if e.is_zero:
                    dst.write(b"\x00" * size)
                else:
                    fh.seek(e.byte_offset)
                    remaining = size
                    while remaining > 0:
                        chunk = fh.read(min(remaining, 4 << 20))
                        if not chunk:
                            raise InvalidImage(
                                f"super 数据被截断：{partition.name} 需要读到 {e.byte_offset + size}，文件不够长"
                            )
                        dst.write(chunk)
                        remaining -= len(chunk)
                written += size
    except InvalidImage:
        Path(out).unlink(missing_ok=True)  # 别留下半个镜像骗人
        raise
    return {"partition": partition.name, "bytes": written, "output": str(out)}
