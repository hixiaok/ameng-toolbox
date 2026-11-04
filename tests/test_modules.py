from __future__ import annotations

import unittest
from pathlib import Path

from iris.core.device import modules

from . import local_tmp
from .fake_android import FakeAndroid

DUMP = """=== zygisk-next
id=zygisk-next
name=Zygisk Next
version=v1.2.3
versionCode=123
author=Dr-TS
description=为 KernelSU 提供 Zygisk 支持
__DISABLE__
=== lsposed
id=lsposed
name=LSPosed
version=1.9.3
versionCode=193
author=LSPosed
description=模块化 Xposed 框架
"""


class TestParse(unittest.TestCase):
    def test_parses_props_and_flags(self):
        mods = modules._parse(DUMP)
        by_name = {m.name: m for m in mods}

        self.assertEqual(by_name["Zygisk Next"].version, "v1.2.3")
        self.assertEqual(by_name["Zygisk Next"].version_code, "123")
        self.assertEqual(by_name["Zygisk Next"].author, "Dr-TS")
        self.assertFalse(by_name["Zygisk Next"].enabled)
        self.assertTrue(by_name["LSPosed"].enabled)
        self.assertEqual(by_name["LSPosed"].version, "1.9.3")

    def test_disabled_modules_sort_first(self):
        mods = modules._parse(DUMP)
        self.assertFalse(mods[0].enabled)

    def test_empty_dump(self):
        self.assertEqual(modules._parse(""), [])

    def test_garbage_lines_ignored(self):
        mods = modules._parse("=== x\nnot a prop line\nversion=1\n")
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0].version, "1")


class TestManager(unittest.TestCase):
    def test_magisk_can_install(self):
        adb = FakeAndroid(root=False, granted=True, manager="Magisk")
        mgr = modules.manager(adb)
        self.assertEqual(mgr.name, "Magisk")
        self.assertTrue(mgr.can_install)

    def test_kernelsu(self):
        adb = FakeAndroid(root=False, granted=True, manager="KernelSU")
        mgr = modules.manager(adb)
        self.assertEqual(mgr.name, "KernelSU")
        self.assertTrue(mgr.can_install)


class TestListToggle(unittest.TestCase):
    def test_list_reads_modules(self):
        adb = FakeAndroid(
            root=False, granted=True,
            modules={"zygisk-next": "name=Zygisk Next\nversion=1.0\n"},
        )
        mods = modules.list_modules(adb)
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0].name, "Zygisk Next")

    def test_toggle_writes_disable_flag(self):
        adb = FakeAndroid(root=False, granted=True)

        ok, msg = modules.toggle(adb, "demo", False)
        self.assertTrue(ok)
        self.assertIn("禁用", msg)
        self.assertTrue(any(c[0] == "su" and "disable" in c[2] for c in adb.calls))

        ok, msg = modules.toggle(adb, "demo", True)
        self.assertTrue(ok)
        self.assertIn("启用", msg)

    def test_bad_module_name_rejected(self):
        adb = FakeAndroid(root=False, granted=True)
        for name in ("../evil", "a/b", "", ".."):
            with self.assertRaises(modules.ModuleError):
                modules.toggle(adb, name, False)


class TestInstall(unittest.TestCase):
    def test_install_pushes_and_calls_manager(self):
        adb = FakeAndroid(root=False, granted=True, manager="Magisk")
        with local_tmp() as td:
            z = Path(td) / "mod.zip"
            z.write_bytes(b"PK\x03\x04fake")
            ok, msg = modules.install(adb, str(z))
        self.assertTrue(ok, msg)
        self.assertIn("已安装", msg)

    def test_install_requires_zip(self):
        adb = FakeAndroid(root=False, granted=True)
        with local_tmp() as td:
            f = Path(td) / "mod.apk"
            f.write_bytes(b"x")
            with self.assertRaises(modules.ModuleError):
                modules.install(adb, str(f))

    def test_install_missing_file(self):
        adb = FakeAndroid(root=False, granted=True)
        with self.assertRaises(modules.ModuleError):
            modules.install(adb, "does-not-exist-mod.zip")


if __name__ == "__main__":
    unittest.main()
