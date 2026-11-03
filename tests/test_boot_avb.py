from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.image import avb, bootimg, lp

from . import local_tmp
from .boot_fixture import KERNEL, RAMDISK, build_boot, build_vbmeta
from .image_fixture import build_super


class TestBootImage(unittest.TestCase):
    def test_v4(self):
        with local_tmp() as td:
            p = Path(td) / "boot.img"
            p.write_bytes(build_boot(version=4))
            img = bootimg.parse(p)
        self.assertEqual(img.header_version, 4)
        self.assertEqual(img.kernel_size, len(KERNEL))
        self.assertEqual(img.ramdisk_size, len(RAMDISK))
        self.assertEqual(img.page_size, 4096)
        self.assertIn("console=", img.cmdline)
        self.assertEqual(img.kernel_offset % 4096, 0)
        self.assertGreaterEqual(img.ramdisk_offset, img.kernel_offset + len(KERNEL))

    def test_v0(self):
        with local_tmp() as td:
            p = Path(td) / "boot.img"
            p.write_bytes(build_boot(version=0))
            img = bootimg.parse(p)
        self.assertEqual(img.header_version, 0)
        self.assertEqual(img.page_size, 2048)
        self.assertEqual(img.name, "test-device")
        self.assertEqual(img.kernel_size, len(KERNEL))

    def test_bad_magic(self):
        with local_tmp() as td:
            p = Path(td) / "x.img"
            p.write_bytes(b"\x00" * 4096)
            with self.assertRaises(bootimg.InvalidImage):
                bootimg.parse(p)


class TestVbmeta(unittest.TestCase):
    def test_parse(self):
        with local_tmp() as td:
            p = Path(td) / "vbmeta.img"
            p.write_bytes(build_vbmeta(flags=1, algorithm=2))
            meta = avb.parse(p)
        self.assertEqual(meta.algorithm_name, "SHA256_RSA4096")
        self.assertEqual(meta.flags, 1)
        self.assertIn("hashtree_disabled", meta.flag_names)
        self.assertTrue(meta.release_string.startswith("avbtool"))
        tags = [t for t, _ in meta.descriptors]
        self.assertEqual(tags, [2, 0])

    def test_bad_magic(self):
        with local_tmp() as td:
            p = Path(td) / "x.img"
            p.write_bytes(b"\x00" * 1024)
            with self.assertRaises(avb.InvalidImage):
                avb.parse(p)


class TestSuperExtract(unittest.TestCase):
    def test_extract_linear(self):
        payload = bytes((i * 11) % 256 for i in range(2048 * 512))
        blob = bytearray(build_super([{"name": "system_a", "extents": [(2048, 1024)]}]))
        blob[1024 * 512 : 1024 * 512 + len(payload)] = payload

        with local_tmp() as td:
            src = Path(td) / "super.img"
            src.write_bytes(bytes(blob))
            meta = lp.parse(bytes(blob))
            part = meta.find("system_a")
            out = Path(td) / "system_a.img"
            stats = lp.extract_partition(meta, part, out, src=src)
            self.assertEqual(out.read_bytes(), payload)
            self.assertEqual(stats["bytes"], len(payload))

    def test_missing_partition(self):
        blob = build_super([{"name": "system_a", "extents": [(2048, 1024)]}])
        meta = lp.parse(blob)
        self.assertIsNone(meta.find("nope"))


if __name__ == "__main__":
    unittest.main()
