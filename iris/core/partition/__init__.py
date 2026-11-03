"""分区层：GPT、LP metadata、super 布局。

全部是纯离线模块，不 import adb，便于用镜像夹具做单元测试。
"""

from . import gpt  # noqa: F401

__all__ = ["gpt"]
