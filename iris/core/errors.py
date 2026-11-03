"""统一异常与错误分类。

上游把所有失败都塞进一个字符串日志里，调用方只能靠肉眼判断。
这里给每类失败一个明确类型，CLI 层据此决定退出码。
"""

from __future__ import annotations


class IrisError(Exception):
    """所有可预期错误的基类。"""

    exit_code = 1

    def __init__(self, message: str, *, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message


class ToolMissing(IrisError):
    """缺少外部依赖（adb / fastboot / 驱动）。"""

    exit_code = 3


class NoDevice(IrisError):
    """没有可用设备，或设备状态不对（unauthorized / offline）。"""

    exit_code = 4


class PermissionDenied(IrisError):
    """需要 root / 需要解锁，但当前设备不满足。"""

    exit_code = 5


class UnsupportedDevice(IrisError):
    """设备或固件不在支持范围内。"""

    exit_code = 6


class InvalidImage(IrisError):
    """镜像格式不符合预期（GPT / super / payload / sparse）。"""

    exit_code = 7


class PlanRejected(IrisError):
    """预检拒绝执行（机型不符、ARB 熔断、空间不足等）。"""

    exit_code = 8
