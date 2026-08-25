# -*- coding: utf-8 -*-
"""S1 position_signal.py —— 持仓信号状态机输出（2026-08-21 落地）
口径: taobo-O'Neil position-rules.md R2/R3/R4/R6（状态机 WATCH/OPEN/MANAGING/CLOSED）
   - adaptive 组合A 仅 A 股个股：-8% 盘中止损 > 峰值回撤减半 > 峰值回撤清仓 > 250 日到期
   - ETF 不参与 adaptive（Al Brooks 移动止盈锚）；黄金标的战略持有·逻辑止损（8/14 拍板）
   - 战略持有（港股死拿/长期持有/商业航天）：事件/基本面止损，仅极端线监控
   - 已决持有（8/20 拍板 000999/159999/563999）：豁免 adaptive，守极端线
输入: position_status_YYYYMMDD.json + data/holdings_config.json + market_state_YYYYMMDD.json
输出: position_signal_YYYYMMDD.json [{code,state,signal,reason,trigger_line}]
用法: python position_signal.py --date 20260821 [--out-dir ...]
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import MARKET_PULSE, ADAPTIVE

CFG = os.path.join(HERE, "data", "holdings_config.json")

# 战略持有类策略（不套 adaptive，事件/基本面止损 + 极端线）
STRATEGIC = ("港股死拿", "长期持有", "战略持有·逻辑止损", "商业航天·已决持有", "已决持有·守极端线")


def classify_strat(s):
    return "STRATEGIC" if any(k in s for k in STRATEGIC) else "ADAPTIVE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", default=MARKET_PULSE)
    a = ap.parse_args()

    ps = json.load(open(os.path.join(a.out_dir, f"position_status_{a.date}.json"), encoding="utf-8"))
    cfg = json.load(open(CFG, encoding="utf-8"))
    ext = cfg.get("extreme_lines", {})

    out = []
    for h in ps["positions"]:
        code, strat = h["code"], h["strat"]
        kind = classify_strat(strat)
        line = ext.get(code)
        rec = {"code": code, "name": h["name"], "strat": strat, "kind": kind,
               "pnl_pct": h["pnl_pct"], "price": h["price"], "cost": h["cost"]}

        if kind == "STRATEGIC":
            # 极端线触发判定
            if line and h["price"] <= line:
                rec.update(state="MANAGING", signal="🔴 触发极端线·重新评估",
                           reason=f"现价 {h['price']} ≤ 极端线 {line}（事件/基本面未破坏仍可持有，触发重评）",
                           trigger_line=line)
            elif h["status"] == "⚠️触发-25%复盘线":
                rec.update(state="MANAGING", signal="⚠️ 触发-25%复盘线·逻辑复盘",
                           reason="浮亏达 -25%，按死拿纪律复核基本面/主题逻辑",
                           trigger_line=None)
            else:
                rec.update(state="MANAGING", signal="✅ 持有",
                           reason="战略持有·事件/基本面止损" + (f"；极端线 {line}" if line else ""),
                           trigger_line=line)
        else:
            # ADAPTIVE（A 股个股新仓/管理仓）：当前持仓无此类型则输出规则说明
            stop_line = h["cost"] * (1 - ADAPTIVE["stop_pct"])
            if h["price"] <= stop_line:
                rec.update(state="CLOSED", signal="🔴 清仓（-8% 盘中止损）",
                           reason=f"现价 {h['price']} ≤ 止损线 {stop_line:.2f}（low 触及即触发）",
                           trigger_line=round(stop_line, 2))
            elif h["pnl_pct"] >= ADAPTIVE["protect"][0] and h["pnl_pct"] < 0:
                pass  # 峰值回撤需历史数据，此处仅 -8% 判定
            else:
                rec.update(state="MANAGING", signal="✅ 持有",
                           reason=f"adaptive 管理：-8% 止损线 {stop_line:.2f} / R6 BE 浮盈≥8% / 峰值回撤 trend10·15 range8·12 weak6·10",
                           trigger_line=round(stop_line, 2))

        out.append(rec)
        print(f"  {code} {h['name']}: {rec['state']} | {rec['signal']}")

    op = os.path.join(a.out_dir, f"position_signal_{a.date}.json")
    json.dump({"date": a.date, "signals": out}, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WROTE", op)


if __name__ == "__main__":
    main()
