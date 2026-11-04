"""Iris —— 面向 Android 设备的多功能工具链（核心库 + CLI）。

设计原则（与上游 VioletToolBox 的主要区别）：

1. 计划式执行：任何改动设备的操作先产出 plan，再 apply；plan 可 --dry-run 审阅。
2. 结构化结果：一切外部命令返回 ProcResult，靠退出码判断成败，不靠字符串匹配。
3. 探测优先：设备路径/槽位/分区布局一律探测后写入 profile，功能模块只读 profile。
4. 无 UI 依赖：core 层不 import 任何界面库，CLI 只是第一个前端。
"""

__version__ = "0.3.0"
__all__ = ["__version__"]
