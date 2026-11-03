# Iris

面向 Android 设备的多功能工具链。**核心库 + CLI 优先**，零第三方依赖（只用 Python 标准库），Windows / Linux / macOS 都能跑。

> 定位：不是为了"再做一个刷机箱"，而是把刷机工具里最容易出错的部分——
> 设备差异、路径探测、执行顺序、失败判定——做成可测试、可脚本化、可审计的一层。

## 当前状态：v0.1（只读）

已实现：

| 能力 | 说明 |
|---|---|
| `iris doctor` | 环境自检：adb 版本、设备授权状态、驱动提示 |
| `iris devices` | 列出在线设备 |
| `iris info` | 设备画像：机型、SoC、A/B 槽位、安全补丁、by-name 根路径、分区表 |
| `iris gpt <img>` | 离线解析 GPT：主/备表、CRC 校验、分区起止与大小 |

未实现（见路线图）：payload 解包、super 合并、AVB 签名、fastboot 刷写、EDL。

## 快速开始

```powershell
python -m iris doctor
python -m iris devices
python -m iris info --verbose
python -m iris gpt .tmp/demo_gpt.img
```

`adb` 查找顺序：`--adb` 参数 → `IRIS_ADB` 环境变量 → `PATH` → 上溯各级目录下的 `platform-tools/adb.exe`。

## 四条设计原则

上游 [VioletToolBox](https://github.com/Smart-Paocai/VioletToolBox)（GPL-3.0）功能很全，但有四个结构性缺陷，本项目的骨架就是针对它们设计的：

**1. 计划式执行，而不是按钮直连**
任何会改动设备的操作，先生成一份 JSON 计划（机型、目标分区、风险、空间），`--dry-run` 可以只看不干。上游是点一下就跑，出问题只能翻日志。

**2. 结构化结果，而不是字符串匹配**
上游用 `output.Contains("failed")` 判断成败，于是 `dd` 报 `No such file or directory` 时三个关键词全不匹配，被误判为成功（[上游 issue #4](https://github.com/Smart-Paocai/VioletToolBox/issues/4)）。这里统一用退出码 + `ProcResult`，127 / 124 / 非零各有明确语义。

**3. 探测优先，而不是硬编码路径**
上游把 `/dev/block/bootdevice/by-name` 写死，玄戒 SoC 上整片功能失效。这里开机探测一次，把 by-name 根、块设备、槽位写进 `DeviceProfile` 缓存，功能只读 profile。

**4. 核心与界面分离**
上游 `MainWindow.xaml.cs` 有 947KB，逻辑和 UI 焊死，无法测试。这里的 `iris/core` 不 import 任何界面库，能脱离真机做单元测试。

## 目录结构

```
iris/
  cli.py              命令行入口
  core/
    proc.py           子进程执行（退出码语义、超时、编码容错）
    adb.py            adb 封装（参数列表透传，不拼 shell 字符串）
    profile.py        设备画像探测 + 缓存
    diag.py           环境自检
    errors.py         错误分类（对应不同退出码）
    partition/gpt.py  GPT 解析（纯离线）
    image/            镜像层（v0.2）
tests/                单元测试 + GPT 镜像夹具
```

## 测试

```powershell
python -m unittest discover -s tests -t . -v
```

测试不需要真机：`tests/gpt_fixture.py` 会造一张 CRC 合法（含备份表）的 GPT 镜像；`tests/test_profile.py` 用回放式假 adb 复刻上游 issue #4 的设备场景。

## 路线图

| 版本 | 内容 |
|---|---|
| v0.1 | 只读：自检、设备画像、GPT ✅ |
| v0.2 | 离线镜像引擎：payload 解包、sparse 互转、ext4/erofs 读 build.prop、super 解析与合并 |
| v0.3 | 写入：flash plan / dry-run / apply、fastboot 刷分区、AB 槽、super 重建、AVB 签名 |
| v0.4 | EDL（9008） |

## 许可

GPL-3.0。本项目参考了 VioletToolBox（GPL-3.0）的设计与算法知识，按 GPL-3.0 发布。
仓库内**不包含**任何第三方二进制（kptools、ksud、QSaharaServer、fh_loader 等），
需要时由用户自行提供或按哈希从官方渠道获取。
