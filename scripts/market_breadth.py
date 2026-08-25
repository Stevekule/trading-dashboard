# -*- coding: utf-8 -*-
"""
市场广度引擎 (M1) — 全市场 250日新高/新低「下雨图」数据
================================================================
数据源(100% 本地, 零接口费用):
- 通达信本地日K: vipdoc/{sh,sz,bj}/lday/*.day
- 全A股代码清单: tdxhy.cfg(通达信行业映射文件, 含全部A股)
输出:
- JSON 时间序列: 每日新高家数/新低家数/差值/占比/20日平滑 + 上证指数对照
- 供 trading-dashboard 看板「市场广度」区块渲染与自动分析

更新频率: 每日收盘后(通达信盘后下载完成即可跑)
用法:
    python market_breadth.py [--out out.json] [--days 120]
窗口: 默认 120 个交易日(约半年, 2026-08-12 用户指令 60→120)
"""
import os, sys, json, struct, datetime

TDX_ROOT = r"D:\Sofeware\TongDaXin"
TDXHY_CFG = os.path.join(TDX_ROOT, "T0002", "hq_cache", "tdxhy.cfg")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "deliverables", "taobo-daily", "market_pulse")

# 行业一级名称(来自 tdxzs.cfg 类型2, 与 tdxhy.cfg T代码前缀匹配)
SECTOR_L1 = {
    "T0101": "煤炭", "T0102": "电力", "T0103": "石油", "T0201": "钢铁", "T0202": "有色",
    "T0204": "化工", "T0206": "建材", "T0302": "农林牧渔", "T0303": "纺织服饰",
    "T0304": "食品饮料", "T0305": "酿酒", "T0402": "汽车类", "T0405": "医药",
    "T0501": "商业连锁", "T0601": "传媒娱乐", "T0605": "旅游", "T0704": "通用机械",
    "T0705": "工业机械", "T0901": "运输服务", "T0903": "交通设施", "T1101": "建筑",
    "T1102": "房地产", "T1202": "通信设备", "T1203": "半导体", "T1204": "软件服务",
    "T1205": "元器件", "T1002": "证券", "T1003": "保险", "T0401": "白酒", "T0403": "家电",
}

def market_dir(code6):
    if code6.startswith(("6", "9", "5", "11", "58")):
        return "sh"
    if code6.startswith(("0", "3", "12", "15", "16", "18")):
        return "sz"
    return "bj"

def read_day_tail(code, root=TDX_ROOT, max_bars=450):
    """读 .day 尾部 max_bars 根K线(价格已 /100)。返回 list[dict(date,high,low,close)] 按时间升序
    max_bars=450: 120日窗口 + 250日回看 + 边距(2026-08-12 窗口改半年)"""
    mkt = market_dir(code)
    path = os.path.join(root, "vipdoc", mkt, "lday", f"{mkt}{code}.day")
    if not os.path.exists(path):
        return None
    data = open(path, "rb").read()
    n = len(data) // 32
    if n == 0:
        return None
    start = max(0, n - max_bars)
    rows = []
    for i in range(start, n):
        d, o, h, l, c, amt, vol, _ = struct.unpack("<8I", data[i*32:(i+1)*32])
        rows.append({"date": str(d), "high": h/100.0, "low": l/100.0, "close": c/100.0})
    return rows

def load_stock_list():
    """从 tdxhy.cfg 加载全A代码(第一列=0 的个股行)"""
    codes = []
    with open(TDXHY_CFG, "rb") as f:
        raw = f.read().decode("gbk", errors="ignore")
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[0] in ("0", "1", "2"):
            codes.append(parts[1])
    return codes

def compute_breadth(codes, lookback=250, max_bars=400):
    """
    对每只股票: 判定每个交易日是否创 lookback 日新高/新低(用最高/最低价)。
    返回 {date: {"nh": int, "nl": int}}
    """
    daily = {}   # date -> [nh, nl]
    missing = 0
    for i, code in enumerate(codes):
        rows = read_day_tail(code, max_bars=max_bars)
        if not rows:
            missing += 1
            continue
        # 滚动窗口: 第 j 天对照前 lookback 天(不含当日)
        for j in range(1, len(rows)):
            lo = max(0, j - lookback)
            win_high = max(r["high"] for r in rows[lo:j])
            win_low = min(r["low"] for r in rows[lo:j])
            d = rows[j]["date"]
            if d not in daily:
                daily[d] = [0, 0]
            if rows[j]["high"] > win_high:
                daily[d][0] += 1
            if rows[j]["low"] < win_low:
                daily[d][1] += 1
        if (i+1) % 1000 == 0:
            print(f"  进度 {i+1}/{len(codes)}")
    return daily, missing

