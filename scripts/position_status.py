# -*- coding: utf-8 -*-
"""C2/A3 position_status.py —— 持仓收盘批量读取 + 盈亏/整体账/触发线判定
输入: --date YYYYMMDD（默认最新）| --hk "09999:37.54,09997:20.94,09998:9.73"（港股收盘，WebSearch 回填）
      --hk-chg "09999:+1.19,09997:-1.60,09998:+0.10"（可选；缺省则 chg=null）
输出: position_status_YYYYMMDD.json
  { date, positions:[{code,name,qty,cost,mkt,price,chg,pnl_pct,pnl_amt,mkt_val,weight_pct,strat,plan,status}],
    totals:{mkt_val,cost,unrealized,realized,overall} }
用法: python position_status.py [--date 20260821] --hk "..." [--hk-chg "..."] [--out-dir ...]
"""
import os, sys, struct, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import TDX_VIP, HK_REVIEW25_MULT, MARKET_PULSE

CONFIG = os.path.join(HERE, "data", "holdings_config.json")


def _resolve(code):
    if code.startswith(("sh", "sz", "bj")):
        return code[:2], code[2:]
    return ("sh" if code[0] in ("6", "5", "9") else "sz"), code


def read_last2(code, scale):
    """读 .day 最后 2 根：返回 (date, close, prev_close) 或 None"""
    mkt, c = _resolve(code)
    p = os.path.join(TDX_VIP, mkt, "lday", f"{mkt}{c}.day")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        data = f.read()
    n = len(data) // 32
    if n == 0:
        return None
    recs = [struct.unpack("<IIIIIfII", data[i * 32:(i + 1) * 32]) for i in range(n)]
    last = recs[-1]
    prev = recs[-2] if n > 1 else recs[-1]
    return last[0], last[4] / scale, prev[4] / scale


def main():
    args = sys.argv[1:]
    date, hk, hk_chg, out_dir = None, {}, {}, None
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date = args[i + 1]; i += 2
        elif args[i] == "--hk" and i + 1 < len(args):
            for pair in args[i + 1].split(","):
                if ":" in pair:
                    c, v = pair.split(":")
                    hk[c.strip()] = float(v)
            i += 2
        elif args[i] == "--hk-chg" and i + 1 < len(args):
            for pair in args[i + 1].split(","):
                if ":" in pair:
                    c, v = pair.split(":")
                    hk_chg[c.strip()] = float(v)
            i += 2
        elif args[i] == "--out-dir" and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2
        else:
            i += 1

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    positions = cfg["positions"]
    closed = cfg["closed"]
    ext_lines = cfg.get("extreme_lines", {})

    real_date = date
    rows = []
    total_val = 0.0
    total_cost = 0.0

    for pos in positions:
        code, mkt, qty, cost = pos["code"], pos["mkt"], pos["qty"], pos["cost"]
        price, chg = None, None
        d = None
        if mkt == "HK":
            if code in hk:
                price = hk[code]
                chg = hk_chg.get(code)
                d = date
        else:
            scale = 1000 if mkt == "ETF" else 100
            r = read_last2(code, scale)
            if r:
                d, price, prev = r
                chg = (price - prev) / prev * 100 if prev else None
                if not date:
                    real_date = str(d)
                elif real_date != str(d):
                    # 本地数据滞后时仍用最近日，但记录
                    pass
        if price is None:
            print(f"WARN {code} 无价格（港股需 --hk 回填）")
            continue
        pnl_pct = (price - cost) / cost * 100
        pnl_amt = (price - cost) * qty
        mkt_val = price * qty
        total_val += mkt_val
        total_cost += cost * qty

        # 触发线判定
        status = "正常"
        line = ext_lines.get(code)
        if line and price <= line:
            status = "⚠️触发极端线"
        elif mkt == "HK" and price <= cost * HK_REVIEW25_MULT:
            status = "⚠️触发-25%复盘线"
        elif mkt == "HK":
            ratio = price / cost
            if ratio <= HK_REVIEW25_MULT + 0.05:
                status = "接近-25%复盘线"

        rows.append(dict(code=code, name=pos["name"], qty=qty, cost=cost, mkt=mkt,
                         price=round(price, 3), chg=round(chg, 2) if chg is not None else None,
                         pnl_pct=round(pnl_pct, 2), pnl_amt=round(pnl_amt),
                         mkt_val=round(mkt_val), strat=pos["strat"], plan=pos["plan"],
                         status=status))
        _c = f"{chg:+.2f}%" if chg is not None else "-"
        print(f"  {code} {pos['name']}: {price:.3f} ({_c}) pnl={pnl_pct:+.2f}% {status}")

    for r in rows:
        r["weight_pct"] = round(r["mkt_val"] / total_val * 100, 1) if total_val else 0

    realized = sum(c["realized_pnl"] for c in closed)
    unrealized = total_val - total_cost
    out = {
        "date": real_date,
        "positions": rows,
        "totals": {
            "mkt_val": round(total_val),
            "cost": round(total_cost),
            "unrealized": round(unrealized),
            "realized": realized,
            "overall": round(unrealized + realized),
        },
    }
    if not out_dir:
        out_dir = MARKET_PULSE
    op = os.path.join(out_dir, f"position_status_{real_date}.json")
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TOTALS: 持仓市值", out["totals"]["mkt_val"], "未实现", out["totals"]["unrealized"],
          "已实现", realized, "合计", out["totals"]["overall"])
    print("WROTE", op)


if __name__ == "__main__":
    main()
