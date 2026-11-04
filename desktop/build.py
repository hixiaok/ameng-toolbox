"""构建 Iris 桌面版（WPF 原生窗口，不是网页）。

用 .NET Framework 自带的 csc.exe 编译，不依赖 Visual Studio 或 dotnet SDK。
产物：dist/Iris-Desktop/Iris.exe（旁边带 adb 与 platform-tools）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # iris/
DESKTOP = ROOT / "desktop"
SRC = DESKTOP / "src"
DIST = Path(os.environ.get("IRIS_DESKTOP_OUT") or (ROOT / "dist" / "A梦工具箱"))
MANIFEST = Path(os.environ.get("IRIS_MANIFEST") or (DESKTOP / "src" / "app.manifest"))
FW = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319"
CSC = FW / "csc.exe"

PLATFORM_FILES = ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "fastboot.exe", "NOTICE.txt")


def run(args: list[str]) -> None:
    print("  $", " ".join(str(a) for a in args[:5]) + (" …" if len(args) > 5 else ""))
    res = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(f"命令失败（{res.returncode}）")


def make_icon() -> Path:
    ico = DESKTOP / "iris.ico"
    if ico.is_file():
        return ico
    py = Path(sys.executable)
    code = (
        "from PIL import Image, ImageDraw\n"
        "S=512\n"
        "img=Image.new('RGBA',(S,S),(0,0,0,0))\n"
        "d=ImageDraw.Draw(img)\n"
        "grad=Image.new('RGB',(S,S)); gd=ImageDraw.Draw(grad)\n"
        "for y in range(S):\n"
        "    t=y/S; gd.line([(0,y),(S,y)],fill=(int(63+(15-63)*t),int(140+(95-140)*t),int(255+(196-255)*t)))\n"
        "mask=Image.new('L',(S,S),0); ImageDraw.Draw(mask).rounded_rectangle([0,0,S-1,S-1],radius=112,fill=255)\n"
        "img.paste(grad,(0,0),mask)\n"
        "d=ImageDraw.Draw(img); w=84; cx=S//2\n"
        "d.rounded_rectangle([cx-92,128,cx+92,128+w],radius=24,fill='white')\n"
        "d.rounded_rectangle([cx-92,S-128-w,cx+92,S-128],radius=24,fill='white')\n"
        "d.rounded_rectangle([cx-w//2,128,cx+w//2,S-128],radius=24,fill='white')\n"
        f"img.save(r'{ico}', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])\n"
    )
    subprocess.run([str(py), "-c", code], check=True)
    return ico


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if not CSC.is_file():
        raise SystemExit(f"找不到 csc.exe：{CSC}")

    ico = make_icon()
    out_dir = DIST
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    exe = out_dir / "A梦工具箱.exe"

    refs = [
        FW / "WPF" / "PresentationFramework.dll",
        FW / "WPF" / "PresentationCore.dll",
        FW / "WPF" / "WindowsBase.dll",
        FW / "System.Xaml.dll",
        FW / "System.dll",
        FW / "System.Core.dll",
        FW / "System.Drawing.dll",
        FW / "System.Windows.Forms.dll",
    ]
    sources = sorted(str(p) for p in SRC.glob("*.cs"))
    args = [
        CSC, "/nologo", "/target:winexe", "/platform:anycpu", "/optimize+",
        f"/out:{exe}", f"/win32icon:{ico}", f"/win32manifest:{MANIFEST}",
    ] + [f"/reference:{r}" for r in refs] + sources
    run(args)

    shutil.copy2(ico, out_dir / "iris.ico")
    readme = DESKTOP / "README.md"
    if readme.is_file():
        shutil.copy2(readme, out_dir / "README.md")
    tools = ROOT / "platform-tools"
    if not tools.is_dir():
        tools = ROOT.parent / "platform-tools"
    if tools.is_dir():
        for name in PLATFORM_FILES:
            f = tools / name
            if f.is_file():
                shutil.copy2(f, out_dir / name)
    (out_dir / "shots").mkdir(exist_ok=True)
    (out_dir / "backups").mkdir(exist_ok=True)
    extra_tools = DESKTOP / "tools"
    if extra_tools.is_dir():
        shutil.copytree(extra_tools, out_dir / "tools", dirs_exist_ok=True)

    size = exe.stat().st_size / 1024
    print(f"✓ {exe}  ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
