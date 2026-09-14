# 街市即日餸 Dashboard

三樣嘢一版睇晒：

| Tab | 內容 | 來源 |
|---|---|---|
| 落單時段 | 九個街市 D+0..D+2 每格時段揀唔揀得到 | 監察程式每分鐘查嘅實際落單頁 |
| District Quota | 六個街市 D+0..D+14 delivery quota 用量 | OIX 自動劃車線 → District Quota |
| 車線 Carline | 六個街市 D+0..D+14 車線上咗未 | OIX 自動劃車線 → Delivery Zone |

## 覆蓋缺口

OIX 得六個街市有 district：士美菲路、九龍城、荃灣、灣仔、保安道、將軍澳。
**屯門、大埔墟、元朗冇** —— 所以 District Quota 同車線兩個 tab 得六行組，
落單時段就九個都有。

## 點更新

```
python collect.py --timeslots --district     # 平，可以密啲跑
python collect.py --carline                  # 重（~90 requests），一日一兩次
python publish.py                             # commit + push，GitHub Pages 自動更新
```

`--timeslots` **唔會**自己 call 時段 API —— 佢淨係讀 `wm-quota-monitor/snapshot.json`。
時段 API 跟 account 嘅 default 送貨地址，monitor 每輪都要 PUT 一次改地址；
兩個 process 一齊 PUT 就會互相踢走對方揀嘅地址，讀到第啲街市嘅時段表，
結果報假爆 quota（2026-09-01 中過一次）。

OIX 登入見 `wm-quota-monitor/oix_setcred.py`（密碼放 Windows Credential Manager）。
