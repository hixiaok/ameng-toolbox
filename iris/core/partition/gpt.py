"""GPT（GUID Partition Table）解析。

纯离线：只吃文件或内存字节，不碰设备。这样即使手上没有真机、没有 root，
也能用镜像夹具做完整单元测试——上游把这段逻辑焊在 900KB 的 MainWindow 里，
除了真机没法验证。

支持：512 / 4096 扇区自动识别、主/备 GPT 回退、CRC 校验、分区名（UTF-16LE）。
"""

from __future__ import annotations

import struct
import uuid
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import InvalidImage

GPT_SIGNATURE = b"EFI PART"
HEADER_SIZE_MIN = 92
SECTOR_SIZES = (512, 4096)
READ_WINDOW = 4 * 1024 * 1024


@dataclass(frozen=True)
class GptPartition:
    index: int
    type_guid: uuid.UUID
    unique_guid: uuid.UUID
    first_lba: int
    last_lba: int
    attributes: int
    name: str

    @property
    def sectors(self) -> int:
        return self.last_lba - self.first_lba + 1

    def byte_range(self, sector_size: int) -> tuple[int, int]:
        return self.first_lba * sector_size, (self.last_lba + 1) * sector_size

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "type": str(self.type_guid),
            "unique": str(self.unique_guid),
            "first_lba": self.first_lba,
            "last_lba": self.last_lba,
            "sectors": self.sectors,
            "attributes": self.attributes,
        }


@dataclass
class GptTable:
    sector_size: int
    disk_guid: uuid.UUID
    first_usable_lba: int
    last_usable_lba: int
    partitions: list[GptPartition] = field(default_factory=list)
    source: str = "primary"  # primary | backup
    crc_ok: bool = True

    def find(self, name: str) -> GptPartition | None:
        for p in self.partitions:
            if p.name == name:
                return p
        return None

    def names(self) -> list[str]:
        return [p.name for p in self.partitions]

    def to_dict(self) -> dict:
        return {
            "sector_size": self.sector_size,
            "disk_guid": str(self.disk_guid),
            "first_usable_lba": self.first_usable_lba,
            "last_usable_lba": self.last_usable_lba,
            "source": self.source,
            "crc_ok": self.crc_ok,
            "partition_count": len(self.partitions),
            "partitions": [p.to_dict() for p in self.partitions],
        }


def _guid(raw: bytes) -> uuid.UUID:
    """GPT 的 GUID 前三个字段是小端序；uuid.UUID(bytes_le=...) 正好对应。"""
    if len(raw) != 16:
        raise InvalidImage("GUID 长度不是 16 字节")
    return uuid.UUID(bytes_le=raw)


def _decode_name(raw: bytes) -> str:
    return raw.decode("utf-16-le", "replace").split("\x00")[0].strip()


