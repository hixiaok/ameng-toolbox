"""造合法的 super / sparse 测试镜像。

和 GPT 夹具一样：校验和按 AOSP 规则算好，解析器如果写错了会当场暴露。
"""

from __future__ import annotations

import hashlib
import struct

GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030
NAME_LEN = 36


def _name(raw: str) -> bytes:
    b = raw.encode("ascii")
    assert len(b) <= NAME_LEN
    return b.ljust(NAME_LEN, b"\x00")


def build_super(
    partitions: list[dict],
    *,
    geometry_off: int = 4096,
    header_off: int = 8192,
    block_size: int = 4096,
    total_size: int = 1024 * 1024,
    groups: list[tuple[str, int]] | None = None,
    block_device: tuple[str, int, int] = ("super", 0, 1024 * 1024),
    corrupt_geometry_crc: bool = False,
) -> bytes:
    """partitions: [{"name": str, "extents": [(num_sectors, target_data), ...]}]"""
    groups = groups or [("default", 0)]
    blob = bytearray(total_size)

    # --- 表 ---
    p_tbl = bytearray()
    e_tbl = bytearray()
    extent_cursor = 0
    for part in partitions:
        exts = part.get("extents", [])
        p_tbl += (
            _name(part["name"])
            + struct.pack("<IIII", part.get("attributes", 1), extent_cursor, len(exts), part.get("group", 0))
        )
        for num_sectors, target_data in exts:
            e_tbl += struct.pack("<QIQI", num_sectors, 0, target_data, 0)
        extent_cursor += len(exts)

    g_tbl = bytearray()
    for name, max_size in groups:
        g_tbl += _name(name) + struct.pack("<IQ", 0, max_size)

    b_tbl = bytearray()
    bd_name, bd_first, bd_size = block_device
    b_tbl += struct.pack("<QIIQ", bd_first, 1024 * 1024, 0, bd_size) + _name(bd_name) + struct.pack("<I", 0)

    tables = bytes(p_tbl) + bytes(e_tbl) + bytes(g_tbl) + bytes(b_tbl)
    descs = (
        (0, len(partitions), 52),
        (len(p_tbl), extent_cursor, 24),
        (len(p_tbl) + len(e_tbl), len(groups), 48),
        (len(p_tbl) + len(e_tbl) + len(g_tbl), 1, 64),
    )

    # --- geometry ---
    geom = bytearray(52)
    struct.pack_into("<II", geom, 0, GEOMETRY_MAGIC, 52)
    geom[8:40] = b"\x00" * 32
    struct.pack_into("<III", geom, 40, 65536, 2, block_size)
    crc = hashlib.sha256(bytes(geom)).digest()
    if corrupt_geometry_crc:
        crc = bytes(32)
    geom[8:40] = crc
    blob[geometry_off : geometry_off + 52] = geom

    # --- header (v12, 256 字节) ---
    header = bytearray(256)
    struct.pack_into("<IHHI", header, 0, HEADER_MAGIC, 10, 2, 256)
    header[12:44] = b"\x00" * 32
    struct.pack_into("<I", header, 44, len(tables))
    struct.pack_into("<I", header, 128, 0)  # flags
    header[48:80] = hashlib.sha256(tables).digest()
    for i, (off, num, esize) in enumerate(descs):
        struct.pack_into("<III", header, 80 + i * 12, off, num, esize)
    header[12:44] = hashlib.sha256(bytes(header)).digest()

    tables_off = header_off + 256
    blob[header_off : header_off + 256] = header
    blob[tables_off : tables_off + len(tables)] = tables
    return bytes(blob)


def build_sparse(raw: bytes, *, block_size: int = 4096) -> bytes:
    """把 raw 数据打包成 sparse 镜像：raw 块 + fill 块 + dont_care 块 + raw 块。"""
    assert len(raw) % block_size == 0
    chunks: list[bytes] = []
    total_blocks = 0

    def raw_chunk(data: bytes) -> bytes:
        nonlocal total_blocks
        blocks = len(data) // block_size
        total_blocks += blocks
        return struct.pack("<HHII", 0xCAC1, 0, blocks, 12 + len(data)) + data

    def fill_chunk(value: bytes, blocks: int) -> bytes:
        nonlocal total_blocks
        total_blocks += blocks
        return struct.pack("<HHII", 0xCAC2, 0, blocks, 16) + value

    def skip_chunk(blocks: int) -> bytes:
        nonlocal total_blocks
        total_blocks += blocks
        return struct.pack("<HHII", 0xCAC3, 0, blocks, 12)

    half = len(raw) // 2
    chunks.append(raw_chunk(raw[:half]))
    chunks.append(fill_chunk(b"\xab\xcd\xef\x01", 2))
    chunks.append(skip_chunk(1))
    chunks.append(raw_chunk(raw[half:]))

    body = b"".join(chunks)
    header = struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, block_size, total_blocks, len(chunks), 0)
    return header + body


def expected_unpacked(raw: bytes, *, block_size: int = 4096) -> bytes:
    """build_sparse 会插入 fill / skip 块，这里给出展开后的期望内容。"""
    half = len(raw) // 2
    fill = (b"\xab\xcd\xef\x01" * (block_size // 4)) * 2
    return raw[:half] + fill + b"\x00" * block_size + raw[half:]