def build_series(daily, total, idx_rows, days=60):
    """整理为时间序列 + 指数对照。idx_rows = 上证指数日K(升序)"""
    dates = sorted(daily.keys())[-days:]
    idx_by_date = {r["date"]: r for r in idx_rows}
    series = {"dates": [], "new_highs": [], "new_lows": [], "high_pct": [], "low_pct": [],
              "net": [], "net_ma5": [], "high_pct_ma20": [], "idx_close": [], "idx_ma50": []}
    for d in dates:
        nh, nl = daily[d]
        series["dates"].append(d)
        series["new_highs"].append(nh)
        series["new_lows"].append(nl)
        series["high_pct"].append(round(nh / total * 100, 2))
        series["low_pct"].append(round(nl / total * 100, 2))
        series["net"].append(nh - nl)
        # 指数对照
        if d in idx_by_date:
            series["idx_close"].append(round(idx_by_date[d]["close"], 2))
        else:
            series["idx_close"].append(None)
    # 移动平均
    for i in range(len(dates)):
        w5 = series["net"][max(0,i-4):i+1]
        series["net_ma5"].append(round(sum(w5)/len(w5), 1))
        w20 = series["high_pct"][max(0,i-19):i+1]
        series["high_pct_ma20"].append(round(sum(w20)/len(w20), 2))
    # 指数 MA50
    closes = [r["close"] for r in idx_rows]
    for d in dates:
        idx = next((k for k, r in enumerate(idx_rows) if r["date"] == d), None)
        if idx is not None and idx >= 49:
            series["idx_ma50"].append(round(sum(closes[idx-49:idx+1])/50, 2))
        else:
            series["idx_ma50"].append(None)
    return series

def main():
    out = None
    days = 120  # 半年≈120交易日(2026-08-12 用户指令 60→120)
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--out" and i+1 < len(args):
            out = args[i+1]
        if a == "--days" and i+1 < len(args):
            days = int(args[i+1])

    print("加载全A股票清单...")
    codes = load_stock_list()
    print(f"  {len(codes)} 只")

    print("计算 250日新高/新低...")
    daily, missing = compute_breadth(codes)
    print(f"  完成, 缺失 {missing} 只")

    # 上证指数(本地 sh000001.day, 自包含读取)
    path = os.path.join(TDX_ROOT, "vipdoc", "sh", "lday", "sh000001.day")
    idx = None
    if os.path.exists(path):
        data = open(path, "rb").read()
        n = len(data) // 32
        idx = []
        for i in range(max(0, n-500), n):
            d, o, h, l, c, amt, vol, _ = struct.unpack("<8I", data[i*32:(i+1)*32])
            idx.append({"date": str(d), "close": c/100.0})
    if idx:
        idx = idx[-260:]
        print(f"  上证指数对照 {len(idx)} 根, 最新 {idx[-1]['date']} {idx[-1]['close']}")

    total = len(codes) - missing
    series = build_series(daily, total, idx, days)
    result = {
        "asof": series["dates"][-1] if series["dates"] else "",
        "asof_full": datetime.date.today().strftime("%Y-%m-%d"),
        "total_stocks": total,
        "lookback": 250,
        "data_source": "通达信本地vipdoc(免费)",
        "series": series,
    }

    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"已输出: {out}")
    else:
        os.makedirs(OUT_DIR, exist_ok=True)
        out = os.path.join(OUT_DIR, f"breadth_{series['dates'][-1]}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"已输出: {out}")
    print(f"最新日 {series['dates'][-1]}: 新高 {series['new_highs'][-1]} / 新低 {series['new_lows'][-1]} / 差值 {series['net'][-1]}")

if __name__ == "__main__":
    main()
