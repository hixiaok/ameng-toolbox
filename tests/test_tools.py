from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.image import bootimg, sparse
from iris.core.tools import local

from . import local_tmp
from .boot_fixture import KERNEL, RAMDISK, build_boot
from .gpt_fixture import build as build_gpt
from .image_fixture import build_super


class TestHash(unittest.TestCase):
    def test_hash_matches_hashlib(self):
        import hashlib

        with local_tmp() as td:
            p = Path(td) / "a.bin"
            p.write_bytes(b"iris")
            got = local.hash_file(p, ("md5", "sha256"))
        self.assertEqual(got["md5"], hashlib.md5(b"iris").hexdigest())
        self.assertEqual(got["sha256"], hashlib.sha256(b"iris").hexdigest())
        self.assertEqual(got["size"], 4)


class TestSplitJoin(unittest.TestCase):
    def test_roundtrip(self):
        data = bytes((i * 7) % 256 for i in range(10000))
        with local_tmp() as td:
            src = Path(td) / "big.bin"
            src.write_bytes(data)
            parts = local.split_file(src, "4096", Path(td) / "parts")
            self.assertEqual(len(parts), 3)
            out = Path(td) / "joined.bin"
            local.join_files(parts, out)
            self.assertEqual(out.read_bytes(), data)

    def test_join_missing(self):
        with local_tmp() as td:
            with self.assertRaises(local.IrisError):
                local.join_files(str(Path(td) / "nope"), Path(td) / "x")


class TestSparsePack(unittest.TestCase):
    def test_roundtrip(self):
        raw = b"\x11" * 4096 + b"\x00" * 8192 + b"\x22" * 4096
        with local_tmp() as td:
            src = Path(td) / "raw.img"
            src.write_bytes(raw)
            out = Path(td) / "s.img"
            local.pack_sparse(src, out)
            self.assertTrue(sparse.is_sparse(out.read_bytes()[:8]))
            stats = sparse.describe(out.read_bytes())
            self.assertGreaterEqual(stats["total_blocks"], 4)
            back = Path(td) / "back.raw"
            sparse.unpack(out, back)
            self.assertEqual(back.read_bytes(), raw)


class TestGptXml(unittest.TestCase):
    def test_generate(self):
        img = build_gpt(["boot_a", "super", "userdata"])
        with local_tmp() as td:
            disk = Path(td) / "disk.img"
            disk.write_bytes(img)
            xml_path = Path(td) / "rawprogram.xml"
            result = local.gpt_to_rawprogram(disk, xml_path)
            text = xml_path.read_text("utf-8")
        self.assertEqual(result["partitions"], 3)
        self.assertIn("<program", text)
        self.assertIn('label="super"', text)


class TestBootUnpack(unittest.TestCase):
    def test_extract(self):
        with local_tmp() as td:
            img = Path(td) / "boot.img"
            img.write_bytes(build_boot(version=4))
            out = Path(td) / "out"
            result = bootimg.extract(bootimg.parse(img), img, out)
            self.assertEqual((out / "kernel").read_bytes(), KERNEL)
            self.assertEqual((out / "ramdisk").read_bytes(), RAMDISK)
            self.assertEqual(result["kernel_bytes"], len(KERNEL))


if __name__ == "__main__":
    unittest.main()
