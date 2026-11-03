from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.image import sparse

from . import local_tmp
from .image_fixture import build_sparse, expected_unpacked

BLOCK = 4096
RAW = bytes((i * 7) % 256 for i in range(BLOCK * 8))


class TestSparse(unittest.TestCase):
    def setUp(self):
        self.blob = build_sparse(RAW, block_size=BLOCK)

    def test_header(self):
        info = sparse.parse_header(self.blob)
        self.assertEqual(info.block_size, BLOCK)
        self.assertEqual(info.total_chunks, 4)
        self.assertEqual(info.expanded_size, info.total_blocks * BLOCK)

    def test_is_sparse(self):
        self.assertTrue(sparse.is_sparse(self.blob))
        self.assertFalse(sparse.is_sparse(b"not a sparse image"))

    def test_chunk_kinds(self):
        kinds = [c.kind for c in sparse.iter_chunks(self.blob)]
        self.assertEqual(kinds, ["raw", "fill", "dont_care", "raw"])

    def test_describe(self):
        info = sparse.describe(self.blob)
        self.assertEqual(info["chunk_stats"]["raw"], 2)
        self.assertEqual(info["chunk_stats"]["fill"], 1)
        self.assertEqual(info["chunk_stats"]["dont_care"], 1)

    def test_unpack_matches_expected(self):
        with local_tmp() as td:
            src = Path(td) / "x.img"
            dst = Path(td) / "x.raw"
            src.write_bytes(self.blob)
            stats = sparse.unpack(src, dst)
            self.assertEqual(dst.read_bytes(), expected_unpacked(RAW, block_size=BLOCK))
            self.assertEqual(stats["expanded_bytes"], len(expected_unpacked(RAW, block_size=BLOCK)))
            self.assertEqual(stats["chunks"], 4)

    def test_truncated_raises(self):
        with self.assertRaises(sparse.InvalidImage):
            list(sparse.iter_chunks(self.blob[: len(self.blob) // 2]))

    def test_bad_magic(self):
        with self.assertRaises(sparse.InvalidImage):
            sparse.parse_header(b"\x00" * 28)


if __name__ == "__main__":
    unittest.main()
