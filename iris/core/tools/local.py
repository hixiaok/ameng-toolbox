"""本地文件工具：哈希、拆分、合并、镜像打包、GPT 转 XML。

全部离线，不依赖 adb。路径是调用方机器上的真实路径（本工具本来就跑在本机）。
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from ..errors import IrisError
from ..image import sparse as sparse_mod

CHUNK = 4 * 1024 * 1024


def hash_file(path: str | Path, algos: tuple[str, ...] = ("md5", "sha256")) -> dict:
    p = Path(path)
    if not p.is_file():
        raise IrisError(f"文件不存在：{p}")
    hashers = {}
    for name in algos:
        try:
            hashers[name] = hashlib.new(name)
        except ValueError:
            raise IrisError(f"不支持的算法：{name}") from None

    size = 0
    with p.open("rb") as f:
        while chunk := f.read(CHUNK):
            size += len(chunk)
            for h in hashers.values():
                h.update(chunk)

    return {"path": str(p), "size": size, **{k: h.hexdigest() for k, h in hashers.items()}}


def _parse_size(text: str) -> int:
    """支持 512M / 2G / 1024 这类写法。"""
    t = text.strip().upper()
    mult = 1
    if t.endswith("K"):
        mult, t = 1024, t[:-1]
    elif t.endswith("M"):
        mult, t = 1024**2, t[:-1]
    elif t.endswith("G"):
        mult, t = 1024**3, t[:-1]
    try:
        value = float(t)
    except ValueError:
        raise IrisError(f"无法解析大小：{text}", hint="示例：2G / 512M / 1048576") from None
    if value <= 0:
        raise IrisError("大小必须大于 0")
    return int(value * mult)


def split_file(path: str | Path, part_size: str, out_dir: str | Path | None = None) -> list[str]:
    src = Path(path)
    if not src.is_file():
        raise IrisError(f"文件不存在：{src}")
    size = _parse_size(part_size)
    target = Path(out_dir) if out_dir else src.parent
    target.mkdir(parents=True, exist_ok=True)

    total = src.stat().st_size
    count = math.ceil(total / size)
    width = max(3, len(str(count)))
    out: list[str] = []

    with src.open("rb") as f:
        for i in range(count):
            piece = target / f"{src.name}.{i:0{width}d}"
            written = 0
            with piece.open("wb") as o:
                while written < size:
                    data = f.read(min(CHUNK, size - written))
                    if not data:
                        break
                    o.write(data)
                    written += len(data)
            out.append(str(piece))
    return out


def join_files(parts: list[str] | str, out: str | Path) -> dict:
    """parts 可以是文件列表，也可以是 "目录/前缀" 这种模式。"""
    if isinstance(parts, str):
        base = Path(parts)
        if any(ch in parts for ch in "*?[]"):
            files = sorted(base.parent.glob(base.name))
        elif base.is_dir():
            files = sorted(base.glob("*"))
        else:
            files = sorted(base.parent.glob(base.name + ".*"))
    else:
        files = [Path(p) for p in parts]

    files = [f for f in files if f.is_file()]
    if not files:
        raise IrisError("没有找到要合并的分片")

    total = 0
    with Path(out).open("wb") as o:
        for f in files:
            with f.open("rb") as i:
                while chunk := i.read(CHUNK):
                    o.write(chunk)
                    total += len(chunk)
    return {"output": str(out), "bytes": total, "parts": len(files)}


def pack_sparse(src: str | Path, out: str | Path, *, block_size: int = 4096) -> dict:
    return sparse_mod.pack(src, out, block_size=block_size)


def gpt_to_rawprogram(image: str | Path, out: str | Path, *, filename_suffix: str = ".img",
                      physical_partition: int = 0) -> dict:
    """生成 9008（QFIL/fh_loader）用的 rawprogram XML。"""
    from ..partition import gpt as gpt_mod

    table = gpt_mod.read_path(image)
    root = ET.Element("data")
    for part in table.partitions:
        ET.SubElement(
            root,
            "program",
            {
                "SECTOR_SIZE_IN_BYTES": str(table.sector_size),
                "filename": f"{part.name}{filename_suffix}" if part.name else "NONAME.img",
                "label": part.name or "NONAME",
                "num_partition_sectors": str(part.sectors),
                "physical_partition_number": str(physical_partition),
                "start_sector": str(part.first_lba),
            },
        )
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return {
        "output": str(out),
        "partitions": len(table.partitions),
        "sector_size": table.sector_size,
    }
