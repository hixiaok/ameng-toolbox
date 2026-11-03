"""Android boot 镜像头解析（boot.img / init_boot.img）。

支持 header v0–v2（老布局）和 v3/v4（新布局）。只做解析，不改写——
改写涉及重算 id 哈希和页对齐，风险高，等写入阶段再说。

magic：
    ANDROID!  boot / init_boot
    VNDRBOOT  vendor_boot（v3/v4 专用布局，字段不同，这里单独标注）
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import InvalidImage

BOOT_MAGIC = b"ANDROID!"
VENDOR_MAGIC = b"VNDRBOOT"

# v0–v2 头长度 1632；v3 1580；v4 1584
LEGACY_MIN = 1632
V3_HEADER = 1580


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _text(raw: bytes) -> str:
    return raw.split(b"\x00")[0].decode("utf-8", "replace").strip()


@dataclass
class BootImage:
    magic: str
    header_version: int
    header_size: int
    page_size: int
    kernel_size: int
    ramdisk_size: int
    second_size: int
    os_version: str
    name: str
    cmdline: str
    kernel_offset: int = 0
    ramdisk_offset: int = 0
    second_offset: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def kernel_end(self) -> int:
        return self.kernel_offset + self.kernel_size

    def to_dict(self) -> dict:
        return {
            "magic": self.magic,
            "header_version": self.header_version,
            "header_size": self.header_size,
            "page_size": self.page_size,
            "kernel_size": self.kernel_size,
            "ramdisk_size": self.ramdisk_size,
            "second_size": self.second_size,
            "os_version": self.os_version,
            "name": self.name,
            "cmdline": self.cmdline,
            "kernel_offset": self.kernel_offset,
            "ramdisk_offset": self.ramdisk_offset,
            "notes": self.notes,
        }


def _os_version(value: int) -> str:
    if value == 0:
        return "未知"
    a = (value >> 25) & 0x7F
    b = (value >> 18) & 0x7F
    c = (value >> 11) & 0x7F
    y = ((value >> 4) & 0x7F) + 2000
    m = value & 0xF
    return f"{a}.{b}.{c} ({y}-{m:02d})"


def is_boot(head: bytes) -> bool:
    return head[:8] in (BOOT_MAGIC, VENDOR_MAGIC)


def parse(path: str | Path) -> BootImage:
    p = Path(path)
    if not p.is_file():
        raise InvalidImage(f"文件不存在：{p}")

    with p.open("rb") as f:
        head = f.read(V3_HEADER)
    if len(head) < 44:
        raise InvalidImage("文件太小，不可能是 boot 镜像")

    magic = head[:8]
    if magic == VENDOR_MAGIC:
        raise InvalidImage("这是 vendor_boot 镜像，暂不支持解析")
    if magic != BOOT_MAGIC:
        raise InvalidImage("不是 boot 镜像（magic 'ANDROID!' 不匹配）")

    notes: list[str] = []
    version = _u32(head, 40)

    if version >= 3:
        header_size = _u32(head, 20)
        kernel_size = _u32(head, 8)
        ramdisk_size = _u32(head, 12)
        os_ver = _os_version(_u32(head, 16))
        cmdline = _text(head[44 : 44 + 1536])
        page_size = 4096  # v3/v4 固定 4096
        second_size = 0
        name = ""
        if header_size not in (V3_HEADER, 1584):
            notes.append(f"header_size 异常（{header_size}），按 1580 处理")
        if version > 4:
            notes.append(f"未知的 header_version {version}，仅按 v4 结构解析")
    else:
        page_size = _u32(head, 36)
        header_size = LEGACY_MIN
        kernel_size = _u32(head, 8)
        ramdisk_size = _u32(head, 16)
        second_size = _u32(head, 24)
        os_ver = _os_version(_u32(head, 44))
        name = _text(head[48:64])
        cmdline = _text(head[64:64 + 512])
        if page_size <= 0 or page_size & (page_size - 1):
            notes.append(f"page_size 非法（{page_size}），按 2048 处理")
            page_size = 2048

    def align(size: int) -> int:
        if size <= 0:
            return 0
        return (size + page_size - 1) // page_size * page_size

    kernel_offset = align(header_size)
    ramdisk_offset = kernel_offset + align(kernel_size)
    second_offset = ramdisk_offset + align(ramdisk_size)

    return BootImage(
        magic="ANDROID!",
        header_version=version,
        header_size=header_size,
        page_size=page_size,
        kernel_size=kernel_size,
        ramdisk_size=ramdisk_size,
        second_size=second_size,
        os_version=os_ver,
        name=name,
        cmdline=cmdline,
        kernel_offset=kernel_offset,
        ramdisk_offset=ramdisk_offset,
        second_offset=second_offset,
        notes=notes,
    )


def extract(img: BootImage, src: str | Path, out_dir: str | Path) -> dict:
    """按头里的偏移切出 kernel / ramdisk。"""
    source = Path(src)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}
    with source.open("rb") as f:
        f.seek(img.kernel_offset)
        kernel = f.read(img.kernel_size)
        (out / "kernel").write_bytes(kernel)
        written["kernel"] = str(out / "kernel")

        if img.ramdisk_size:
            f.seek(img.ramdisk_offset)
            ramdisk = f.read(img.ramdisk_size)
            (out / "ramdisk").write_bytes(ramdisk)
            written["ramdisk"] = str(out / "ramdisk")

    return {
        "output_dir": str(out),
        "files": written,
        "kernel_bytes": len(kernel),
        "ramdisk_bytes": img.ramdisk_size,
    }
