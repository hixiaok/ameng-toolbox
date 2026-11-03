from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.image import lp, superbuild

from . import local_tmp


class TestSuperBuild(unittest.TestCase):
    def test_merge_then_parse(self):
        system = bytes((i * 3) % 256 for i in range(200_000))
        vendor = bytes((i * 5) % 256 for i in range(90_000))

        with local_tmp() as td:
            d = Path(td)
            (d / "system.img").write_bytes(system)
            (d / "vendor.img").write_bytes(vendor)

            out = d / "super.img"
            result = superbuild.merge(
                [("system_a", d / "system.img"), ("vendor_a", d / "vendor.img")], out
            )
            self.assertTrue(out.is_file())
            self.assertEqual(result["out_bytes"], out.stat().st_size)

            meta = lp.parse(out.read_bytes()[: 8 * 1024 * 1024])
            self.assertEqual([p.name for p in meta.partitions], ["system_a", "vendor_a"])
            # LP extent 以 512B 扇区为单位，文件长度会向上对齐
            self.assertGreaterEqual(meta.find("system_a").size_bytes, len(system))
            self.assertLess(meta.find("system_a").size_bytes - len(system), 512)
            self.assertEqual(meta.warnings, [])
            self.assertEqual(meta.block_devices[0].partition_name, "super")

            back = d / "system_back.img"
            lp.extract_partition(meta, meta.find("system_a"), back, src=out)
            raw = back.read_bytes()
            self.assertEqual(raw[: len(system)], system)
            self.assertEqual(raw[len(system):].strip(b"\x00"), b"")

            back2 = d / "vendor_back.img"
            lp.extract_partition(meta, meta.find("vendor_a"), back2, src=out)
            self.assertEqual(back2.read_bytes()[: len(vendor)], vendor)

    def test_empty_rejected(self):
        with self.assertRaises(Exception):
            superbuild.plan([])

    def test_duplicate_name(self):
        with local_tmp() as td:
            p = Path(td) / "a.img"
            p.write_bytes(b"\x01" * 4096)
            with self.assertRaises(Exception):
                superbuild.plan([("system_a", p), ("system_a", p)])

    def test_too_small_total(self):
        with local_tmp() as td:
            p = Path(td) / "a.img"
            p.write_bytes(b"\x01" * 4096)
            with self.assertRaises(Exception):
                superbuild.plan([("system_a", p)], total_size=1024)


if __name__ == "__main__":
    unittest.main()
