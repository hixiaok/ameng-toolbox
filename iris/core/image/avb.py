"""AVB / vbmeta 解析。

只需要判断：这个设备/镜像是哪种签名方案、是否启用 verity/verification、
以及用的是什么密钥算法。这对"能不能免解锁刷"很关键。

结构（AOSP avbtool，小端）：
    magic "AVB0" | major u32 | minor u32 |
    auth_block_size u64 | aux_block_size u64 | algorithm u32 |
    hash_offset/size | signature_offset/size |
    public_key_offset/size | public_key_metadata_offset/size |
    descriptors_offset/size | rollback_index u64 |
    flags u32 | rollback_index_location u32 | release_string[48] | reserved[80]
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..errors import InvalidImage

MAGIC = b"AVB0"
HEADER_SIZE = 256

ALGORITHMS = {
    0: "NONE",
    1: "SHA256_RSA2048",
    2: "SHA256_RSA4096",
    3: "SHA256_RSA8192",
    4: "SHA512_RSA2048",
    5: "SHA512_RSA4096",
    6: "SHA512_RSA8192",
}

FLAG_HASHTREE_DISABLED = 1 << 0
FLAG_VERIFICATION_DISABLED = 1 << 1
FLAG_VERITY_DISABLED = 1 << 2

FLAG_NAMES = {
    0: "hashtree_disabled",
    1: "verification_disabled",
    2: "verity_disabled",
}

DESCRIPTOR_TAGS = {
    0: "property",
    1: "hashtree",
    2: "hash",
    3: "kernel_cmdline",
    4: "chain_partition",
}

DESCRIPTOR_HEADER = 16  # tag u64 + num_bytes_following u64


@dataclass
class Vbmeta:
    version_major: int
    version_minor: int
    auth_size: int
    aux_size: int
    algorithm: int
    rollback_index: int
    flags: int
    rollback_index_location: int
    release_string: str
    descriptors: list[tuple[int, int]]  # (tag, size)

    @property
    def algorithm_name(self) -> str:
        return ALGORITHMS.get(self.algorithm, f"UNKNOWN({self.algorithm})")

    @property
    def flag_names(self) -> list[str]:
        return [name for bit, name in FLAG_NAMES.items() if self.flags & (1 << bit)]

    @property
    def is_verity_disabled(self) -> bool:
        # avbtool 只有两个 flag 位：bit0 关 hashtree（等价于 dm-verity 关闭）、bit1 关验证
        return bool(self.flags & FLAG_HASHTREE_DISABLED)

    def to_dict(self) -> dict:
        return {
            "version": f"{self.version_major}.{self.version_minor}",
            "auth_size": self.auth_size,
            "aux_size": self.aux_size,
            "algorithm": self.algorithm_name,
            "rollback_index": self.rollback_index,
            "rollback_index_location": self.rollback_index_location,
            "flags": self.flags,
            "flag_names": self.flag_names,
            "verity_disabled": self.is_verity_disabled,
            "release_string": self.release_string,
            "descriptors": [
                {"tag": tag, "name": DESCRIPTOR_TAGS.get(tag, f"unknown({tag})"), "size": size}
                for tag, size in self.descriptors
            ],
        }


def is_vbmeta(head: bytes) -> bool:
    return head[:4] == MAGIC


def _parse_descriptors(blob: bytes) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    pos = 0
    while pos + DESCRIPTOR_HEADER <= len(blob):
        tag = struct.unpack_from("<Q", blob, pos)[0]
        size = struct.unpack_from("<Q", blob, pos + 8)[0]
        if size > len(blob) - pos - DESCRIPTOR_HEADER:
            break
        out.append((tag, size))
        pos += DESCRIPTOR_HEADER + size
        if len(out) > 256:
            break
    return out


def parse(path: str | Path) -> Vbmeta:
    p = Path(path)
    if not p.is_file():
        raise InvalidImage(f"文件不存在：{p}")

    with p.open("rb") as f:
        buf = f.read(HEADER_SIZE + 64 * 1024)
    if len(buf) < HEADER_SIZE:
        raise InvalidImage("文件太小，不是 vbmeta")
    if buf[:4] != MAGIC:
        raise InvalidImage("不是 vbmeta（magic 'AVB0' 不匹配）")

    major, minor = struct.unpack_from("<II", buf, 4)
    auth_size, aux_size = struct.unpack_from("<QQ", buf, 12)
    algorithm = struct.unpack_from("<I", buf, 28)[0]
    descriptors_offset, descriptors_size = struct.unpack_from("<QQ", buf, 96)
    rollback_index = struct.unpack_from("<Q", buf, 112)[0]
    flags = struct.unpack_from("<I", buf, 120)[0]
    rollback_loc = struct.unpack_from("<I", buf, 124)[0]
    release = buf[128:176].split(b"\x00")[0].decode("utf-8", "replace").strip()

    desc_start = HEADER_SIZE + auth_size + descriptors_offset
    descriptors = _parse_descriptors(buf[desc_start : desc_start + descriptors_size]) if descriptors_size else []

    return Vbmeta(major, minor, auth_size, aux_size, algorithm, rollback_index,
                  flags, rollback_loc, release, descriptors)
