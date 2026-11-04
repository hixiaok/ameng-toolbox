from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from iris.core.device import partitions
from iris.core.proc import ProcResult

from . import local_tmp
from .fake_android import FakeAndroid


class TestTable(unittest.TestCase):
    def test_parses_name_path_size(self):
        adb = FakeAndroid(partitions={"boot_a": 64 * 1024 * 1024, "super": 8 * 1024 ** 3})
        parts = partitions.table(adb)

        self.assertEqual([p.name for p in parts], ["boot_a", "super"])
        self.assertEqual(parts[0].size, 64 * 1024 * 1024)
        self.assertEqual(parts[0].path, "/dev/block/by-name/boot_a")
        self.assertEqual(parts[0].size_text, "64.0MiB")

    def test_missing_partition_raises(self):
        adb = FakeAndroid()
        with self.assertRaises(partitions.DiskError):
            partitions.find_partition(adb, "vendor_boot_b")


class TestPlan(unittest.TestCase):
    def test_backup_plan_has_paths_and_no_blockers(self):
        adb = FakeAndroid()
        with local_tmp() as td:
            plan = partitions.plan_backup(adb, "boot_a", td)
        self.assertEqual(plan.action, "backup")
        self.assertTrue(plan.executable)
        self.assertTrue(plan.local_path.endswith(".img"))
        self.assertIn("/data/local/tmp/iris/", plan.remote_tmp)
        self.assertEqual(plan.partition_size, 64 * 1024 * 1024)

    def test_restore_plan_blocks_oversized_image(self):
        adb = FakeAndroid()
        with local_tmp() as td:
            img = Path(td) / "too-big.img"
            img.write_bytes(b"\0" * (65 * 1024 * 1024))
            plan = partitions.plan_restore(adb, "boot_a", str(img))
        self.assertFalse(plan.executable)
        self.assertTrue(any("大于分区" in b for b in plan.blockers))

    def test_restore_plan_warns_smaller_image(self):
        adb = FakeAndroid()
        with local_tmp() as td:
            img = Path(td) / "small.img"
            img.write_bytes(b"\1" * 1024)
            plan = partitions.plan_restore(adb, "boot_a", str(img))
        self.assertTrue(plan.executable)
        self.assertTrue(any("比分区小" in w for w in plan.warnings))
        self.assertEqual(len(plan.sha256), 64)

    def test_restore_plan_missing_image(self):
        adb = FakeAndroid()
        with self.assertRaises(partitions.DiskError):
            partitions.plan_restore(adb, "boot_a", "does-not-exist-iris.img")


class TestBackupApply(unittest.TestCase):
    def test_backup_verifies_both_sides(self):
        adb = FakeAndroid()
        with local_tmp() as td:
            plan = partitions.plan_backup(adb, "boot_a", td)
            result = partitions.apply_backup(adb, plan)

            self.assertTrue(result["ok"])
            self.assertTrue(result["verified"])
            data = Path(result["local_path"]).read_bytes()
            self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(result["size"], len(data))

    def test_backup_detects_corruption(self):
        adb = FakeAndroid()

        def corrupt_pull(remote, local, timeout=None):
            Path(local).write_bytes(b"TRUNCATED")
            return ProcResult(argv=("pull",), code=0, out="", err="", duration=0.0)

        adb.pull = corrupt_pull  # type: ignore[assignment]
        with local_tmp() as td:
            plan = partitions.plan_backup(adb, "boot_a", td)
            with self.assertRaises(partitions.DiskError) as ctx:
                partitions.apply_backup(adb, plan)
        self.assertIn("校验失败", str(ctx.exception))

    def test_backup_blocked_plan_is_not_executed(self):
        adb = FakeAndroid(partitions={"boot_a": 64 * 1024 * 1024})
        with local_tmp() as td:
            plan = partitions.plan_backup(adb, "boot_a", td)
            plan.blockers.append("模拟：空间不足")
            with self.assertRaises(partitions.DiskError):
                partitions.apply_backup(adb, plan)


class TestRestoreApply(unittest.TestCase):
    def test_restore_pushes_writes_and_verifies(self):
        adb = FakeAndroid()
        content = b"IRIS-BOOT-IMAGE" * 64
        with local_tmp() as td:
            img = Path(td) / "boot.img"
            img.write_bytes(content)
            plan = partitions.plan_restore(adb, "boot_a", str(img))
            result = partitions.apply_restore(adb, plan)

            self.assertTrue(result["ok"])
            self.assertEqual(result["written"], len(content))
            self.assertEqual(result["verify"]["scope"], "full")
            self.assertEqual(adb.tmp["/dev/block/by-name/boot_a"], content)

    def test_restore_refuses_blocked_plan(self):
        adb = FakeAndroid()
        with local_tmp() as td:
            img = Path(td) / "big.img"
            img.write_bytes(b"\0" * (65 * 1024 * 1024))
            plan = partitions.plan_restore(adb, "boot_a", str(img))
            with self.assertRaises(partitions.DiskError):
                partitions.apply_restore(adb, plan)


if __name__ == "__main__":
    unittest.main()
