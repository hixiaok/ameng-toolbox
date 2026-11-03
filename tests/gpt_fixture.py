"""测试用的 GPT 镜像构造器：造一张真正合法（CRC 正确）的分区表。"""

from __future__ import annotations

import struct
import uuid
import zlib

TYPE_BASIC = uuid.UUID("ebd0a0a2-b9e5-4433-87c0-68b6b72699c7")


def entry(name: str, first_lba: int, last_lba: int, type_guid: uuid.UUID = TYPE_BASIC) -> bytes:
    e = bytearray(128)
    e[0:16] = type_guid.bytes_le
    e[16:32] = uuid.uuid5(uuid.NAMESPACE_DNS, name).bytes_le
    struct.pack_into("<QQQ", e, 32, first_lba, last_lba, 0)
    raw = name.encode("utf-16-le")[:72]
    e[56 : 56 + len(raw)] = raw
    return bytes(e)


def header(
    *,
    my_lba: int,
    alt_lba: int,
    first_usable: int,
    last_usable: int,
    entry_lba: int,
    num_entries: int,
    entry_size: int,
    entries_crc: int,
    disk_guid: uuid.UUID,
) -> bytes:
    h = bytearray(92)
    h[0:8] = b"EFI PART"
    struct.pack_into("<IIII", h, 8, 0x00010000, 92, 0, 0)
    struct.pack_into("<QQ", h, 24, my_lba, alt_lba)
    struct.pack_into("<QQ", h, 40, first_usable, last_usable)
    h[56:72] = disk_guid.bytes_le
    struct.pack_into("<QIII", h, 72, entry_lba, num_entries, entry_size, entries_crc)
    struct.pack_into("<I", h, 16, zlib.crc32(bytes(h)) & 0xFFFFFFFF)
    return bytes(h)


def build(names: list[str], *, sector: int = 512, total_sectors: int = 4096) -> bytes:
    """造一张 512B/4KB 扇区的完整 GPT 磁盘镜像（含备份表）。"""
    num_entries = 128
    entry_size = 128
    entries_len = num_entries * entry_size
    entries_sectors = entries_len // sector

    disk_guid = uuid.uuid5(uuid.NAMESPACE_DNS, "iris-test-disk")
    first_usable = 2 + entries_sectors
    last_usable = total_sectors - entries_sectors - 2

    parts = []
    cursor = first_usable
    for i, name in enumerate(names):
        span = 64
        parts.append(entry(name, cursor, cursor + span - 1))
        cursor += span
    blob = b"".join(parts).ljust(entries_len, b"\x00")
    entries_crc = zlib.crc32(blob) & 0xFFFFFFFF

    img = bytearray(sector * total_sectors)
    # 保护性 MBR
    img[510:512] = b"\x55\xaa"
    # 主表
    img[sector : sector + 92] = header(
        my_lba=1, alt_lba=total_sectors - 1, first_usable=first_usable, last_usable=last_usable,
        entry_lba=2, num_entries=num_entries, entry_size=entry_size, entries_crc=entries_crc,
        disk_guid=disk_guid,
    )
    img[2 * sector : 2 * sector + entries_len] = blob

    # 备份表：条目在最后 header 之前，header 在最后一个扇区
    backup_entries_lba = total_sectors - 1 - entries_sectors
    img[backup_entries_lba * sector : backup_entries_lba * sector + entries_len] = blob
    img[(total_sectors - 1) * sector : (total_sectors - 1) * sector + 92] = header(
        my_lba=total_sectors - 1, alt_lba=2, first_usable=first_usable, last_usable=last_usable,
        entry_lba=backup_entries_lba, num_entries=num_entries, entry_size=entry_size,
        entries_crc=entries_crc, disk_guid=disk_guid,
    )
    return bytes(img)
