"""子进程执行层。

上游（VioletToolBox）大量用 `Process.Start` + 字符串拼接 + `output.Contains("failed")`
判断成败，于是 dd 报 "No such file or directory" 时三个关键词都不匹配，被误判为成功
（见上游 issue #4）。本模块的约定：

* 一律 argv 列表，不经 shell，除非显式调用 `run_shell`。
* 非零退出码不抛异常，返回 ProcResult，由调用方决定是否致命。
* 失败分得很细：找不到可执行文件（127）、超时（124）、被信号杀（-N）。
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Sequence

DEFAULT_TIMEOUT = 30.0

# 与 shell 习惯保持一致：命令不存在、超时
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124


@dataclass(frozen=True)
class ProcResult:
    """一次外部命令的完整结果。"""

    argv: tuple[str, ...]
    code: int
    out: str
    err: str
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out

    @property
    def stdout_lines(self) -> list[str]:
        return [ln for ln in self.out.splitlines() if ln.strip()]

    def first_line(self) -> str:
        lines = self.stdout_lines
        return lines[0] if lines else ""

    def describe(self) -> str:
        """一行摘要，用于日志。"""
        cmd = " ".join(self.argv)
        if self.timed_out:
            return f"{cmd} -> 超时({self.duration:.1f}s)"
        if self.code != 0:
            tail = (self.err or self.out).strip().splitlines()
            detail = tail[-1] if tail else ""
            return f"{cmd} -> 退出码 {self.code}{': ' + detail if detail else ''}"
        return f"{cmd} -> ok({self.duration:.1f}s)"


def run(
    argv: Sequence[str],
    *,
    timeout: float | None = DEFAULT_TIMEOUT,
    stdin: str | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> ProcResult:
    """执行命令，永不抛异常（除了 KeyboardInterrupt / 参数错误）。"""
    argv = tuple(str(a) for a in argv)
    started = time.monotonic()

    full_env = None
    if env:
        full_env = os.environ.copy()
        full_env.update(env)

    try:
        proc = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=full_env,
            check=False,
        )
    except FileNotFoundError:
        return ProcResult(
            argv=argv,
            code=EXIT_NOT_FOUND,
            out="",
            err=f"找不到可执行文件：{argv[0]}",
            duration=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        def _as_text(v: bytes | str | None) -> str:
            if v is None:
                return ""
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else v

        return ProcResult(
            argv=argv,
            code=EXIT_TIMEOUT,
            out=_as_text(exc.stdout),
            err=_as_text(exc.stderr) or f"超时 {timeout}s",
            duration=time.monotonic() - started,
            timed_out=True,
        )
    except OSError as exc:
        return ProcResult(
            argv=argv,
            code=EXIT_NOT_FOUND,
            out="",
            err=f"无法启动 {argv[0]}：{exc}",
            duration=time.monotonic() - started,
        )

    return ProcResult(
        argv=argv,
        code=proc.returncode,
        out=proc.stdout or "",
        err=proc.stderr or "",
        duration=time.monotonic() - started,
    )


def which(name: str) -> str | None:
    """在 PATH 中查找可执行文件；Windows 下自动补 .exe。"""
    import shutil

    return shutil.which(name)


def run_shell(command: str, *, timeout: float | None = DEFAULT_TIMEOUT) -> ProcResult:
    """显式走 shell 的逃生口。

    只应传给 shell 一次（例如需要管道/重定向的命令），不要用来拼接设备侧参数。
    设备侧命令请用 `Adb.shell(*args)`，参数以列表形式透传。
    """
    if os.name == "nt":
        return run(["cmd", "/c", command], timeout=timeout)
    return run(["/bin/sh", "-c", command], timeout=timeout)
