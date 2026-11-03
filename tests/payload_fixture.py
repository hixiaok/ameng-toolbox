"""构造合法的 payload.bin 测试夹具（手写 protobuf 编码）。"""

from __future__ import annotations

import bz2
import hashlib
import struct

BLOCK = 4096


def _v(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _v((field << 3) | wire)


def _var(field: int, value: int) -> bytes:
    return _tag(field, 0) + _v(value)


def _bytes(field: int, payload: bytes) -> bytes:
    return _tag(field, 2) + _v(len(payload)) + payload


def _extent(start: int, blocks: int) -> bytes:
    return _var(1, start) + _var(2, blocks)


def build_payload(parts: dict[str, bytes], *, version: int = 2, compress: str = "none") -> bytes:
    """parts: {分区名: 原始数据}，数据长度必须是 4096 的整数倍。"""
    partition_msgs: list[bytes] = []
    data = bytearray()
    offset = 0

    for name, raw in parts.items():
        assert len(raw) % BLOCK == 0, name
        blocks = len(raw) // BLOCK

        if compress == "bz2":
            blob = bz2.compress(raw)
            op_type = 1
        else:
            blob = raw
            op_type = 0

        op = bytearray()
        op += _var(1, op_type)
        op += _var(2, offset)
        op += _var(3, len(blob))
        op += _bytes(6, _extent(0, blocks))
        op += _bytes(8, hashlib.sha256(blob).digest())

        partition_msgs.append(_bytes(1, name.encode()) + _bytes(8, bytes(op)))
        data += blob
        offset += len(blob)

    manifest = _var(3, BLOCK) + b"".join(_bytes(13, m) for m in partition_msgs)

    head = b"CrAU" + struct.pack("<Q", version) + struct.pack("<Q", len(manifest))
    if version >= 2:
        head += struct.pack("<I", 0)
    return head + manifest + bytes(data)


def build_zero_payload(name: str = "empty", blocks: int = 2) -> bytes:
    op = _var(1, 6) + _bytes(6, _extent(0, blocks))
    part = _bytes(1, name.encode()) + _bytes(8, op)
    manifest = _var(3, BLOCK) + _bytes(13, part)
    head = b"CrAU" + struct.pack("<Q", 2) + struct.pack("<Q", len(manifest)) + struct.pack("<I", 0)
    return head + manifest
