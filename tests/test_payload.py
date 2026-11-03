from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.image import payload as pl

from . import local_tmp
from .payload_fixture import BLOCK, build_payload, build_zero_payload

BOOT = bytes((i * 13) % 256 for i in range(BLOCK * 2))
SYSTEM = bytes((i * 7) % 256 for i in range(BLOCK * 3))


class TestPayload(unittest.TestCase):
    def setUp(self):
        self.blob = build_payload({"boot": BOOT, "system": SYSTEM})

    def _write(self, td, data, name="payload.bin"):
        p = Path(td) / name
        p.write_bytes(data)
        return p

    def test_is_payload(self):
        self.assertTrue(pl.is_payload(self.blob[:16]))
        self.assertFalse(pl.is_payload(b"\x00" * 16))

    def test_parse(self):
        with local_tmp() as td:
            p = self._write(td, self.blob)
            pay = pl.parse(p)
        self.assertEqual(pay.version, 2)
        self.assertEqual(pay.block_size, BLOCK)
        self.assertEqual([x.name for x in pay.partitions], ["boot", "system"])
        self.assertEqual(pay.find("boot").size_bytes, len(BOOT))
        self.assertEqual(pay.data_start, 20 + 4 + pay.manifest_size + 0)

    def test_extract_boot(self):
        with local_tmp() as td:
            p = self._write(td, self.blob)
            pay = pl.parse(p)
            out = Path(td) / "boot.img"
            stats = pl.extract(pay, pay.find("boot"), out, src=p)
            self.assertEqual(out.read_bytes(), BOOT)
            self.assertEqual(stats["bytes"], len(BOOT))

    def test_extract_bz2(self):
        blob = build_payload({"boot": BOOT}, compress="bz2")
        with local_tmp() as td:
            p = self._write(td, blob)
            pay = pl.parse(p)
            out = Path(td) / "boot.img"
            pl.extract(pay, pay.find("boot"), out, src=p)
            self.assertEqual(out.read_bytes(), BOOT)

    def test_zero_op(self):
        blob = build_zero_payload("blank", blocks=2)
        with local_tmp() as td:
            p = self._write(td, blob)
            pay = pl.parse(p)
            out = Path(td) / "blank.img"
            pl.extract(pay, pay.find("blank"), out, src=p)
            self.assertEqual(out.read_bytes(), b"\x00" * (BLOCK * 2))

    def test_bad_magic(self):
        with local_tmp() as td:
            p = self._write(td, b"XXXX" + b"\x00" * 64)
            with self.assertRaises(pl.InvalidImage):
                pl.parse(p)

    def test_unknown_partition(self):
        with local_tmp() as td:
            p = self._write(td, self.blob)
            pay = pl.parse(p)
            self.assertIsNone(pay.find("nope"))


if __name__ == "__main__":
    unittest.main()
