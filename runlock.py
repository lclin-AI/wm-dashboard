#!/usr/bin/env python3
"""
跨 process 鎖，畀 collect.py 同 publish.py 共用。

點解要：`WM Dashboard Fast`（每 5 分鐘）同 `WM Dashboard Carline`（每日 06:30）
兩個 task 撞正 06:30 一齊跑，改同一批 docs/data/*.json、又一齊 git commit，
邊個搶輸就 exit 1。2026-09-18 至 09-21 車線連續四日冇更新就係咁 ——
而且係靜靜雞失敗，dashboard 照顯示舊數，冇任何提示。

用 mkdir（檔案系統層面 atomic）做鎖。殘鎖過 STALE_MIN 自動搶返，
唔怕有 process 死咗鎖死晒。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = HERE / ".runlock"
STALE_MIN = 20


class RunLock:
    def __init__(self, wait_s: int = 300):
        self.wait_s = wait_s

    def __enter__(self):
        deadline = time.time() + self.wait_s
        while True:
            try:
                LOCK.mkdir()
                (LOCK / "pid").write_text(str(os.getpid()), encoding="utf-8")
                return self
            except FileExistsError:
                try:
                    age = (time.time() - LOCK.stat().st_mtime) / 60
                    if age > STALE_MIN:
                        print(f"  發現殘鎖（{age:.0f} 分鐘前），接手")
                        for f in LOCK.iterdir():
                            f.unlink(missing_ok=True)
                        LOCK.rmdir()
                        continue
                except FileNotFoundError:
                    continue          # 啱啱畀人放咗，再試
                if time.time() > deadline:
                    raise SystemExit(
                        f"等咗 {self.wait_s}s 都攞唔到 {LOCK.name} — "
                        "有另一個 collect/publish 行緊，今次唔做")
                time.sleep(2)

    def __exit__(self, *exc):
        try:
            for f in LOCK.iterdir():
                f.unlink(missing_ok=True)
            LOCK.rmdir()
        except FileNotFoundError:
            pass
