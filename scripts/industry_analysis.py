# -*- coding: utf-8 -*-
"""
行业广度 + 行业RPS 引擎 (M2/M3) — 通达信行业分类, 100% 本地
================================================================
数据源(免费):
- 行业归属: tdxhy.cfg(个股→T代码) + tdxzs.cfg(类型2 行业板块名)
- 个股日K: vipdoc/{sh,sz,bj}/lday/*.day

M2 行业广度: 每行业 250日新高家数 / 行业个股数 = 新高比例
M3 行业RPS:  行业成分股周涨幅等权平均 → 全行业 RANK → 0-100 分位

更新频率: 每周五收盘后(周涨幅口径) / 每日(广度口径)
用法:
    python industry_analysis.py [--out out.json] [--days 60]
"""
import os, sys, json, struct, datetime

TDX_ROOT = r"D:\Sofeware\TongDaXin"
TDXHY_CFG = os.path.join(TDX_ROOT, "T0002", "hq_cache", "tdxhy.cfg")
TDXZS_CFG = os.path.join(TDX_ROOT, "T0002", "hq_cache", "tdxzs.cfg")

def market_dir(code6):
    if code6.startswith(("6", "9", "5", "11", "58")):
        return "sh"
    if code6.startswith(("0", "3", "12", "15", "16", "18")):
        return "sz"
    return "bj"

def read_day_tail(code, root=TDX_ROOT, max_bars=400):
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

def load_sectors():
    """从 tdxzs.cfg 类型2 构建 {5位T代码: 行业名}——5位=二级行业(通达信行业, 粒度≈申万一级, 排除3位TDX大类)。"""
    data = open(TDXZS_CFG, "rb").read().decode("gbk", errors="ignore")
    l2 = {}
    for line in data.splitlines():
        parts = line.split("|")
        if len(parts) >= 6 and parts[2] == "2":
            tcode = parts[5]
            if len(tcode) == 5 and not parts[0].startswith("TDX"):
                l2[tcode] = parts[0]
    return l2

def load_stock_sector():
    """个股 → 二级行业T代码(取前5位)"""
    data = open(TDXHY_CFG, "rb").read().decode("gbk", errors="ignore")
    mapping = {}
    for line in data.splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[0] in ("0", "1", "2"):
            code, t = parts[1], parts[2]
            mapping[code] = t[:5] if len(t) >= 5 else t
    return mapping

def compute():
    print("解析行业归属...")
    sectors = load_sectors()
    stock_sector = load_stock_sector()
    print(f"  一级行业 {len(sectors)} 个, 个股映射 {len(stock_sector)} 只")

    # 按行业分组
    sector_codes = {}
    for code, t1 in stock_sector.items():
        sector_codes.setdefault(t1, []).append(code)

    # 逐行业统计
    print("计算行业广度与周涨幅...")
    results = []
    for t1, name in sectors.items():
        codes = sector_codes.get(t1, [])
        if not codes:
            continue
        # 采样最多 80 只(性能), 统计每只的高新新低与周涨幅
        nh_cnt = 0
        nl_cnt = 0
        valid = 0
        week_chg_sum = 0.0
        week_chg_n = 0
        for code in codes:
            rows = read_day_tail(code, max_bars=260)
            if not rows:
                continue
            valid += 1
            # 250日新高新低(最后一日)
            if len(rows) >= 251:
                win_high = max(r["high"] for r in rows[-251:-1])
                win_low = min(r["low"] for r in rows[-251:-1])
                if rows[-1]["high"] > win_high:
                    nh_cnt += 1
                if rows[-1]["low"] < win_low:
                    nl_cnt += 1
            # 周涨幅: 最近5个交易日
            if len(rows) >= 6:
                w = (rows[-1]["close"] / rows[-6]["close"] - 1) * 100
                week_chg_sum += w
                week_chg_n += 1
        if valid == 0:
            continue
        results.append({
            "code": t1, "name": name, "stocks": len(codes), "valid": valid,
            "new_highs": nh_cnt, "new_lows": nl_cnt,
            "high_ratio": round(nh_cnt / valid * 100, 2),
            "low_ratio": round(nl_cnt / valid * 100, 2),
            "net": nh_cnt - nl_cnt,
            "week_chg": round(week_chg_sum / week_chg_n, 2) if week_chg_n else 0,
        })

    # 行业RPS: 按周涨幅排名 → 0-100
    if results:
        n = len(results)
        by_chg = sorted(results, key=lambda r: r["week_chg"], reverse=True)
        rank_map = {r["code"]: i+1 for i, r in enumerate(by_chg)}
        for r in results:
            r["rps"] = round((n - rank_map[r["code"]]) / n * 100, 1)
            r["rank"] = rank_map[r["code"]]

    results.sort(key=lambda r: r["rps"], reverse=True)
    return results

def main():
    out = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--out" and i+1 < len(args):
            out = args[i+1]

    results = compute()
    asof = datetime.date.today().strftime("%Y%m%d")
    payload = {
        "asof": asof,
        "asof_full": datetime.date.today().strftime("%Y-%m-%d"),
        "data_source": "通达信本地vipdoc + tdxhy.cfg + tdxzs.cfg (免费)",
        "metric": "M2行业新高比例(250日) + M3行业RPS(周涨幅排名)",
        "industries": results,
    }
    if not out:
        out = os.path.join(r"<PROJECT_ROOT>\deliverables\taobo-daily\market_pulse", f"industry_{asof}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"已输出: {out}")
    print("\n=== 行业RPS TOP10 ===")
    for r in results[:10]:
        print(f"  {r['name']:<6} RPS={r['rps']:>5.1f} 周涨幅={r['week_chg']:>6.2f}% 新高比例={r['high_ratio']:>5.2f}% 新高/新低={r['new_highs']}/{r['new_lows']} ({r['valid']}只)")

if __name__ == "__main__":
    main()
