"""构建 Iris 手机版 APK：只用 SDK 自带工具，不需要 Gradle / AndroidX。

链路：
    aapt2 compile/link  ->  javac (JDK 21 用 -source 8)  ->  d8  ->  zipalign  ->  apksigner

为什么不用 Gradle：这台机器没有网络，AGP 依赖拉不下来；本项目也刻意不用
AndroidX，纯 framework API，编译链就是四条命令，出了问题一眼能看出是哪步。

用法：  python android/build.py
产物：  dist/Iris-<version>-android.apk
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # android/
REPO = ROOT.parent
BUILD = ROOT / "build"
DIST = REPO / "dist"
VERSION = "0.3.0"
KEYSTORE = ROOT / "keystore" / "iris.jks"
KS_PASS = "iris123456"
KS_ALIAS = "iris"

JDK_CANDIDATES = [
    os.environ.get("JAVA_HOME"),
    r"D:\软件\android studio\jbr",
    r"C:\Program Files\Android\Android Studio\jbr",
    r"C:\Program Files\Java\jdk-21",
    r"C:\Program Files\Eclipse Adoptium\jdk-21",
]
SDK_CANDIDATES = [
    os.environ.get("ANDROID_HOME"),
    os.environ.get("ANDROID_SDK_ROOT"),
    r"C:\Users\admin\AppData\Local\Android\Sdk",
    r"D:\Android\Sdk",
]


def find_jdk() -> Path:
    for cand in JDK_CANDIDATES:
        if cand and (Path(cand) / "bin" / "javac.exe").is_file():
            return Path(cand)
    raise SystemExit("找不到 JDK：设置 JAVA_HOME，或安装 Android Studio（自带 jbr）")


def find_sdk() -> Path:
    for cand in SDK_CANDIDATES:
        if cand and (Path(cand) / "build-tools").is_dir():
            return Path(cand)
    raise SystemExit("找不到 Android SDK：设置 ANDROID_HOME")


def latest(dir_: Path, pattern: str) -> Path:
    items = sorted(dir_.glob(pattern), key=lambda p: [int(x) if x.isdigit() else x for x in p.name.replace("-", ".").split(".")])
    if not items:
        raise SystemExit(f"{dir_} 下没有 {pattern}")
    return items[-1]


def run(argv: list[str], *, env: dict | None = None, quiet: bool = False) -> None:
    print("  $", " ".join(str(a) for a in argv[:6]) + (" …" if len(argv) > 6 else ""))
    res = subprocess.run([str(a) for a in argv], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(f"命令失败（{res.returncode}）：{argv[0]}")
    if not quiet and res.stdout.strip():
        print("    " + res.stdout.strip()[:400].replace("\n", "\n    "))


def make_keystore(keytool: Path, env: dict) -> None:
    if KEYSTORE.is_file():
        return
    KEYSTORE.parent.mkdir(parents=True, exist_ok=True)
    run([
        keytool, "-genkeypair", "-keystore", KEYSTORE, "-alias", KS_ALIAS,
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", KS_PASS, "-keypass", KS_PASS,
        "-dname", "CN=Iris, OU=Toolbox, O=Iris, L=CN, ST=CN, C=CN",
    ], env=env, quiet=True)


def collect_sources() -> list[Path]:
    files = sorted(ROOT.glob("src/**/*.java")) + sorted((BUILD / "gen").rglob("*.java"))
    if not files:
        raise SystemExit("没有 Java 源码")
    return files


def build() -> Path:
    jdk = find_jdk()
    sdk = find_sdk()
    bt = latest(sdk / "build-tools", "*/aapt2.exe").parent
    platform = latest(sdk / "platforms", "android-*")
    android_jar = platform / "android.jar"
    print(f"JDK      {jdk}")
    print(f"SDK      {sdk}")
    print(f"build    {bt.name}    platform {platform.name}")

    env = os.environ.copy()
    env["JAVA_HOME"] = str(jdk)
    env["PATH"] = f"{jdk / 'bin'};{env.get('PATH', '')}"

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    (BUILD / "gen").mkdir()
    (BUILD / "classes").mkdir()
    (BUILD / "dex").mkdir()

    aapt2 = bt / "aapt2.exe"
    res_zip = BUILD / "res.zip"
    res_dir = ROOT / "res"
    link_args = [
        aapt2, "link", "-o", BUILD / "base.apk",
        "-I", android_jar,
        "--manifest", ROOT / "AndroidManifest.xml",
        "--java", BUILD / "gen",
        "--min-sdk-version", "24",
        "--target-sdk-version", "34",
        "--version-code", "1",
        "--version-name", VERSION,
    ]
    if res_dir.is_dir():
        run([aapt2, "compile", "--dir", res_dir, "-o", res_zip])
        link_args += ["-R", res_zip]
    assets = ROOT / "assets"
    if assets.is_dir():
        link_args += ["-A", assets]
    run(link_args)

    sources = collect_sources()
    javac = jdk / "bin" / "javac.exe"
    run([
        javac, "-encoding", "UTF-8", "-source", "8", "-target", "8", "-Xlint:-options",
        "-bootclasspath", android_jar, "-classpath", android_jar,
        "-d", BUILD / "classes", *sources,
    ], env=env)

    d8 = bt / "d8.bat"
    classes_jar = BUILD / "classes.jar"
    run([jdk / "bin" / "jar.exe", "--create", "--file", classes_jar, "-C", BUILD / "classes", "."], env=env, quiet=True)
    run([d8, "--release", "--lib", android_jar, "--min-api", "24",
         "--output", BUILD / "dex", classes_jar], env=env)

    merged = BUILD / "merged.apk"
    with zipfile.ZipFile(BUILD / "base.apk") as src, zipfile.ZipFile(merged, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.write(BUILD / "dex" / "classes.dex", "classes.dex")

    aligned = BUILD / "aligned.apk"
    run([bt / "zipalign.exe", "-f", "-p", "4", merged, aligned])

    make_keystore(jdk / "bin" / "keytool.exe", env)
    out = DIST / f"Iris-{VERSION}-android.apk"
    DIST.mkdir(exist_ok=True)
    run([
        bt / "apksigner.bat", "sign",
        "--ks", KEYSTORE, "--ks-key-alias", KS_ALIAS,
        "--ks-pass", f"pass:{KS_PASS}", "--key-pass", f"pass:{KS_PASS}",
        "--out", out, aligned,
    ], env=env, quiet=True)
    run([bt / "apksigner.bat", "verify", "--print-certs", out], env=env, quiet=True)
    return out


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    out = build()
    size = out.stat().st_size / 1024
    print(f"\n✓ {out}  ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
