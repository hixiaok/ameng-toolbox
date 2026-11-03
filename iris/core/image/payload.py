"""OTA payload.bin 解析与提取。

格式（AOSP update_engine）：

    "CrAU" | version:u64 | manifest_size:u64 | [sig_size:u32] | manifest(protobuf) | sig | data

manifest 是 DeltaArchiveManifest（proto2），字段号以
上游 `Protos/update_metadata.proto` 为准：

    DeltaArchiveManifest: block_size=3, partitions=13
    PartitionUpdate:      partition_name=1, operations=8
    InstallOperation:     type=1, data_offset=2, data_length=3,
                          dst_extents=6, data_sha256_hash=8
    Extent:               start_block=1, num_blocks=2

`data_offset` 是相对"数据区起点"（header + manifest + sig 之后）的偏移。
不依赖 protobuf 库：manifest 只用 varint + length-delimited 两种 wire type，
手写解析足够，而且能保证零第三方依赖。
"""

from __future__ import annotations

import bz2
import hashlib
import lzma
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import InvalidImage

MAGIC = b"CrAU"
HEADER_BASE = 20  # magic(4) + version(8) + manifest_size(8)

TYPE_REPLACE = 0
TYPE_REPLACE_BZ = 1
TYPE_ZERO = 6
TYPE_REPLACE_XZ = 8
TYPE_ZSTD = 14

TYPE_NAMES = {
    0: "REPLACE", 1: "REPLACE_BZ", 2: "MOVE", 3: "BSDIFF", 4: "SOURCE_COPY",
    5: "SOURCE_BSDIFF", 6: "ZERO", 7: "DISCARD", 8: "REPLACE_XZ", 9: "PUFFDIFF",
    10: "BROTLI_BSDIFF", 11: "ZUCCHINI", 12: "LZ4DIFF_BSDIFF", 13: "LZ4DIFF_PUFFDIFF",
    14: "ZSTD",
}


@dataclass
class Extent:
    start_block: int
    num_blocks: int


@dataclass
class Op:
    type: int
    data_offset: int
    data_length: int
    dst_extents: list[Extent] = field(default_factory=list)
    data_sha256: bytes = b""

    @property
    def type_name(self) -> str:
        return TYPE_NAMES.get(self.type, f"UNKNOWN({self.type})")

    @property
    def is_extractable(self) -> bool:
        return self.type in (TYPE_REPLACE, TYPE_REPLACE_BZ, TYPE_REPLACE_XZ, TYPE_ZERO)


@dataclass
class Partition:
    name: str
    operations: list[Op] = field(default_factory=list)

    @property
    def blocks(self) -> int:
        return sum(e.num_blocks for op in self.operations for e in op.dst_extents)

    @property
    def size_bytes(self) -> int:
        return self.blocks * 4096  # 真实块大小由 Payload.block_size 决定，见 Payload.size_of

    def to_dict(self, block_size: int = 4096) -> dict:
        return {
            "name": self.name,
            "size_bytes": self.blocks * block_size,
            "operation_count": len(self.operations),
            "operations": sorted({op.type_name for op in self.operations}),
            "extractable": all(op.is_extractable for op in self.operations),
        }


@dataclass
class Payload:
    version: int
    block_size: int
    partitions: list[Partition]
    manifest_size: int
    sig_size: int

    @property
    def data_start(self) -> int:
        return HEADER_BASE + (4 if self.version >= 2 else 0) + self.manifest_size + self.sig_size

    def find(self, name: str) -> Partition | None:
        for p in self.partitions:
            if p.name == name:
                return p
        return None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "block_size": self.block_size,
            "data_start": self.data_start,
            "partition_count": len(self.partitions),
            "partitions": [p.to_dict(self.block_size) for p in self.partitions],
        }


# ---- 极简 protobuf -------------------------------------------------
def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        if pos >= len(buf):
            raise InvalidImage("protobuf varint 越界")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise InvalidImage("protobuf varint 过长")


def _fields(buf: bytes):
    pos = 0
    while pos < len(buf):
        key, pos = _varint(buf, pos)
        num, wire = key >> 3, key & 7
        if wire == 0:
            val, pos = _varint(buf, pos)
        elif wire == 2:
            length, pos = _varint(buf, pos)
            if pos + length > len(buf):
                raise InvalidImage("protobuf 长度越界")
            val = buf[pos : pos + length]
            pos += length
        elif wire == 5:
            val = buf[pos : pos + 4]
            pos += 4
        elif wire == 1:
            val = buf[pos : pos + 8]
            pos += 8
        else:
            raise InvalidImage(f"不支持的 protobuf wire type：{wire}")
        yield num, wire, val


