from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.partition import gpt

from . import local_tmp
from .gpt_fixture import build


class TestGptParse(unittest.TestCase):
    def test_parse_512(self):
        img = build(["boot_a", "init_boot_a", "system_a", "userdata"])
        table = gpt.parse(img, file_size=len(img))
        self.assertEqual(table.sector_size, 512)
        self.assertEqual(table.source, "primary")
        self.assertTrue(table.crc_ok)
        self.assertEqual(table.names(), ["boot_a", "init_boot_a", "system_a", "userdata"])

        boot = table.find("boot_a")
        self.assertIsNotNone(boot)
        self.assertEqual(boot.sectors, 64)
        start, end = boot.byte_range(512)
        self.assertEqual(end - start, 64 * 512)

    def test_parse_4096(self):
        img = build(["super", "metadata"], sector=4096, total_sectors=1024)
        table = gpt.parse(img, file_size=len(img))
        self.assertEqual(table.sector_size, 4096)
        self.assertEqual(table.names(), ["super", "metadata"])

    def test_bad_crc_falls_back_to_backup(self):
        img = bytearray(build(["boot_a", "dtbo_a"]))
        # 破坏主表的条目区，主表 CRC 不再匹配
        img[2 * 512 : 2 * 512 + 16] = b"\xff" * 16
        table = gpt.parse(bytes(img), file_size=len(img))
        self.assertEqual(table.source, "backup")
        self.assertFalse(table.crc_ok)
        self.assertIn("boot_a", table.names())

    def test_garbage_raises(self):
        with self.assertRaises(gpt.InvalidImage):
            gpt.parse(b"\x00" * 4096, file_size=4096)

    def test_read_path_roundtrip(self):
        img = build(["boot_a", "init_boot_a", "vendor_boot_a"])
        with local_tmp() as td:
            p = Path(td) / "gpt.bin"
            p.write_bytes(img)
            table = gpt.read_path(p)
            self.assertEqual(table.names(), ["boot_a", "init_boot_a", "vendor_boot_a"])

    def test_read_path_backup_only(self):
        """主表被彻底破坏时，从文件尾部读备份表。"""
        img = bytearray(build(["boot_a", "super"]))
        img[512 : 512 + 92] = b"\x00" * 92  # 抹掉主表签名
        with local_tmp() as td:
            p = Path(td) / "gpt.bin"
            p.write_bytes(bytes(img))
            table = gpt.read_path(p)
            self.assertEqual(table.source, "backup")
            self.assertEqual(table.names(), ["boot_a", "super"])


if __name__ == "__main__":
    unittest.main()
