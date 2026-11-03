from __future__ import annotations

import unittest

from iris.core.image import lp

from .image_fixture import build_super


PARTS = [
    {"name": "system_a", "extents": [(2048, 1024), (2048, 4096)]},
    {"name": "vendor_a", "extents": [(1024, 8192)]},
    {"name": "product_a", "extents": [(512, 9216)]},
]


class TestLpMetadata(unittest.TestCase):
    def setUp(self):
        self.image = build_super(PARTS)
        self.meta = lp.parse(self.image)

    def test_geometry(self):
        geom = self.meta.geometry
        self.assertEqual(geom.metadata_max_size, 65536)
        self.assertEqual(geom.metadata_slot_count, 2)
        self.assertEqual(geom.logical_block_size, 4096)

    def test_header(self):
        h = self.meta.header
        self.assertEqual((h.major, h.minor), (10, 2))
        self.assertEqual(h.header_size, 256)
        self.assertEqual(h.flags, 0)

    def test_no_warnings(self):
        self.assertEqual(self.meta.warnings, [])

    def test_partitions(self):
        self.assertEqual([p.name for p in self.meta.partitions], ["system_a", "vendor_a", "product_a"])
        system = self.meta.find("system_a")
        self.assertIsNotNone(system)
        self.assertEqual(len(system.extents), 2)
        self.assertEqual(system.size_bytes, (2048 + 2048) * 512)
        self.assertTrue(system.readonly)
        self.assertEqual(system.extents[0].byte_offset, 1024 * 512)

    def test_totals(self):
        expected = (2048 + 2048 + 1024 + 512) * 512
        self.assertEqual(self.meta.logical_size, expected)

    def test_groups_and_block_device(self):
        self.assertEqual([g.name for g in self.meta.groups], ["default"])
        self.assertEqual(self.meta.block_devices[0].partition_name, "super")

    def test_geometry_offset_is_scanned_not_hardcoded(self):
        """geometry 不固定在第 4096 字节时也要能找到。"""
        shifted = build_super(PARTS, geometry_off=8192, header_off=12288)
        meta = lp.parse(shifted)
        self.assertEqual(meta.geometry.offset, 8192)
        self.assertEqual(len(meta.partitions), 3)

    def test_bad_checksum_is_warning_not_error(self):
        broken = build_super(PARTS, corrupt_geometry_crc=True)
        meta = lp.parse(broken)
        self.assertTrue(any("geometry checksum" in w for w in meta.warnings))
        self.assertEqual(len(meta.partitions), 3)

    def test_garbage_raises(self):
        with self.assertRaises(lp.InvalidImage):
            lp.parse(b"\x00" * 65536)


if __name__ == "__main__":
    unittest.main()
