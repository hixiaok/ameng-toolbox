"""核心层：不依赖任何 UI，可独立被脚本/测试调用。"""

from . import adb, diag, errors, proc, profile  # noqa: F401

__all__ = ["adb", "diag", "errors", "proc", "profile"]
