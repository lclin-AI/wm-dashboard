"""
zonegap.py — 搵出「CMS 話送得到、但 OIX 冇車線」嘅地址，逐日。

  CMS  /api/common/cms/address/estate?districtCode=   -> estate: zoneId, availableStores[], isolatedArea
  OIX  auto_delivery_route_delivery_zone_setting      -> 每日每個 zone 喺邊個時段有 route

規則（lclin 2026-10-02）：
  · 只計 active estate，isolatedArea=true（偏遠）一律剔走。
  · mapping 跟 estate 行（ZoneStoreGroupMapping 開關 = N，即係 legacy estate mapping），
    唔係跟 zone —— 同一個 zone 可以有啲 estate map 咗、有啲冇。
  · 一個街市嘅車線唔止喺自己個 district：屯門嘅元朗區仲行緊 NT-YTEX（舊元朗 WMYL*），
    大埔墟嘅火炭／大學行 NT-TSMEX（WMTPS*/WMTPM*）。漏咗呢兩個會誤報 300+ 個 zone。
  · 某街市某日自己個 district 完全冇 row = 車線未開到嗰日（批次推），唔逐個地址報。
"""
from __future__ import annotations

import collections
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

MONITOR = r"C:\Users\lclin\Downloads\wm-quota-monitor"
sys.path.insert(0, MONITOR)
import carline_check as C          # noqa: E402
from quota_report import headers, T  # noqa: E402

ACTIVE = list(C.CARLINE_DISTRICT)             # 八個 active 街市
# 街市 -> 佢啲 zone 可能掛喺邊幾個 OIX district（第一個係自己嗰個）
WM_DISTRICTS = {m: [d] for m, d in C.CARLINE_DISTRICT.items()}
WM_DISTRICTS["TM00001"].append("NT-YTEX")
WM_DISTRICTS["TPH00001"].append("NT-TSMEX")
THREE_SLOT = set(C.THREE_SLOT) | {"NT-YTEX", "NT-TSMEX"}
SLOTS = ("AM", "PM1", "PM2", "EV")


def _slots(district: str, ts: str) -> tuple[str, ...]:
    if ts == "PM":
        return ("PM1", "PM2") if district in THREE_SLOT else ("PM1",)
    return (ts,) if ts in SLOTS else ()


def cms_estates() -> list[dict]:
    H = headers()
    areas = requests.get(T + "/api/common/cms/address/areas", headers=H, timeout=60).json()["data"]
    ds = [(d["code"], d["nameZh"]) for a in areas for d in a["district"]]

    def f(x):
        r = requests.get(T + "/api/common/cms/address/estate", params={"districtCode": x[0]},
                         headers=H, timeout=120)
        r.raise_for_status()
        return x, r.json().get("data") or []

    out = []
    with ThreadPoolExecutor(6) as ex:
        for (code, name), rows in ex.map(f, ds):
            for e in rows:
                if not e.get("active") or e.get("isolatedArea"):
                    continue
                wms = [s for s in e.get("availableStores") or [] if s in ACTIVE]
                if wms:
                    out.append({"zone": e["zoneId"], "wms": wms, "name": e.get("nameZh") or e.get("nameEn"),
                                "code": e.get("code"), "district": name})
    if len(out) < 10000:            # 平時 ~40k；太少即係 CMS 出事，唔好出一份假嘅「全部冇車線」
        raise RuntimeError(f"CMS estate 得 {len(out)} 個，似係抽唔齊")
    return out


def oix_cover(dates: list[str]) -> tuple[dict, dict]:
    """cover[(date, district)] = {zone: set(slots)}；rows[(date, district)] = row 數。"""
    cover, nrows = {}, {}
    districts = sorted({d for v in WM_DISTRICTS.values() for d in v})
    for dist in districts:
        for d in dates:
            rows = [r for r in C.fetch_day(dist, d.replace("-", ""))
                    if not (dist in C.THREE_SLOT and r.get("timeslot") == "PM2")]  # fetch_day 自己複製咗嗰份
            z = collections.defaultdict(set)
            for r in rows:
                if r.get("route"):
                    z[r["zone"]].update(_slots(dist, r.get("timeslot")))
            cover[(d, dist)] = z
            nrows[(d, dist)] = len(rows)
    return cover, nrows


def build(days: int) -> dict:
    today = datetime.now().date()
    dates = [f"{today + timedelta(days=i):%Y-%m-%d}" for i in range(days)]
    est = cms_estates()
    cover, nrows = oix_cover(dates)

    out = {}
    for d in dates:
        per = {}
        for m in ACTIVE:
            own = WM_DISTRICTS[m][0]
            if not nrows[(d, own)]:
                per[m] = {"window": False}       # 車線未開到呢日
                continue
            need = set().union(*cover[(d, own)].values()) if cover[(d, own)] else set(SLOTS)
            zones = {}
            for e in est:
                if m not in e["wms"]:
                    continue
                got = set()
                for dist in WM_DISTRICTS[m]:
                    got |= cover.get((d, dist), {}).get(e["zone"], set())
                miss = sorted(need - got, key=SLOTS.index)
                if not miss:
                    continue
                z = zones.setdefault(e["zone"], {"zone": e["zone"], "miss": miss, "estates": [],
                                                 "districts": set()})
                z["estates"].append(e["name"])
                z["districts"].add(e["district"])
            lst = sorted(zones.values(), key=lambda z: (-len(z["estates"]), z["zone"]))
            for z in lst:
                z["districts"] = sorted(z["districts"])
                z["none"] = len(z["miss"]) == len(need)
            per[m] = {"window": True, "zones": lst,
                      "addresses": sum(len(z["estates"]) for z in lst)}
        out[d] = per
    return {"updatedAt": datetime.now().isoformat(timespec="seconds"),
            "dates": dates, "estatesChecked": len(est), "byDate": out,
            "districts": WM_DISTRICTS}
