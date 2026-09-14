#!/usr/bin/env python3
"""
collect.py — 砌 dashboard 要嘅三份 JSON，寫落 docs/data/。

    python collect.py --all
    python collect.py --timeslots --district      # 平，可以密啲跑
    python collect.py --carline                   # 重（~90 requests），一日一兩次

三份數據：
  timeslots.json  街市即日餸實際落單時段（open / cutoff / gone / none）
  district.json   OIX District Quota 用量（已使用 + 已使用臨時 / 配額）
  carline.json    OIX Delivery Zone 車線上咗未（☑ / ☐）

⚠ 時段嗰份**唔可以**喺度自己 call API。時段 API 跟 account 嘅 default 送貨地址，
  monitor 每輪都要 PUT 一次；兩個 process 一齊 PUT 會互相踢走對方揀嘅地址，
  讀到第啲街市嘅時段表 → 假 alert（2026-09-01 中過）。
  所以呢度只係讀 monitor 每輪寫低嘅 snapshot.json。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DATA = HERE / "docs" / "data"
MONITOR = Path(r"C:\Users\lclin\Downloads\wm-quota-monitor")
sys.path.insert(0, str(MONITOR))

DAYS = 15                      # D+0 .. D+14（lclin：要到 Today+14）


def _write(name: str, obj) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    print(f"  寫咗 docs/data/{name}")


def do_timeslots() -> None:
    src = MONITOR / "snapshot.json"
    if not src.exists():
        print("  ✗ 搵唔到 monitor 嘅 snapshot.json（monitor 未跑過新版？）")
        return
    d = json.loads(src.read_text(encoding="utf-8"))
    age = (datetime.now() - datetime.fromisoformat(d["updatedAt"])).total_seconds()
    d["ageSeconds"] = int(age)
    if age > 600:
        print(f"  ⚠ snapshot 已經 {int(age//60)} 分鐘冇更新，monitor 可能停咗")
    _write("timeslots.json", d)


def do_district() -> None:
    import oix_quota as Q
    today = datetime.now().date()
    cells = []
    for code in sorted(Q.DISTRICTS):
        for i in range(DAYS):
            day = today + timedelta(days=i)
            try:
                got = Q._fetch(code, day.strftime("%Y%m%d"))
            except Exception as e:
                print(f"  ✗ {code} {day}: {type(e).__name__}: {e}")
                continue
            for ts, (used, quota) in got.items():
                if ts not in Q.TS_LABEL:
                    continue
                cells.append({"code": code, "date": f"{day:%Y-%m-%d}", "plusDay": i,
                              "ts": ts, "slot": Q.TS_LABEL[ts],
                              "used": used, "quota": quota})
    _write("district.json", {"updatedAt": datetime.now().isoformat(timespec="seconds"),
                             "cells": cells})


def do_carline() -> None:
    import carline_check as C
    recs = C.scan(DAYS)
    lat = C.latest_dates()
    _write("carline.json", {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "cells": [{"code": r["district"], "date": r["date"], "plusDay": r["plusDay"],
                   "ts": r["timeslot"], "ok": bool(r["rows"] and r["routes"] and r["quota"]),
                   "rows": r["rows"], "routes": r["routes"], "quota": r["quota"]}
                  for r in recs],
        "districtLatest": {c: lat.get(c) for c in C.MARKET_NAME}})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeslots", action="store_true")
    ap.add_argument("--district", action="store_true")
    ap.add_argument("--carline", action="store_true")
    a = ap.parse_args()
    if not any((a.all, a.timeslots, a.district, a.carline)):
        ap.error("要揀至少一樣：--all / --timeslots / --district / --carline")
    print(f"collect {datetime.now():%Y-%m-%d %H:%M:%S}")
    if a.all or a.timeslots:
        do_timeslots()
    if a.all or a.district:
        do_district()
    if a.all or a.carline:
        do_carline()
    return 0


if __name__ == "__main__":
    sys.exit(main())
