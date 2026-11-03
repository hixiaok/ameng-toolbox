"""boot.img / vbmeta 测试夹具。"""

from __future__ import annotations

import struct

KERNEL = bytes((i * 3) % 256 for i in range(5000))
RAMDISK = bytes((i * 7) % 256 for i in range(3000))


def _align(n: int, page: int) -> int:
    return (n + page - 1) // page * page


def build_boot(*, version: int = 4) -> bytes:
    if version >= 3:
        header = bytearray(1584)
        header[0:8] = b"ANDROID!"
        struct.pack_into("<I", header, 8, len(KERNEL))
        struct.pack_into("<I", header, 12, len(RAMDISK))
        struct.pack_into("<I", header, 16, (16 << 25) | (0 << 18) | (0 << 11) | (6 << 4) | 1)  # 16.0.0 (2026-01)
        struct.pack_into("<I", header, 20, 1584)
        struct.pack_into("<I", header, 40, version)
        cmd = b"console=ttyMSM0 androidboot.hardware=qcom"
        header[44 : 44 + len(cmd)] = cmd
        page = 4096
    else:
        header = bytearray(1632)
        header[0:8] = b"ANDROID!"
        struct.pack_into("<I", header, 8, len(KERNEL))
        struct.pack_into("<I", header, 12, 0x8000)
        struct.pack_into("<I", header, 16, len(RAMDISK))
        struct.pack_into("<I", header, 20, 0x1000000)
        struct.pack_into("<I", header, 24, 0)
        struct.pack_into("<I", header, 28, 0)
        struct.pack_into("<I", header, 32, 0x100)
        struct.pack_into("<I", header, 36, 2048)
        struct.pack_into("<I", header, 40, version)
        struct.pack_into("<I", header, 44, 0)
        header[48:58] = b"test-device"
        cmd = b"console=ttyMSM0"
        header[64 : 64 + len(cmd)] = cmd
        page = 2048

    body = bytearray()
    body += bytes(header)
    body += b"\x00" * (_align(len(body), page) - len(body))
    body += KERNEL
    body += b"\x00" * (_align(len(body), page) - len(body))
    body += RAMDISK
    body += b"\x00" * (_align(len(body), page) - len(body))
    return bytes(body)


def build_vbmeta(*, flags: int = 1, algorithm: int = 2) -> bytes:
    descriptors = b""
    # hash 描述符（tag=2）
    descriptors += struct.pack("<QQ", 2, 8) + b"\x00" * 8
    # property 描述符（tag=0）
    prop = b"com.android.build.boot.security_patch\x00" + b"2026-08-05\x00" + b"\x00" * 7
    descriptors += struct.pack("<QQ", 0, len(prop)) + prop

    auth_size = 256
    aux_size = len(descriptors)

    header = bytearray(256)
    header[0:4] = b"AVB0"
    struct.pack_into("<II", header, 4, 1, 0)
    struct.pack_into("<QQ", header, 12, auth_size, aux_size)
    struct.pack_into("<I", header, 28, algorithm)
    struct.pack_into("<Q", header, 32, 0)          # hash_offset
    struct.pack_into("<Q", header, 40, 32)         # hash_size
    struct.pack_into("<Q", header, 48, 32)         # signature_offset
    struct.pack_into("<Q", header, 56, 512)        # signature_size
    struct.pack_into("<Q", header, 64, 544)        # public_key_offset
    struct.pack_into("<Q", header, 72, 1032)       # public_key_size
    struct.pack_into("<QQ", header, 80, 0, 0)      # public_key_metadata
    struct.pack_into("<Q", header, 96, 0)          # descriptors_offset
    struct.pack_into("<Q", header, 104, aux_size)
    struct.pack_into("<Q", header, 112, 0)         # rollback_index
    struct.pack_into("<I", header, 120, flags)
    struct.pack_into("<I", header, 124, 0)         # rollback_index_location
    header[128:128 + len(b"avbtool 1.2.0")] = b"avbtool 1.2.0"

    return bytes(header) + b"\x00" * auth_size + descriptors
