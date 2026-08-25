# -*- coding: utf-8 -*-
"""C3 watchlist_pullback.py —— 重点观察池解析 + 回踩目标（均线）计算
输入: --date YYYYMMDD（必填；从 daily-screening-YYYY-MM-DD.md 解析观察池）
输出: watchlist_YYYYMMDD.json
  [{code,name,channel,score,c6,dbl,rps250,rps120,board,close,chg,ma10,ma20,ma50,ma120,pullback:{target_ma,value}}]
回踩目标规则: RPS120<70 → 50日线；RPS120≥85 → 10日线；否则 20日线（2026-08-21 方案定稿）
用法: python watchlist_pullback.py --date 20260821 [--out-dir ...]
"""
import os, sys, struct, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import TDX_VIP, TAOBO_DAILY, MARKET_PULSE


def _resolve(code):
    if code.startswith(("sh", "sz", "bj")):
        return code[:2], code[2:]
    return ("sh" if code[0] in ("6", "5", "9") else "sz"), code


def read_day_n(code, scale, n=130):
    mkt, c = _resolve(code)
    p = os.path.join(TDX_VIP, mkt, "lday", f"{mkt}{c}.day")
    if not os.path.exists(p):
        return []
    with open(p, "rb") as f:
        data = f.read()
    total = len(data) // 32
    start = max(0, total - n)
    recs = [struct.unpack("<IIIIIfII", data[i * 32:(i + 1) * 32]) for i in range(start, total)]
    return [(r[0], r[4] / scale) for r in recs]


def parse_watchlist(date):
    """从 daily-screening 报告解析重点观察池表 → list[dict]"""
    d = date[:4] + "-" + date[4:6] + "-" + date[6:]
    p = os.path.join(TAOBO_DAILY, f"daily-screening-{d}.md")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    lines = open(p, encoding="utf-8").read().splitlines()

    # 找重点观察池表起点（标题后第一个表头行）
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("## 重点观察池"):
            start = i
            break
    if start is None:
        raise ValueError("报告无重点观察池章节")
    # 找表头行（含 通道/代码/名称 关键列）
    head_i = None
    for i in range(start, min(start + 20, len(lines))):
        if "通道" in lines[i] and "代码" in lines[i]:
            head_i = i
            break
    if head_i is None:
        raise ValueError("观察池表头未找到")

    items = []
    for ln in lines[head_i + 1:]:
        ln = ln.strip()
        if not ln.startswith("|"):
            if ln.startswith("**操作提示") or ln.startswith("---"):
                break
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 11 or not cells[0].isdigit():
            continue
        # 序号|通道|代码|名称|加分|C6|双RPS|RPS250|RPS120|板块|...
        ch = cells[1]
        code = cells[2]
        name = cells[3]
        score = int(cells[4]) if cells[4].isdigit() else 0
        c6 = 1 if cells[5] == "✅" else 0
        dbl = 1 if cells[6] == "✅" else 0
        rps250 = float(cells[7]) if cells[7].replace(".", "").isdigit() else None
        rps120 = float(cells[8]) if cells[8].replace(".", "").isdigit() else None
        board = cells[9]
        items.append(dict(code=code, name=name, channel=ch, score=score, c6=c6, dbl=dbl,
                          rps250=rps250, rps120=rps120, board=board))
    if not items:
        raise ValueError("观察池解析为空")
    return items


def main():
    args = sys.argv[1:]
    date, out_dir = None, None
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date = args[i + 1]; i += 2
        elif args[i] == "--out-dir" and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2
        else:
            i += 1
    assert date, "需要 --date YYYYMMDD"

    items = parse_watchlist(date)
    out = []
    for it in items:
        code = it["code"]
        mkt = "ETF" if code.startswith(("5", "1")) else "A"
        scale = 1000 if mkt == "ETF" else 100
        seq = read_day_n(code, scale)
        if not seq:
            print(f"WARN {code} 无本地数据")
            continue
        close = seq[-1][1]
        chg = (seq[-1][1] - seq[-2][1]) / seq[-2][1] * 100 if len(seq) > 1 else None
        closes = [c for _, c in seq]
        ma = {}
        for n in (10, 20, 50, 120):
            if len(closes) >= n:
                ma[n] = sum(closes[-n:]) / n
        # 回踩目标规则：RPS120 初选档位，若现价已跌破该均线则顺延下一档（10→20→50→120），直到均线<现价
        r120 = it["rps120"]
        if r120 is None:
            tgt0 = 20
        elif r120 < 70:
            tgt0 = 50
        elif r120 >= 85:
            tgt0 = 10
        else:
            tgt0 = 20
        ladder = [10, 20, 50, 120]
        tgt = tgt0
        note = ""
        for cand in ladder[ladder.index(tgt0):]:
            if ma.get(cand) and ma[cand] < close:
                tgt = cand
                if cand != tgt0:
                    note = f"已破MA{tgt0}·顺延MA{cand}"
                break
        else:
            tgt = 120
            note = "超跌·MA120仍上方"
        it.update(close=round(close, 2), chg=round(chg, 2) if chg is not None else None,
                  ma10=round(ma.get(10, 0), 2), ma20=round(ma.get(20, 0), 2),
                  ma50=round(ma.get(50, 0), 2), ma120=round(ma.get(120, 0), 2),
                  pullback={"target_ma": tgt, "value": round(ma.get(tgt, 0), 2), "note": note})
        out.append(it)
        print(f"  {code} {it['name']}: close={it['close']} 回踩MA{tgt}={it['pullback']['value']}")

    if not out_dir:
        out_dir = MARKET_PULSE
    op = os.path.join(out_dir, f"watchlist_{date}.json")
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"WATCH {len(out)} 只 | WROTE", op)


if __name__ == "__main__":
    main()
