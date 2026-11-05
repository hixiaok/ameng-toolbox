# A梦工具箱 0.5.1 发布：内置 adb / fastboot / scrcpy 的安卓桌面工具箱

> 一个面向 Android 设备的 Windows 桌面工具箱，原生 WPF 界面，不是网页套壳。

## 它能做什么

- **仪表盘**：设备信息、电量 / 存储 / 内存、详细参数、截图、录屏、抓日志、无线调试；
- **快捷指令**：重启到系统 / Recovery / Bootloader / Fastbootd、屏幕常亮、动画缩放、触摸显示、重启 ADB、打开设备管理器；
- **刷机**：常规镜像刷入、小米整包线刷（`flash_all*.bat`）、Bootloader 解锁 / 回锁、双清、分区表备份还原；
- **Fastboot**：检测设备、镜像预检、刷入分区、重启到系统 / bootloader / fastbootd；
- **ROOT**：root 状态、备份 boot / init_boot / vbmeta、打开 Magisk / KernelSU；
- **投屏**：内置 scrcpy，可选分辨率、码率、窗口置顶；
- **基带备份**：modem / fsg / persist 等分区备份与还原；
- **模块**：Magisk / KernelSU 模块启停；
- **应用**：全部 / 第三方应用、冻结、解冻、清数据、提取 APK、卸载、安装 APK；
- **终端**：设备 `adb shell` 或本机 CMD，root 开关、历史记录。

![界面](https://gitee.com/hixiaok/ameng-toolbox/raw/main/docs/screenshot-0.5.1.png)

## 下载

- GitHub：https://github.com/hixiaok/ameng-toolbox/releases/tag/v0.5.1
- Gitee：https://gitee.com/hixiaok/ameng-toolbox/releases/tag/v0.5.1

文件名：

- `AMengToolbox-0.5.1-setup.exe`：NSIS 安装包，安装到 Program Files，带开始菜单 / 桌面快捷方式和卸载项；
- `AMengToolbox-0.5.1-portable.zip`：绿色版，解压运行 `A梦工具箱.exe`。

## 运行要求

- Windows 10 / 11 + .NET Framework 4.8（系统自带）；
- 需要管理员权限；
- 安装包未做数字签名，SmartScreen 提示“未知发布者”时点「更多信息 → 仍要运行」。

## 关于刷机

刷机、解锁、回锁、双清都有风险，不同机型分区和脚本差异很大。工具只负责调用命令，**刷错分区或脚本可能导致无法开机**，请确认自己知道后果再操作。

## 开源与第三方

源码以 GPL-3.0 开源：

- GitHub：https://github.com/hixiaok/ameng-toolbox
- Gitee：https://gitee.com/hixiaok/ameng-toolbox

使用的第三方组件：

- [scrcpy](https://github.com/Genymobile/scrcpy) 5.0.1（Apache-2.0）——投屏；
- Android SDK Platform Tools（adb / fastboot，Apache-2.0）——设备通信；
- .NET Framework / WPF（MIT）——界面与运行环境；
- [NSIS](https://nsis.sourceforge.io/) 3.10（zlib / libpng）——安装程序。

## 作者的话

我是一个普通的安卓爱好者，不是专业开发，这个工具箱是我边学边做出来的。初衷很简单：把平时刷机、装模块、传文件、投屏常用的操作集中到一个窗口里，少敲点命令，也少在几个工具之间来回切换。

很多功能我还没有在足够多的机型上实测过，不敢保证每个都好用；如果你遇到问题，请把机型、系统版本、操作步骤和截图发到我的邮箱，我会尽力修复，也会继续更新。

开发过程中参考和借鉴了紫罗兰工具箱、搞机助手等工具的思路，也使用了 scrcpy、adb/fastboot 等开源项目，这里谢谢各位作者。

- QQ：17513499
- 邮箱：jinkaizhe2@gmail.com
