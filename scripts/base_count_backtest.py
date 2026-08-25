# -*- coding: utf-8 -*-
"""
M5 基底计数回测验证 — 第1/2基底突破 vs 3+基底突破 的胜率/赔率
================================================================
口径(遵循 #10 回测铁律): 突破后60交易日持有期收益, 按突破时基底数分组
样本: 候选池 546 只(taobo) 或 全市场, 2016-2026 全部突破事件
输出: 分组胜率/平均收益/中位/赔率(平均盈利/平均亏损) + 事件数

用法: python base_count_backtest.py [--pool 候选池csv或为空=全市场] [--hold 60]
"""
import os, sys, json, struct, datetime, math

TDX_ROOT = r"D:\Sofeware\TongDaXin"
MKT_PULSE = r"<PROJECT_ROOT>\deliverables\taobo-daily\market_pulse"

HOLD = 60          # 持有交易日
NEW_BASE_GAIN = 0.20
RESET_DRAWDOWN = 0.20

def market_dir(code6):
    if code6.startswith(("6", "9", "5", "11", "58")):
        return "sh"
    if code6.startswith(("0", "3", "12", "15", "16", "18")):
        return "sz"
    return "bj"

def read_day_all(code):
    mkt = market_dir(code)
    path = os.path.join(TDX_ROOT, "vipdoc", mkt, "lday", f"{mkt}{code}.day")
    if not os.path.exists(path):
        return None
    data = open(path, "rb").read()
    n = len(data) // 32
    rows = []
    for i in range(n):
        d, o, h, l, c, amt, vol, _ = struct.unpack("<8I", data[i*32:(i+1)*32])
        rows.append({"date": str(d), "close": c/100.0})
    return rows

def weekly_from_daily(daily):
    weeks = {}
    for r in daily:
        d = datetime.datetime.strptime(r["date"], "%Y%m%d")
        key = d.isocalendar()[:2]
        if key not in weeks:
            weeks[key] = {"date": r["date"], "close": r["close"]}
        else:
            weeks[key]["date"] = r["date"]
            weeks[key]["close"] = r["close"]
    return [weeks[k] for k in sorted(weeks.keys())]

def collect_breaks(daily, weekly):
    """返回突破事件: {week_idx, base_count, break_px}"""
    if len(weekly) < 30:
        return []
    hh = weekly[0]["close"]
    base_count = 0
    last_break_px = None
    events = []
    for i in range(1, len(weekly)):
        c = weekly[i]["close"]
        if c > hh:
            if last_break_px is None or (c / last_break_px - 1) >= NEW_BASE_GAIN:
                base_count += 1
                events.append({"week_idx": i, "base": base_count, "px": c,
                               "date": weekly[i]["date"]})
            last_break_px = c
            hh = c
        elif c < hh * (1 - RESET_DRAWDOWN):
            base_count = 0
            last_break_px = None
            hh = c
    return events

def main():
    pool_file = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--pool" and i+1 < len(args):
            pool_file = args[i+1]
        if a == "--hold" and i+1 < len(args):
            globals()["HOLD"] = int(args[i+1])

    # 股票池
    if pool_file and os.path.exists(pool_file):
        codes = [l.strip() for l in open(pool_file, encoding="utf-8") if l.strip()]
        print(f"池: {pool_file} ({len(codes)}只)")
    else:
        # 默认候选池: taobo kline_v2 目录(546只)
        kv = r"<PROJECT_ROOT>\deliverables\taobo-daily\tdx_data\kline_v2"
        codes = [f[:-4] for f in os.listdir(kv) if f.endswith(".csv")]
        print(f"池: taobo候选池 kline_v2 ({len(codes)}只)")

    # 分组统计
    groups = {}   # base -> {n, wins, losses, rets, gains, losses_sum}
    for ci, code in enumerate(codes):
        daily = read_day_all(code)
        if not daily:
            continue
        weekly = weekly_from_daily(daily)
        events = collect_breaks(daily, weekly)
        # 按周索引映射回日K: 周idx → 日K索引
        # 简化: 突破后 HOLD 交易日收益直接用日K在突破日期之后的索引
        dates_daily = [r["date"] for r in daily]
        for ev in events:
            bd = ev["date"]
            # 找突破日期在日K中的位置
            try:
                di = dates_daily.index(bd)
            except ValueError:
                continue
            if di + HOLD >= len(daily):
                continue  # 数据不足
            ret = daily[di + HOLD]["close"] / daily[di]["close"] - 1
            g = groups.setdefault(ev["base"], {"n": 0, "wins": 0, "rets": [],
                                               "gains": 0.0, "losses": 0.0,
                                               "win_ret": 0.0, "loss_ret": 0.0})
            g["n"] += 1
            g["rets"].append(ret)
            if ret > 0:
                g["wins"] += 1
                g["gains"] += 1
                g["win_ret"] += ret
            else:
                g["losses"] += 1
                g["loss_ret"] += ret
        if (ci+1) % 100 == 0:
            print(f"  进度 {ci+1}/{len(codes)}")

    # 汇总
    print(f"\n=== M5 基底计数回测 (持有{HOLD}交易日, 全区间) ===")
    print(f"{'基底数':<6}{'事件数':<8}{'胜率':<8}{'平均收益':<10}{'中位':<9}{'平均盈':<9}{'平均亏':<9}{'赔率':<7}")
    summary = []
    for b in sorted(groups.keys()):
        g = groups[b]
        avg_ret = sum(g["rets"]) / g["n"] * 100
        med = sorted(g["rets"])[g["n"]//2] * 100
        avg_win = g["win_ret"] / max(g["gains"], 1) * 100
        avg_loss = g["loss_ret"] / max(g["losses"], 1) * 100
        odds = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
        wr = g["wins"] / g["n"] * 100
        print(f"{b:<6}{g['n']:<8}{wr:<8.1f}{avg_ret:<10.2f}{med:<9.2f}{avg_win:<9.2f}{avg_loss:<9.2f}{odds:<7.2f}")
        summary.append({"base": b, "n": g["n"], "win_rate": round(wr, 1),
                        "avg_ret": round(avg_ret, 2), "median": round(med, 2),
                        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
                        "odds": round(odds, 2)})

    # 分组对比: 1-2 vs 3+
    early = groups.get(1, {"n":0})["n"] + groups.get(2, {"n":0})["n"]
    late = sum(groups.get(b, {"n":0})["n"] for b in groups if b >= 3)
    print(f"\n对比: 第1-2基底突破 {early} 事件 vs 第3+基底突破 {late} 事件")
    if late > 0:
        e_ret = sum(sum(groups[b]["rets"]) for b in [1, 2] if b in groups) / early * 100 if early else 0
        l_ret = sum(sum(groups[b]["rets"]) for b in groups if b >= 3) / late * 100
        e_wr = (sum(groups[b]["wins"] for b in [1, 2] if b in groups)) / early * 100 if early else 0
        l_wr = sum(groups[b]["wins"] for b in groups if b >= 3) / late * 100
        print(f"第1-2基底: 胜率 {e_wr:.1f}% 平均收益 {e_ret:+.2f}%")
        print(f"第3+基底:  胜率 {l_wr:.1f}% 平均收益 {l_ret:+.2f}%")
        print(f"Δ 胜率 {e_wr-l_wr:+.1f}pp, Δ 收益 {e_ret-l_ret:+.2f}pp")

    out = os.path.join(MKT_PULSE, f"base_count_backtest_{datetime.date.today().strftime('%Y%m%d')}.json")
    json.dump({"hold": HOLD, "summary": summary}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已输出: {out}")

if __name__ == "__main__":
    main()
