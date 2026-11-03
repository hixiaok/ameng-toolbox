from __future__ import annotations

import sys
import unittest

from iris.core import proc


class TestProc(unittest.TestCase):
    def test_ok(self):
        r = proc.run([sys.executable, "-c", "print('hi')"])
        self.assertTrue(r.ok)
        self.assertEqual(r.out.strip(), "hi")
        self.assertEqual(r.code, 0)

    def test_nonzero_is_not_exception(self):
        r = proc.run([sys.executable, "-c", "import sys; sys.exit(3)"])
        self.assertFalse(r.ok)
        self.assertEqual(r.code, 3)

    def test_missing_binary(self):
        r = proc.run(["iris-definitely-not-a-real-binary"])
        self.assertEqual(r.code, proc.EXIT_NOT_FOUND)
        self.assertIn("找不到", r.err)

    def test_timeout(self):
        r = proc.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3)
        self.assertTrue(r.timed_out)
        self.assertEqual(r.code, proc.EXIT_TIMEOUT)
        self.assertGreater(r.duration, 0.2)

    def test_stderr_captured_separately(self):
        r = proc.run([sys.executable, "-c", "import sys; sys.stderr.write('bad\\n'); sys.exit(1)"])
        self.assertEqual(r.err.strip(), "bad")
        self.assertEqual(r.out, "")

    def test_describe_contains_exit_code(self):
        r = proc.run([sys.executable, "-c", "import sys; sys.exit(9)"])
        self.assertIn("9", r.describe())


if __name__ == "__main__":
    unittest.main()
