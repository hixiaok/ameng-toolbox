from __future__ import annotations

import shlex
import unittest

from iris.core.device import root
from iris.core.errors import PermissionDenied

from .fake_android import FakeAndroid


class TestRootDetect(unittest.TestCase):
    def test_magisk_granted_via_su(self):
        adb = FakeAndroid(root=False, granted=True, manager="Magisk")
        status = root.detect(adb)

        self.assertTrue(status.available)
        self.assertEqual(status.method, "su")
        self.assertEqual(status.manager, "Magisk")
        self.assertEqual(status.version, "27.0:MAGISK")
        self.assertEqual(status.su_path, "/system/bin/su")

    def test_adb_root_shell(self):
        adb = FakeAndroid(root=True)
        status = root.detect(adb)

        self.assertTrue(status.available)
        self.assertEqual(status.method, "adb root")

    def test_no_su(self):
        adb = FakeAndroid(root=False, su_present=False)
        status = root.detect(adb)

        self.assertFalse(status.available)
        self.assertIn("su", status.reason)

    def test_su_present_but_denied(self):
        adb = FakeAndroid(root=False, granted=False)
        status = root.detect(adb)

        self.assertFalse(status.available)
        self.assertIn("未授权", status.reason)

    def test_kernelsu_detected(self):
        adb = FakeAndroid(root=False, granted=True, manager="KernelSU")
        status = root.detect(adb)

        self.assertTrue(status.available)
        self.assertEqual(status.manager, "KernelSU")

    def test_require_root_raises_with_hint(self):
        adb = FakeAndroid(root=False, su_present=False)
        with self.assertRaises(PermissionDenied) as ctx:
            root.require_root(adb)
        self.assertTrue(ctx.exception.hint)
        self.assertEqual(ctx.exception.exit_code, 5)


class TestRootExec(unittest.TestCase):
    def test_command_reaches_su_as_single_argument(self):
        """核心不变量：命令整体只过设备 sh 一层引号，su 收到的是原始整串。"""
        adb = FakeAndroid(root=False, granted=True)
        r = root.Root(adb)
        cmd = "echo 'a b' | tr a-z A-Z && ls /data"
        r.run(cmd)

        su_calls = [c for c in adb.calls if c[0] == "su"]
        self.assertTrue(su_calls)
        argv = su_calls[-1]
        self.assertEqual(argv[:2], ("su", "-c"))
        # 设备 sh 解析后，su -c 拿到的是一个完整命令
        self.assertEqual(shlex.split(argv[2]), [cmd])

    def test_quotes_and_dollar_survive(self):
        adb = FakeAndroid(root=False, granted=True)
        r = root.Root(adb)
        cmd = 'echo "$HOME" \'x\' `id`'
        r.run(cmd)
        argv = [c for c in adb.calls if c[0] == "su"][-1]
        self.assertEqual(shlex.split(argv[2]), [cmd])

    def test_denied_run_raises(self):
        adb = FakeAndroid(root=False, granted=False)
        r = root.Root(adb)
        with self.assertRaises(PermissionDenied):
            r.run("id")

    def test_test_returns_false_instead_of_raising(self):
        adb = FakeAndroid(root=False, granted=False)
        self.assertFalse(root.Root(adb).test("true"))


if __name__ == "__main__":
    unittest.main()
