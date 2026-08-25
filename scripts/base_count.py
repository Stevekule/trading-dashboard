# -*- coding: utf-8 -*-
"""
M5 基底计数状态机 — 欧奈尔基底理论落地(基底.txt 规则)
================================================================
规则(源自 基底.txt, 欧奈尔 How to Make Money in Stocks):
1. 用周线数基底
2. 熊市(主要指数下跌≥20%)重置基底数
3. 牛市轻度回撤(<20%)不重置
4. 当前基底低于先前基底(中断上升趋势)重置计数
5. 突破后上涨<20%又回落仍属同一基底(底上加底)
6. 专注第1/2个基底突破(第3/4个更易失败)

实现(状态机, 日K合成周线, 全部本地免费):
- 逐周推进, 维护: 历史最高价 hh / 上次突破前基底高点 pivot / 基底计数 n / 突破状态
- 周收盘 > hh 且距上次突破涨幅≥20% → 新基底突破 n+1 (突破后涨幅<20%再创新高=底上加底, n不变)
- 周收盘较 hh 回撤 ≥ 20% → 趋势中断, n 归零(与规则2熊市重置一致)
- 突破前基底高点低于上一个基底高点 → 降级/重置(规则4简化: 以 hh 失效即重置)
输出: 每标的当前基底计数 + 历史上每次突破的标记(供回测)

用法:
  python base_count.py [--out base_count_YYYYMMDD.json]
"""
import os, sys, json, struct, datetime

TDX_ROOT = r"D:\Sofeware\TongDaXin"
TDXHY_CFG = os.path.join(TDX_ROOT, "T0002", "hq_cache", "tdxhy.cfg")
MKT_PULSE = r"<PROJECT_ROOT>\deliverables\taobo-daily\market_pulse"

# 突破后涨幅达到该值才算"新基底"(否则底上加底)
NEW_BASE_GAIN = 0.20
# 从高点回撤达到该值 → 趋势中断/熊市重置
RESET_DRAWDOWN = 0.20
# 周线数据起始(欧奈尔建议用完整历史, 取上市以来)

def market_dir(code6):
    if code6.startswith(("6", "9", "5", "11", "58")):
        return "sh"
    if code6.startswith(("0", "3", "12", "15", "16", "18")):
        return "sz"
    return "bj"

def read_day_all(code, root=TDX_ROOT):
    mkt = market_dir(code)
    path = os.path.join(root, "vipdoc", mkt, "lday", f"{mkt}{code}.day")
    if not os.path.exists(path):
        return None
    data = open(path, "rb").read()
    n = len(data) // 32
    rows = []
    for i in range(n):
        d, o, h, l, c, amt, vol, _ = struct.unpack("<8I", data[i*32:(i+1)*32])
        rows.append({"date": str(d), "close": c/100.0, "high": h/100.0, "low": l/100.0})
    return rows

def to_weekly(daily):
    """日K → 周K(每周最后交易日收盘/最高/最低)"""
    weeks = {}
    for r in daily:
        # 日期 YYYYMMDD → ISO周
        d = datetime.datetime.strptime(r["date"], "%Y%m%d")
        key = d.isocalendar()[:2]  # (year, week)
        if key not in weeks:
            weeks[key] = {"date": r["date"], "close": r["close"], "high": r["high"], "low": r["low"]}
        else:
            w = weeks[key]
            w["date"] = r["date"]  # 取当周最后一天
            w["close"] = r["close"]
            w["high"] = max(w["high"], r["high"])
            w["low"] = min(w["low"], r["low"])
    return [weeks[k] for k in sorted(weeks.keys())]

def count_bases(weekly):
    """
    状态机。返回 (当前基底计数, 突破记录列表[(date, base_count, 突破后60日涨幅/收益, 标记)])
    突破记录: 每次创新高突破 → 记录 突破时基底数
    """
    if len(weekly) < 30:
        return 0, []
    hh = weekly[0]["close"]          # 历史最高收盘
    pivot = weekly[0]["close"]       # 当前基底前高(突破参考)
    base_count = 0                   # 已完成基底数
    last_break = None                # 上次突破时的基底计数
    last_break_px = None             # 上次突破时的价格
    breaks = []                      # 突破记录
    cur_count = 0

    for i in range(1, len(weekly)):
        c = weekly[i]["close"]
        # 1) 创新高 → 突破
        if c > hh:
            if last_break_px is not None and (c / last_break_px - 1) < NEW_BASE_GAIN:
                # 底上加底: 距上次突破涨幅<20%, 仍属同一基底, 计数不变
                pass
            else:
                base_count += 1
                breaks.append({"date": weekly[i]["date"], "base": base_count,
                               "px": round(c, 2), "type": "break"})
            last_break = base_count
            last_break_px = c
            hh = c
            pivot = c
        else:
            # 2) 回撤检查: 从 hh 回撤 ≥20% → 趋势中断, 重置
            if c < hh * (1 - RESET_DRAWDOWN):
                if base_count > 0:
                    breaks.append({"date": weekly[i]["date"], "base": 0,
                                   "px": round(c, 2), "type": "reset"})
                base_count = 0
                last_break = None
                last_break_px = None
                hh = c          # 重新锚定
                pivot = c
    return base_count, breaks

def load_stock_list():
    codes = []
    with open(TDXHY_CFG, "rb") as f:
        raw = f.read().decode("gbk", errors="ignore")
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[0] in ("0", "1", "2"):
            codes.append(parts[1])
    return codes

def main():
    out = None
    limit = 0
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--out" and i+1 < len(args):
            out = args[i+1]
        if a == "--limit" and i+1 < len(args):
            limit = int(args[i+1])

    print("加载全A清单...")
    codes = load_stock_list()
    if limit:
        codes = codes[:limit]
    print(f"  {len(codes)} 只")

    results = []
    missing = 0
    for i, code in enumerate(codes):
        daily = read_day_all(code)
        if not daily:
            missing += 1
            continue
        weekly = to_weekly(daily)
        n, breaks = count_bases(weekly)
        # 当前是否处于"突破后回踩中"(最新周 > 基底起点)
        last_break = breaks[-1] if breaks else None
        results.append({
            "code": code,
            "base_count": n,
            "weeks": len(weekly),
            "last_break": last_break,
            "total_breaks": len([b for b in breaks if b["type"] == "break"]),
            "resets": len([b for b in breaks if b["type"] == "reset"]),
        })
        if (i+1) % 2000 == 0:
            print(f"  进度 {i+1}/{len(codes)}")

    # 分布统计
    dist = {}
    for r in results:
        dist[r["base_count"]] = dist.get(r["base_count"], 0) + 1
    print(f"完成, 缺失 {missing} 只")
    print("基底计数分布:", dict(sorted(dist.items())))

    payload = {
        "asof": datetime.date.today().strftime("%Y%m%d"),
        "data_source": "通达信本地vipdoc(免费)",
        "rules": "基底.txt 欧奈尔5规则(20%新基底/20%重置)",
        "total": len(results),
        "distribution": {str(k): v for k, v in sorted(dist.items())},
        "stocks": results,
    }
    if not out:
        out = os.path.join(MKT_PULSE, f"base_count_{datetime.date.today().strftime('%Y%m%d')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"已输出: {out}")

if __name__ == "__main__":
    main()
