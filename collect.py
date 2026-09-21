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
sys.path.insert(0, str(HERE))
from runlock import RunLock
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
    # 唔好出街：snapshot 入面嘅 addresses 係監察 account 嘅真實送貨地址
    # （屋苑／座數），dashboard 用唔着，公開網站更加唔應該有。
    d.pop("addresses", None)
    age = (datetime.now() - datetime.fromisoformat(d["updatedAt"])).total_seconds()
    d["ageSeconds"] = int(age)
    if age > 600:
        print(f"  ⚠ snapshot 已經 {int(age//60)} 分鐘冇更新，monitor 可能停咗")
    _write("timeslots.json", d)

    # 成條鏈嘅健康狀況（monitor 每輪寫）。冇 health.json 都唔好死 ——
    # 舊版 monitor 未寫呢個檔。
    h = MONITOR / "health.json"
    if h.exists():
        st = json.loads(h.read_text(encoding="utf-8"))
        # 幾時抄嘅。冇咗呢個就分唔開「monitor 停咗」同「推送慢咗」——
        # 個站係靜態檔，由 monitor 寫到瀏覽器見到，中間有 task 間隔（5 分鐘）
        # ＋ push ＋ Pages 部署 ＋ 頁面自己 reload，加埋隨時 8 分鐘。
        # 用「瀏覽器而家」減「monitor 最後一輪」去判斷 monitor 死未，一定誤報。
        st["collectedAt"] = datetime.now().isoformat(timespec="seconds")
        _write("status.json", st)
    else:
        print("  ⚠ 冇 health.json（monitor 未跑過新版？）")


def do_district() -> None:
    import oix_quota as Q
    today = datetime.now().date()
    av = Q.available()
    cells = []
    # 九個街市全部出。OIX 未有 district 嗰啲照出 record，標 inOix=false，
    # 等個站可以顯示「OIX 未有」而唔係靜靜雞少咗三行。
    for code in sorted(Q.MARKETS):
        if code not in av:
            for i in range(DAYS):
                day = today + timedelta(days=i)
                for ts in ("AM", "PM", "PM2", "EV"):
                    cells.append({"code": code, "date": f"{day:%Y-%m-%d}", "plusDay": i,
                                  "ts": ts, "slot": Q.TS_LABEL.get(ts, ts),
                                  "inOix": False, "used": None, "quota": None})
            continue
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
                              "inOix": True, "used": used, "quota": quota})
    _write("district.json", {"updatedAt": datetime.now().isoformat(timespec="seconds"),
                             "cells": cells})


def do_carline() -> None:
    import carline_check as C
    recs = C.scan(DAYS)
    lat = C.latest_dates()
    _write("carline.json", {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "cells": [{"code": r["district"], "date": r["date"], "plusDay": r["plusDay"],
                   "ts": r["timeslot"], "inOix": r.get("inOix", True),
                   "ok": bool(r["rows"] and r["routes"] and r["quota"]),
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
    # ⚠ Fast（每 5 分鐘）同 Carline（每日 06:30）會撞正 06:30 —— 兩個一齊
    # 改 docs/data/*.json 又一齊 git commit，邊個搶輸就 exit 1。
    # 2026-09-18~21 車線連續四日冇更新就係咁，而且靜靜雞失敗。
    with RunLock():
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
