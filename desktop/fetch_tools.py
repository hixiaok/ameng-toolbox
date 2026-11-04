"""下载构建/运行需要的第三方工具：scrcpy 与 Android platform-tools。

用法：
    python desktop/fetch_tools.py
"""
import io
import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
TOOLS = DESKTOP / "tools"
PT = ROOT / "platform-tools"


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ameng-toolbox"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def fetch_scrcpy() -> None:
    api = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
    data = json.loads(download(api).decode("utf-8"))
    asset = next(
        a for a in data["assets"]
        if "win64" in a["name"] and a["name"].endswith(".zip")
    )
    print("scrcpy:", asset["name"])
    zip_data = zipfile.ZipFile(io.BytesIO(download(asset["browser_download_url"])))
    TOOLS.mkdir(parents=True, exist_ok=True)
    for name in zip_data.namelist():
        if name.endswith("/"):
            continue
        parts = name.split("/", 1)
        if len(parts) != 2:
            continue
        dest = TOOLS / parts[1]
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(zip_data.read(name))
    print("  ->", TOOLS)


def fetch_platform_tools() -> None:
    url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    print("platform-tools:", url)
    zip_data = zipfile.ZipFile(io.BytesIO(download(url)))
    tmp = ROOT / ".tmp-platform-tools"
    if tmp.exists():
        shutil.rmtree(tmp)
    zip_data.extractall(tmp)
    src = tmp / "platform-tools"
    if src.is_dir():
        if PT.exists():
            shutil.rmtree(PT)
        shutil.copytree(src, PT)
    shutil.rmtree(tmp, ignore_errors=True)
    print("  ->", PT)


if __name__ == "__main__":
    fetch_scrcpy()
    fetch_platform_tools()
