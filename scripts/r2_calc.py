# -*- coding: utf-8 -*-
"""S3 r2_calc.py —— R2 建仓金额/数量计算（2026-08-21 落地）
口径: position-rules.md R2 —— 动态净值×10% 三分建仓（10%/6%/4%），禁固定金额
输入: --date YYYYMMDD --code 688002 --price 160.41 --tranche 1|2|3（默认1）
      --cash 可选（默认从 total_invested 反推）
输出: 建仓数量建议（整手=100 股）
用法: python r2_calc.py --date 20260821 --code 688002 --price 160.41 --tranche 1
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import MARKET_PULSE, R2_FIRST_PCT

CFG = os.path.join(HERE, "data", "holdings_config.json")
TRANCHES = {1: 0.10, 2: 0.06, 3: 0.04}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--price", type=float, required=True)
    ap.add_argument("--tranche", type=int, default=1, choices=[1, 2, 3])
    ap.add_argument("--cash", type=float, default=None, help="现金额（缺省按总投入反推）")
    ap.add_argument("--out-dir", default=MARKET_PULSE)
    a = ap.parse_args()

    ps = json.load(open(os.path.join(a.out_dir, f"position_status_{a.date}.json"), encoding="utf-8"))
    cfg = json.load(open(CFG, encoding="utf-8"))
    invested = cfg.get("total_invested")
    if not invested:
        # 反推：总投入 = 当前持仓成本 + 已清仓成本
        closed_cost = sum(c["qty"] * c["cost"] for c in cfg.get("closed", []))
        invested = ps["totals"]["cost"] + closed_cost

    if a.cash is None:
        cash = invested - ps["totals"]["cost"] + ps["totals"]["realized"]
    else:
        cash = a.cash
    nav = ps["totals"]["mkt_val"] + cash  # 动态净值

    pct = TRANCHES[a.tranche]
    amt = nav * pct
    min_lot = 200 if a.code.startswith("688") else 100  # 科创板 200 股起
    shares = int(amt / a.price // min_lot * min_lot)
    note = ""
    if shares < min_lot:
        shares = min_lot
        note = f"⚠️ {pct*100:.0f}% 动态净值不足 1 手（{min_lot}股起），按最小 1 手计（超支 {shares*a.price/amt*100-100:.0f}%）——建议等回踩或降档"
    actual = shares * a.price

    print(f"净值(动态) = 持仓 {ps['totals']['mkt_val']:,} + 现金 {cash:,.0f} = {nav:,.0f}")
    print(f"第 {a.tranche} 笔（{pct*100:.0f}%）: 金额 {amt:,.0f} → 数量 {shares} 股 @ {a.price:.2f}，占用 {actual:,.0f}")
    if note:
        print(note)
    print(f"建议: {a.code} 建仓 {shares} 股（约 {pct*100:.0f}% 动态净值）")

    out = {"date": a.date, "code": a.code, "price": a.price, "tranche": a.tranche,
           "nav": round(nav), "cash": round(cash), "amount": round(amt),
           "shares": shares, "actual": round(actual), "pct": pct}
    op = os.path.join(a.out_dir, f"r2_calc_{a.date}_{a.code}.json")
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WROTE", op)


if __name__ == "__main__":
    main()
