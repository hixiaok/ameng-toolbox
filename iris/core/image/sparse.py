"""Android sparse image（.img 稀疏格式）解析与展开。

格式：28 字节头 + 若干 chunk。
chunk 类型：RAW(0xCAC1) / FILL(0xCAC2) / DONT_CARE(0xCAC3) / CRC32(0xCAC4)。

很多厂商导出的分区镜像都是 sparse 的，直接当 raw 读会得到错误内容 ——
上游在若干处直接按 raw 处理，靠"读出来不对再试"兜底。这里显式识别。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from ..errors import InvalidImage

MAGIC = 0xED26FF3A
HEADER_SIZE = 28
CHUNK_HEADER_SIZE = 12

CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3
CHUNK_CRC32 = 0xCAC4

CHUNK_NAMES = {
    CHUNK_RAW: "raw",
    CHUNK_FILL: "fill",
    CHUNK_DONT_CARE: "dont_care",
    CHUNK_CRC32: "crc32",
}


@dataclass
class Chunk:
    chunk_type: int
    output_blocks: int
    total_size: int
    data: bytes = b""
    crc: int | None = None

    @property
    def kind(self) -> str:
        return CHUNK_NAMES.get(self.chunk_type, f"0x{self.chunk_type:X}")


@dataclass
class SparseInfo:
    major: int
    minor: int
    block_size: int
    total_blocks: int
    total_chunks: int
    image_checksum: int

    @property
    def expanded_size(self) -> int:
        return self.total_blocks * self.block_size


def is_sparse(blob: bytes) -> bool:
    return len(blob) >= 4 and struct.unpack_from("<I", blob, 0)[0] == MAGIC


def parse_header(blob: bytes) -> SparseInfo:
    if len(blob) < HEADER_SIZE:
        raise InvalidImage("sparse 头不足 28 字节")
    magic, major, minor, file_hdr_sz, chunk_hdr_sz, block_size, total_blocks, total_chunks, checksum = (
        struct.unpack_from("<IHHHHIIII", blob, 0)
    )
    if magic != MAGIC:
        raise InvalidImage("不是 sparse 镜像（magic 0xED26FF3A 不匹配）")
    if file_hdr_sz != HEADER_SIZE:
        raise InvalidImage(f"不支持的 sparse 文件头长度：{file_hdr_sz}")
    if chunk_hdr_sz != CHUNK_HEADER_SIZE:
        raise InvalidImage(f"不支持的 sparse chunk 头长度：{chunk_hdr_sz}")
    return SparseInfo(major, minor, block_size, total_blocks, total_chunks, checksum)


def iter_chunks(blob: bytes, info: SparseInfo | None = None) -> Iterator[Chunk]:
    info = info or parse_header(blob)
    pos = HEADER_SIZE
    for _ in range(info.total_chunks):
        if pos + CHUNK_HEADER_SIZE > len(blob):
            raise InvalidImage("chunk 头越界，文件被截断")
        ctype, _reserved, out_blocks, total_size = struct.unpack_from("<HHII", blob, pos)
        pos += CHUNK_HEADER_SIZE
        payload_len = total_size - CHUNK_HEADER_SIZE
        if payload_len < 0 or pos + payload_len > len(blob):
            raise InvalidImage("chunk 数据越界，文件被截断")
        payload = blob[pos : pos + payload_len]
        pos += payload_len

        if ctype == CHUNK_RAW:
            yield Chunk(ctype, out_blocks, total_size, data=payload)
        elif ctype == CHUNK_FILL:
            if len(payload) < 4:
                raise InvalidImage("fill chunk 缺少填充值")
            yield Chunk(ctype, out_blocks, total_size, data=payload[:4])
        elif ctype == CHUNK_DONT_CARE:
            yield Chunk(ctype, out_blocks, total_size, data=b"\x00" * 4)
        elif ctype == CHUNK_CRC32:
            yield Chunk(ctype, out_blocks, total_size, crc=struct.unpack_from("<I", payload or b"\x00" * 4)[0])
        else:
            # 未知 chunk 类型：跳过载荷，保持前后可解析
            yield Chunk(ctype, out_blocks, total_size)


def unpack(src: str | Path, dst: str | Path) -> dict:
    """把 sparse 展开成 raw。流式写，不把整镜像读进内存。"""
    src_p, dst_p = Path(src), Path(dst)
    if not src_p.is_file():
        raise InvalidImage(f"文件不存在：{src_p}")

    with src_p.open("rb") as f:
        head = f.read(HEADER_SIZE)
        info = parse_header(head)
        written = 0
        chunks = 0
        with dst_p.open("wb") as out:
            for i in range(info.total_chunks):
                raw = f.read(CHUNK_HEADER_SIZE)
                if len(raw) < CHUNK_HEADER_SIZE:
                    raise InvalidImage("chunk 头越界，文件被截断")
                ctype, _res, out_blocks, total_size = struct.unpack("<HHII", raw)
                payload_len = total_size - CHUNK_HEADER_SIZE
                if payload_len < 0:
                    raise InvalidImage("chunk 长度非法")
                payload = f.read(payload_len)
                if len(payload) < payload_len:
                    raise InvalidImage("chunk 数据越界，文件被截断")
                chunks += 1

                if ctype == CHUNK_RAW:
                    out.write(payload)
                elif ctype == CHUNK_FILL:
                    # fill 值是一个 4 字节模式，要铺满 out_blocks 个 block
                    pattern = payload[:4] * (info.block_size // 4)
                    out.write(pattern * out_blocks)
                elif ctype == CHUNK_DONT_CARE:
                    out.write(b"\x00" * (out_blocks * info.block_size))
                elif ctype == CHUNK_CRC32:
                    continue
                else:
                    continue
                written += out_blocks * info.block_size

    return {
        "chunks": chunks,
        "expanded_bytes": written,
        "block_size": info.block_size,
        "total_blocks": info.total_blocks,
    }


def describe(blob: bytes) -> dict:
    info = parse_header(blob)
    chunks = list(iter_chunks(blob, info))
    stats: dict[str, int] = {}
    for c in chunks:
        stats[c.kind] = stats.get(c.kind, 0) + 1
    return {
        "block_size": info.block_size,
        "total_blocks": info.total_blocks,
        "total_chunks": info.total_chunks,
        "expanded_size": info.expanded_size,
        "chunk_stats": stats,
        "version": f"{info.major}.{info.minor}",
    }


def describe_path(path: str | Path) -> dict:
    """只读 chunk 头做统计，不把几 GB 的镜像读进内存。"""
    p = Path(path)
    if not p.is_file():
        raise InvalidImage(f"文件不存在：{p}")
    size = p.stat().st_size
    stats: dict[str, int] = {}
    with p.open("rb") as f:
        info = parse_header(f.read(HEADER_SIZE))
        for _ in range(info.total_chunks):
            raw = f.read(CHUNK_HEADER_SIZE)
            if len(raw) < CHUNK_HEADER_SIZE:
                raise InvalidImage("chunk 头越界，文件被截断")
            ctype, _res, _blocks, total_size = struct.unpack("<HHII", raw)
            payload_len = total_size - CHUNK_HEADER_SIZE
            if payload_len < 0 or f.tell() + payload_len > size:
                raise InvalidImage("chunk 数据越界，文件被截断")
            f.seek(payload_len, 1)
            kind = CHUNK_NAMES.get(ctype, f"0x{ctype:X}")
            stats[kind] = stats.get(kind, 0) + 1
    return {
        "block_size": info.block_size,
        "total_blocks": info.total_blocks,
        "total_chunks": info.total_chunks,
        "expanded_size": info.expanded_size,
        "chunk_stats": stats,
        "version": f"{info.major}.{info.minor}",
    }