def _parse_extent(buf: bytes) -> Extent:
    start = num = 0
    for f, w, v in _fields(buf):
        if w != 0:
            continue
        if f == 1:
            start = v
        elif f == 2:
            num = v
    return Extent(start, num)


def _parse_op(buf: bytes) -> Op:
    op = Op(type=0, data_offset=0, data_length=0)
    for f, w, v in _fields(buf):
        if f == 1 and w == 0:
            op.type = v
        elif f == 2 and w == 0:
            op.data_offset = v
        elif f == 3 and w == 0:
            op.data_length = v
        elif f == 6 and w == 2:
            op.dst_extents.append(_parse_extent(v))
        elif f == 8 and w == 2:
            op.data_sha256 = v
    return op


def _parse_partition(buf: bytes) -> Partition:
    part = Partition(name="")
    for f, w, v in _fields(buf):
        if f == 1 and w == 2:
            part.name = v.decode("utf-8", "replace")
        elif f == 8 and w == 2:
            part.operations.append(_parse_op(v))
    return part


def _parse_manifest(buf: bytes) -> tuple[int, list[Partition]]:
    block_size = 4096
    parts: list[Partition] = []
    for f, w, v in _fields(buf):
        if f == 3 and w == 0:
            block_size = v
        elif f == 13 and w == 2:
            parts.append(_parse_partition(v))
    return block_size, parts


# ---- 读取 ----------------------------------------------------------
def is_payload(head: bytes) -> bool:
    return head[:4] == MAGIC


def parse(path: str | Path) -> Payload:
    p = Path(path)
    if not p.is_file():
        raise InvalidImage(f"文件不存在：{p}")

    with p.open("rb") as f:
        head = f.read(HEADER_BASE + 4)
        if len(head) < HEADER_BASE:
            raise InvalidImage("payload 头部不完整")
        if head[:4] != MAGIC:
            raise InvalidImage("不是 payload.bin（magic 'CrAU' 不匹配）")

        version = int.from_bytes(head[4:12], "little")
        manifest_size = int.from_bytes(head[12:20], "little")
        sig_size = 0
        if version >= 2:
            sig_size = int.from_bytes(head[20:24], "little")

        f.seek(HEADER_BASE + (4 if version >= 2 else 0))
        manifest = f.read(manifest_size)
        if len(manifest) != manifest_size:
            raise InvalidImage("manifest 数据不完整，文件可能被截断")

    block_size, partitions = _parse_manifest(manifest)
    return Payload(version, block_size, partitions, manifest_size, sig_size)


def _decompress(op: Op, data: bytes) -> bytes:
    if op.type == TYPE_REPLACE:
        return data
    if op.type == TYPE_REPLACE_BZ:
        return bz2.decompress(data)
    if op.type == TYPE_REPLACE_XZ:
        return lzma.decompress(data)
    raise InvalidImage(f"不支持的压缩类型：{op.type_name}")


def _write_zeros(fh, count: int) -> None:
    chunk = b"\x00" * (1024 * 1024)
    while count > 0:
        n = min(count, len(chunk))
        fh.write(chunk[:n])
        count -= n


def extract(payload: Payload, partition: Partition, out: str | Path, *, src: str | Path) -> dict:
    """把某个分区还原成原始镜像。"""
    unsupported = [op.type_name for op in partition.operations if not op.is_extractable]
    if unsupported:
        raise InvalidImage(
            f"{partition.name} 含有增量操作（{', '.join(sorted(set(unsupported)))}），"
            "只能从全量包提取，不能从增量包提取"
        )

    written = 0
    with open(src, "rb") as fh, open(out, "wb") as dst:
        for op in partition.operations:
            span = sum(e.num_blocks for e in op.dst_extents) * payload.block_size

            if op.type == TYPE_ZERO:
                _write_zeros(dst, span)
                written += span
                continue

            fh.seek(payload.data_start + op.data_offset)
            raw = fh.read(op.data_length)
            if len(raw) != op.data_length:
                raise InvalidImage("payload 数据被截断")
            if op.data_sha256 and hashlib.sha256(raw).digest() != op.data_sha256:
                raise InvalidImage(f"{partition.name} 数据校验和不匹配")

            data = _decompress(op, raw)
            if len(data) != span:
                raise InvalidImage(
                    f"{partition.name} 解压后大小不符：期望 {span}，实际 {len(data)}"
                )

            cursor = 0
            for ext in op.dst_extents:
                size = ext.num_blocks * payload.block_size
                dst.seek(ext.start_block * payload.block_size)
                dst.write(data[cursor : cursor + size])
                cursor += size
                written += size

    return {"partition": partition.name, "bytes": written, "output": str(out)}
