#!/usr/bin/env python3
"""
publish.py — commit docs/data 嘅新數據再 push，GitHub Pages 會自動更新。

    python publish.py                 # 有變化先 commit，冇變化乜都唔做
    python publish.py --message "..."
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent


def git(*a, check=True):
    p = subprocess.run(["git", *a], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and p.returncode:
        raise SystemExit(f"git {' '.join(a)} 失敗：\n{p.stdout}{p.stderr}")
    return p.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", default="")
    a = ap.parse_args()
    if not git("status", "--porcelain"):
        print("冇嘢變，唔使 push")
        return 0
    git("add", "-A")
    msg = a.message or f"data: {datetime.now():%Y-%m-%d %H:%M}"
    git("commit", "-m", msg)
    git("push")
    print(f"已 push：{msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
