from __future__ import annotations

import os
import unittest
from unittest import mock

from iris.core.adb import Device
from iris.core.proc import ProcResult
from iris.core.profile import load_cached, probe, save

from . import local_tmp

PROC_PARTITIONS = """major minor  #blocks  name

 259        0     131072 sda
 259        1       8192 sda1
 259        2      16384 sda2
   8        0     262144 sdb
"""


def res(argv, code=0, out="", err=""):
    return ProcResult(argv=tuple(argv), code=code, out=out, err=err, duration=0.01)


class FakeAdb:
    """按命令回放的假 adb —— 这就是"无真机可测"的关键。"""

    def __init__(self, *, by_name=(), root=False, props=None, su_by_name=(), serial="TEST123"):
        self.by_name = set(by_name)
        self.su_by_name = set(su_by_name)
        self.root = root
        self.serial = serial
        self._props = props or {
            "ro.product.model": "Pad 7 Ultra",
            "ro.product.brand": "Xiaomi",
            "ro.product.device": "uke",
            "ro.soc.model": "XRING O1",
            "ro.soc.manufacturer": "Xiaomi",
            "ro.build.version.release": "16",
            "ro.build.version.sdk": "36",
            "ro.product.cpu.abi": "arm64-v8a",
            "ro.build.version.security_patch": "2026-10-05",
            "ro.build.ab_update": "true",
            "ro.boot.slot_suffix": "_a",
            "ro.build.fingerprint": "Xiaomi/uke/uke:16/AP4A/1:user/release-keys",
        }

    def require_device(self):
        return Device(serial=self.serial, state="device")

    def props(self):
        return dict(self._props)

    def shell(self, *args, timeout=None):
        return self._dispatch(args, su=False)

    def shell_su(self, *args, timeout=None):
        return self._dispatch(args, su=True)

    def _dispatch(self, args, su):
        if args == ("id",):
            return res(args, 0, "uid=0(root) gid=0(root)\n" if self.root else "uid=2000(shell) gid=2000(shell)\n")
        if args == ("which", "su"):
            return res(args, 0 if self.root else 1, "/system/bin/su\n" if self.root else "")
        if args == ("cat", "/proc/partitions"):
            return res(args, 0, PROC_PARTITIONS)
        if args and args[0] == "ls":
            allow = self.su_by_name if su else self.by_name
            if args[1] in allow:
                return res(args, 0, "boot_a\ninit_boot_a\nsuper\nuserdata\n")
            return res(args, 1, "", f"ls: {args[1]}: No such file or directory")
        return res(args, 1, "", "unsupported")


class TestProfile(unittest.TestCase):
    def test_xring_case_uses_by_name_not_bootdevice(self):
        """复刻上游 issue #4：没有 /dev/block/bootdevice/by-name，只有 /dev/block/by-name。"""
        prof = probe(FakeAdb(by_name={"/dev/block/by-name"}))

        self.assertEqual(prof.by_name_root, "/dev/block/by-name")
        path = prof.partition_path("boot_a")
        self.assertEqual(path, "/dev/block/by-name/boot_a")
        self.assertNotIn("bootdevice", path)

        hits = [p for p in prof.probes if p.name.startswith("by_name") and p.ok]
        self.assertEqual(hits[0].value, "/dev/block/by-name")

    def test_falls_through_to_bootdevice_candidate(self):
        """只有 bootdevice 存在的设备，必须继续往下试到第二个候选。"""
        prof = probe(FakeAdb(by_name={"/dev/block/bootdevice/by-name"}))
        self.assertEqual(prof.by_name_root, "/dev/block/bootdevice/by-name")
        self.assertEqual(prof.partition_path("super"), "/dev/block/bootdevice/by-name/super")

    def test_root_and_su_probe(self):
        adb = FakeAdb(root=True, su_by_name={"/dev/block/bootdevice/by-name"})
        prof = probe(adb)
        self.assertTrue(prof.root)
        self.assertEqual(prof.by_name_root, "/dev/block/bootdevice/by-name")
        self.assertTrue(prof.can_write)

    def test_no_by_name_still_reads_proc_partitions(self):
        adb = FakeAdb()
        prof = probe(adb)
        self.assertIsNone(prof.by_name_root)
        self.assertFalse(prof.can_write)
        self.assertTrue(prof.can_read_partitions)
        self.assertEqual(prof.partitions["sda1"], 8192 * 1024)
        self.assertEqual(prof.block_device, "/dev/block/sdb")  # 262144 块，最大

    def test_ab_slot(self):
        prof = probe(FakeAdb(by_name={"/dev/block/by-name"}))
        self.assertTrue(prof.ab_update)
        self.assertEqual(prof.slot_suffix, "_a")
        self.assertEqual(prof.soc_model, "XRING O1")

    def test_cache_roundtrip(self):
        with local_tmp() as td, mock.patch.dict(os.environ, {"LOCALAPPDATA": str(td)}):
            prof = probe(FakeAdb(by_name={"/dev/block/by-name"}))
            path = save(prof)
            self.assertTrue(path.is_file())
            again = load_cached(prof.serial)
            self.assertIsNotNone(again)
            self.assertEqual(again.model, prof.model)
            self.assertEqual(again.by_name_root, prof.by_name_root)
            self.assertEqual(len(again.probes), len(prof.probes))


if __name__ == "__main__":
    unittest.main()
