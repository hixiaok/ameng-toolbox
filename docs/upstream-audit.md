# 上游代码审计笔记

对 [VioletToolBox](https://github.com/Smart-Paocai/VioletToolBox)（GPL-3.0）关键算法部分的阅读记录。
目的：抽出**格式事实**用于重写，同时记下不能照搬的地方。

审计范围目前覆盖 LP 元数据；AVB、payload 待补。

## 1. LP 元数据格式（已核对）

来源：`EdlDynamicSuper/LpMake/LpMakeConstants.cs`、`LpMakeStructs.cs`、
`EdlVersionInfo/LpMetadataParser.cs`，与 AOSP `liblp/metadata_format.h` 一致。

| 结构 | 尺寸 | 字段 |
|---|---|---|
| geometry | 52（占 4096 区块） | magic `0x616C4467`、struct_size、checksum[32]、metadata_max_size、metadata_slot_count、logical_block_size |
| header v10 | 128 | magic `0x414C5030`、major/minor、header_size、header_checksum[32]、tables_size、tables_checksum[32]、4×表描述符(12B) |
| header v12 | 256 | 上述 + flags(4) + reserved(124) |
| partition | 52 | name[36]、attributes、first_extent_index、num_extents、group_index |
| extent | 24 | num_sectors(8)、target_type(4)、target_data(8)、target_source(4) |
| group | 48 | name[36]、flags、maximum_size(8) |
| block_device | 64 | first_logical_sector(8)、alignment、alignment_offset、size(8)、name[36]、flags |

- 表顺序固定：partitions、extents、groups、block_devices。
- 表描述符的 `offset` 相对于 **header 起始位置 + header_size**。
- checksum 都是 SHA256，计算前把 checksum 字段本身置零。
- `target_type`：0=linear、1=zero；`target_data` 为物理扇区（512B）。

## 2. 上游实现的问题

**a. metadata 偏移硬编码**
`LpMetadataParser.cs:14` 写死 `METADATA_OFFSET = 4096 * 3`（12288）。
不同厂商的 super 预留区并不统一，geometry 与 header 的落点会因此漂移。
我们的做法：按 4096 对齐扫描 magic，geometry 找 `0x616C4467`、
header 找 `0x414C5030`，找到即用。

**b. 完全不校验 checksum**
解析器读完 header 直接用，checksum 字段跳着注释过去。
于是坏镜像会被当成正常分区表，错误要等到刷写阶段才暴露。
我们的做法：校验 geometry / header / tables 三段，**失败只告警不中断**——
部分厂商镜像 checksum 本身就是错的，硬失败会让整片功能不可用。

**c. extent 表边界判断用了错常量**
`LpMetadataParser.cs:60`：`if (off + 28 > metaData.Length) break;`
extent 实际 24 字节，用 28 会提前截断最后一条。属于保守错误，但确实少解析。

**d. 同一份格式实现了两遍**
`EdlDynamicSuper/LpMake/`（构造）与 `EdlVersionInfo/LpMetadataParser.cs`（读取）
各写一套结构体，字段尺寸靠注释维持一致，已经出现常量分叉的苗头。

**e. 构造侧默认值写死**
`LpMakeConstants`：默认组 `default`、对齐 1MiB、块大小 4096。
合包时如果源 super 用了别的对齐，生成的 metadata 会和设备不匹配。
我们生成时必须从源镜像读回这些值，而不是取默认。

## 3. 我们的对应实现

| 上游 | 本项目 |
|---|---|
| `EdlVersionInfo/LpMetadataParser.cs` | [`iris/core/image/lp.py`](../iris/core/image/lp.py) |
| （无 sparse 处理） | [`iris/core/image/sparse.py`](../iris/core/image/sparse.py) |

验证方式：`tests/image_fixture.py` 按 AOSP 规则生成带正确 checksum 的
super 镜像，`tests/test_lp.py` 覆盖正常解析、迁移偏移、坏 checksum、垃圾数据四种情况。

## 4. 待审

- `Avb/NativeAvbRebuilder.cs`（1271 行）：链式/非链式/AOSP/联想签名
- `Payload_Dumper_C#/Core/*`：payload 解析与 bsdiff 应用
- `MainWindow.EdlFlash.cs`（11582 行）：firehose 会话时序
