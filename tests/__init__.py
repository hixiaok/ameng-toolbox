from __future__ import annotations

import contextlib
import shutil
import uuid
from pathlib import Path

# 用仓库内的临时目录，避开系统 temp 在沙箱下的 chmod 限制
TMP_ROOT = Path(__file__).resolve().parent.parent / ".tmp"


@contextlib.contextmanager
def local_tmp():
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    d = TMP_ROOT / uuid.uuid4().hex[:8]
    d.mkdir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