def _parse_header(
    blob: bytes, *, header_off: int, blob_base: int, file_size: int, sector_size: int, source: str
) -> GptTable:
    """解析一张 GPT 表。

    `header_off` 是表头在 blob 内的相对偏移；`blob_base` 是 blob[0] 的绝对偏移。
    """
    offset = header_off
    if offset < 0 or offset + HEADER_SIZE_MIN > len(blob):
        raise InvalidImage(f"{source} GPT 头不在读取窗口内")

    header = blob[offset : offset + HEADER_SIZE_MIN]
    if header[:8] != GPT_SIGNATURE:
        raise InvalidImage(f"{source} GPT 签名不匹配")

    _rev, hdr_size, crc, _res, _my_lba, _alt_lba, first_usable, last_usable = struct.unpack_from(
        "<IIIIQQQQ", header, 8
    )
    disk_guid = _guid(header[56:72])
    entry_lba, num_entries, entry_size, entries_crc = struct.unpack_from("<QIII", header, 72)

    if hdr_size < HEADER_SIZE_MIN or hdr_size > sector_size:
        raise InvalidImage(f"GPT 头长度异常：{hdr_size}")
    if not 0 < num_entries <= 1024:
        raise InvalidImage(f"分区条目数异常：{num_entries}")
    if entry_size < 128 or entry_size % 8:
        raise InvalidImage(f"分区条目大小异常：{entry_size}")

    # 头 CRC：校验和字段自身置零后计算
    head_bytes = bytearray(blob[offset : offset + hdr_size])
    if len(head_bytes) != hdr_size:
        raise InvalidImage("GPT 头数据不完整")
    head_bytes[16:20] = b"\x00\x00\x00\x00"
    header_crc_ok = (zlib.crc32(bytes(head_bytes)) & 0xFFFFFFFF) == crc

    entries_abs = entry_lba * sector_size
    entries_len = num_entries * entry_size
    if entries_abs + entries_len > file_size:
        raise InvalidImage("分区条目区超出文件范围")
    rel = entries_abs - blob_base
    if rel < 0 or rel + entries_len > len(blob):
        raise InvalidImage("分区条目区不在读取窗口内")
    entries = blob[rel : rel + entries_len]

    if (zlib.crc32(entries) & 0xFFFFFFFF) != entries_crc:
        raise InvalidImage("分区条目 CRC 校验失败")

    parts: list[GptPartition] = []
    for i in range(num_entries):
        chunk = entries[i * entry_size : (i + 1) * entry_size]
        type_guid = _guid(chunk[0:16])
        if type_guid.int == 0:
            continue
        first_lba, last_lba, attrs = struct.unpack_from("<QQQ", chunk, 32)
        parts.append(
            GptPartition(
                index=i + 1,
                type_guid=type_guid,
                unique_guid=_guid(chunk[16:32]),
                first_lba=first_lba,
                last_lba=last_lba,
                attributes=attrs,
                name=_decode_name(chunk[56:128]),
            )
        )

    return GptTable(
        sector_size=sector_size,
        disk_guid=disk_guid,
        first_usable_lba=first_usable,
        last_usable_lba=last_usable,
        partitions=parts,
        source=source,
        crc_ok=header_crc_ok,
    )


def parse(blob: bytes, *, file_size: int | None = None, base: int = 0) -> GptTable:
    """解析 GPT。`base` 是 blob[0] 在文件中的绝对偏移（读尾部窗口时用）。"""
    size = file_size if file_size is not None else base + len(blob)
    errors: list[str] = []

    for sector in SECTOR_SIZES:
        # 主表：头 CRC 对了才算数
        try:
            table = _parse_header(
                blob, header_off=sector - base, blob_base=base, file_size=size,
                sector_size=sector, source="primary",
            )
        except InvalidImage as exc:
            errors.append(f"{sector}B 主表: {exc}")
            table = None
        if table is not None and table.crc_ok:
            return table
        if table is not None:
            errors.append(f"{sector}B 主表 CRC 不符")

        # 备份表：位于最后一个扇区，条目区紧随其后
        backup_off = (size // sector - 1) * sector
        try:
            back = _parse_header(
                blob, header_off=backup_off - base, blob_base=base, file_size=size,
                sector_size=sector, source="backup",
            )
            back.crc_ok = False
            return back
        except InvalidImage as exc:
            errors.append(f"{sector}B 备份表: {exc}")

    raise InvalidImage("无法解析 GPT：" + "；".join(errors))


def read_path(path: str | Path) -> GptTable:
    """从镜像文件解析 GPT：先试头部，失败再读尾部找备份表。"""
    p = Path(path)
    if not p.is_file():
        raise InvalidImage(f"文件不存在：{p}")
    size = p.stat().st_size
    with p.open("rb") as f:
        head = f.read(min(size, READ_WINDOW))
        try:
            return parse(head, file_size=size)
        except InvalidImage as first_error:
            tail_start = max(0, size - READ_WINDOW)
            f.seek(tail_start)
            tail = f.read()
            try:
                return parse(tail, file_size=size, base=tail_start)
            except InvalidImage:
                raise first_error from None
