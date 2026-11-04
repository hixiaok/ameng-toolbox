"""打一个 Windows 便携版：内置 Python 运行时 + adb/fastboot，解压双击即用。

为什么不用 PyInstaller：本项目零第三方依赖，但打包机可能没有网络装
PyInstaller。直接复制当前 Python 的运行时（去掉 test/tkinter/site-packages）
再塞进 iris 包，得到的东西同样能脱离安装环境运行，且体积可控（约 35MB）。

用法：  python tools/build_portable.py
产物：  dist/Iris-v0.3.0/        （文件夹，双击 Iris.bat）
        dist/Iris-v0.3.0-portable.zip
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from iris import __version__  # noqa: E402

PREFIX = Path(sys.base_prefix)
DIST = ROOT / "dist"
NAME = f"Iris-v{__version__}"
OUT = DIST / NAME

EXCLUDE_LIB = {
    "test", "idlelib", "tkinter", "turtledemo", "venv", "ensurepip",
    "site-packages", "lib2to3", "__pycache__", "distutils", "pydoc_data",
}
EXCLUDE_DLLS = {
    "_tkinter.pyd", "tcl86t.dll", "tk86t.dll",
    "_testcapi.pyd", "_testinternalcapi.pyd", "_testmultiphase.pyd",
    "_testsinglephase.pyd", "xxlimited.pyd", "xxlimited_35.pyd",
}
PLATFORM_FILES = ("adb.exe", "fastboot.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "NOTICE.txt", "source.properties")

README = """Iris v{version} —— Android 设备工具链（便携版）

【怎么用】
1. 解压整个文件夹到任意位置（路径不要有中文以外的奇怪符号也行，尽量不要放 C:\\Program Files）。
2. 手机打开「开发者选项 → USB 调试」，用数据线连电脑，手机上点「允许」。
3. 双击 Iris.bat，浏览器会自动打开界面；没打开就手动访问 http://127.0.0.1:8765/
4. 需要 root 的功能（分区表、备份、还原、模块管理、root 文件浏览），
   手机必须已 root（Magisk / KernelSU / APatch），并在管理器里给 su 授权。

【里面有什么】
  Iris.bat            图形界面（本地网页，只监听 127.0.0.1）
  Iris命令行.bat      命令行入口，等价于 iris 命令
  runtime\\            内置 Python 3.13 运行时，不用另装
  platform-tools\\      adb / fastboot
  backups\\            分区备份默认保存到这里
  data\\shots\\         截图、录屏、拉取的文件

【注意】
* 分区备份/还原、fastboot 刷入都是写操作，写错分区会变砖。每次写之前界面会
  先给一份计划（大小、哈希、风险），看清楚再点执行。
* 只支持 Windows 10/11 64 位。
* 杀毒软件可能对 adb.exe 报毒，这是 platform-tools 的通病，加白名单即可。
* 软件按 GPL-3.0 发布；platform-tools 归 Google，遵循其 NOTICE。

版本：v{version}
"""


def _ignore_lib(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in EXCLUDE_LIB or n.endswith((".pyc", ".pyo"))}


def _copy_runtime() -> None:
    runtime = OUT / "runtime"
    runtime.mkdir(parents=True)

    for name in ("python.exe", "pythonw.exe", "python3.dll", "python313.dll"):
        src = PREFIX / name
        if src.is_file():
            shutil.copy2(src, runtime / name)
    for dll in PREFIX.glob("vcruntime*.dll"):
        shutil.copy2(dll, runtime / dll.name)

    shutil.copytree(PREFIX / "DLLs", runtime / "DLLs", ignore=shutil.ignore_patterns(*EXCLUDE_DLLS, "*.lib", "*.exp"))
    shutil.copytree(PREFIX / "Lib", runtime / "Lib", ignore=_ignore_lib)

    site = runtime / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "iris",
        site / "iris",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _copy_platform_tools() -> None:
    src = ROOT / "platform-tools"
    if not src.is_dir():
        src = ROOT.parent / "platform-tools"
    if not src.is_dir():
        print("! 没有找到 platform-tools，便携版不会带 adb")
        return
    dst = OUT / "platform-tools"
    dst.mkdir()
    for name in PLATFORM_FILES:
        f = src / name
        if f.is_file():
            shutil.copy2(f, dst / name)
    print(f"platform-tools: {len(list(dst.iterdir()))} 个文件")


def _write_text(path: Path, text: str, *, crlf: bool = False, encoding: str = "utf-8") -> None:
    data = text.replace("\n", "\r\n") if crlf else text
    path.write_bytes(data.encode(encoding))


def _write_launchers() -> None:
    _write_text(OUT / "Iris.bat", f"""@echo off
chcp 65001 >nul
title Iris v{__version__}
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "IRIS_SHOTS=%~dp0data\\shots"
set "IRIS_BACKUP_DIR=%~dp0backups"
if not exist "%~dp0data\\shots" mkdir "%~dp0data\\shots"
if not exist "%~dp0backups" mkdir "%~dp0backups"

echo ============================================================
echo   Iris v{__version__} 正在启动
echo   浏览器会自动打开；没有的话访问 http://127.0.0.1:8765/
echo   关闭本窗口即退出
echo ============================================================
echo.

"%~dp0runtime\\python.exe" -m iris gui --port 8765
echo.
echo 已退出（代码 %errorlevel%）
pause
""", crlf=True)

    _write_text(OUT / "Iris命令行.bat", """@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
"%~dp0runtime\\python.exe" -m iris %*
""", crlf=True)

    _write_text(OUT / "使用说明.txt", README.format(version=__version__), crlf=True, encoding="utf-8-sig")


def _verify() -> bool:
    exe = OUT / "runtime" / "python.exe"
    code = (
        "import iris, json, http.server, hashlib, email, urllib.request, sqlite3, ssl;"
        "print('iris', iris.__version__, 'ok')"
    )
    res = subprocess.run([str(exe), "-c", code], capture_output=True, text=True, timeout=120)
    print((res.stdout or "").strip())
    if res.returncode != 0:
        print((res.stderr or "").strip()[-1500:])
    return res.returncode == 0


def _zip() -> Path:
    target = DIST / f"{NAME}-portable"
    archive = shutil.make_archive(str(target), "zip", root_dir=DIST, base_dir=NAME)
    return Path(archive)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    print(f"打包 {NAME} -> {OUT}")
    _copy_runtime()
    _copy_platform_tools()
    (OUT / "data" / "shots").mkdir(parents=True, exist_ok=True)
    (OUT / "backups").mkdir(parents=True, exist_ok=True)
    _write_launchers()

    if not _verify():
        print("✗ 内置运行时自检失败")
        return 1

    archive = _zip()
    size_mb = archive.stat().st_size / 1024 / 1024
    print(f"✓ {archive}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
