# Iris 手机版（APK）

在手机上直接跑的玩机工具箱。和 PC 版共用一套设计语言，但实现是纯 Android：
WebView 做界面，Java 做“手”（root 命令、分区 dd、模块、文件、应用）。

## 功能

| 页面 | 能做什么 |
|---|---|
| 终端 | 执行设备命令，可切换 root；↑↓ 翻历史，显示退出码/耗时 |
| 分区 | 读 by-name 分区表与真实大小；`dd` 备份到应用目录（带 SHA-256 与进度）；选镜像还原并回读校验 |
| 模块 | 识别 Magisk / KernelSU / APatch；列出模块、启用/禁用、标记卸载、安装 zip |
| 文件 | root 浏览 `/sdcard`、`/data`；文本预览；导出到任意目录（SAF） |
| 应用 | 第三方/全部应用；冻结、解冻、清数据、卸载（当前用户） |

第一次打开时会请求 su：Magisk/KernelSU/APatch 会弹授权框，点允许即可。
如果误点了拒绝，点右上角的 ROOT 徽标重新探测。

## 构建

依赖本机的 JDK 与 Android SDK（不需要 Gradle，也没有 AndroidX 依赖）：

```powershell
python android/build.py
```

产物：`dist/Iris-<version>-android.apk`

链路：`aapt2 compile/link → javac → jar → d8 → zipalign → apksigner`。
脚本会自动寻找 Android Studio 自带的 jbr 与 SDK；找不到时用 `JAVA_HOME` /
`ANDROID_HOME` 指定。

签名密钥在 `android/keystore/iris.jks`（密码 `iris123456`，别名 `iris`）。
**同一个密钥才能覆盖升级**，换机发布时记得把它一起带走或换成自己的。

## 测试

```powershell
node android/test/ui_smoke.js
```

用最小 DOM 桩 + 假 Android 桥把五个页面的渲染、终端、备份、模块开关都跑一遍，
不需要真机。真机上的 su、dd、模块安装仍需自行验证。

## 已知边界

- 手机上做不了 `fastboot` / EDL：那需要电脑端 USB 与引导文件。
- 分区备份默认写到 `Android/data/com.iris.toolbox/files/backups`；
  Android 11+ 文件管理器看不进去，用“导出备份”存到 Downloads。
- 还原镜像会先复制到应用缓存，超大镜像（比如整个 super）要留足空间。
- 只对应用自身能读到的路径免 root；`/data`、`/system` 需要 su。
