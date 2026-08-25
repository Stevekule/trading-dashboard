# -*- coding: utf-8 -*-
"""C1 market_state.py —— 中期信号门控 + 指数状态判定（taobo #8 两指数标准）
输入: --date YYYYMMDD（默认自动取本地 .day 最新交易日）
输出: market_state_YYYYMMDD.json
  { date, gate: ON/OFF, off_days, indexes: {code:{name,close,ma50,dist_pct}}, cyb: {...}, c4: {pass,total,pct} }
用法: python market_state.py [--date 20260821] [--c4 209/546] [--out-dir ...]
"""
import os, sys, struct, json, re, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules_config import TDX_VIP, GATE_INDEXES, GATE_MA, TAOBO_DAILY, MARKET_PULSE


def _resolve(code):
    """带前缀代码(sh000001)直接用，否则按首字符"""
    if code.startswith(("sh", "sz", "bj")):
        return code[:2], code[2:]
    return ("sh" if code[0] in ("6", "5", "9") else "sz"), code


def read_day_all(code, scale):
    """读 .day 全量 K 线，返回 list[(date_int, close_float)] 按时间升序"""
    mkt, c = _resolve(code)
    p = os.path.join(TDX_VIP, mkt, "lday", f"{mkt}{c}.day")
    if not os.path.exists(p):
        return []
    with open(p, "rb") as f:
        data = f.read()
    n = len(data) // 32
    recs = [struct.unpack("<IIIIIfII", data[i * 32:(i + 1) * 32]) for i in range(n)]
    return [(r[0], r[4] / scale) for r in recs]


def ma50_at(seq, idx):
    if idx < GATE_MA - 1:
        return None
    window = [c for _, c in seq[idx - GATE_MA + 1:idx + 1]]
    return sum(window) / GATE_MA


def parse_c4(flag):
    if not flag:
        return None
    m = re.search(r"(\d+)\s*/\s*(\d+)", flag)
    if m:
        p, t = int(m.group(1)), int(m.group(2))
        return {"pass": p, "total": t, "pct": round(p / t * 100, 1)}
    return None


def parse_c4_from_report(date):
    """从 daily-screening-YYYY-MM-DD.md 自动解析 C4 通过数（兜底）"""
    d = date[:4] + "-" + date[4:6] + "-" + date[6:]
    p = os.path.join(TAOBO_DAILY, f"daily-screening-{d}.md")
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"通过\s*(\d+)只\s*\(([\d.]+)%\)", txt)
    if m:
        return {"pass": int(m.group(1)), "total": 546, "pct": float(m.group(2))}
    return None


def main():
    args = sys.argv[1:]
    date = None
    c4 = None
    out_dir = None
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date = args[i + 1]; i += 2
        elif args[i] == "--c4" and i + 1 < len(args):
            c4 = args[i + 1]; i += 2
        elif args[i] == "--out-dir" and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2
        else:
            i += 1

    # 取最新交易日（默认）
    seqs = {}
    for code, name, scale in GATE_INDEXES:
        seqs[code] = read_day_all(code, scale)
    last_date = seqs[GATE_INDEXES[0][0]][-1][0] if seqs[GATE_INDEXES[0][0]] else None
    if date:
        last_date = int(date)

    # 定位目标日在各指数序列中的下标（若无当日数据则取当日之前最近一天）
    def locate(seq, d):
        for j in range(len(seq) - 1, -1, -1):
            if seq[j][0] <= d:
                return j
        return None

    idx = {c: locate(s, last_date) for c, s in seqs.items()}
    # 实际交易日 = 各指数目标下标日期的最大值（以主要指数为准）
    real_date = max(seqs[c][idx[c]][0] for c, s in seqs.items() if idx[c] is not None)

    out = {"date": str(real_date), "gate": None, "off_days": 0, "indexes": {}, "cyb": None, "c4": None}

    # 各指数状态
    gate_ok = True
    for code, name, scale in GATE_INDEXES:
        s = seqs[code]
        j = idx[code]
        close = s[j][1]
        m50 = ma50_at(s, j)
        dist = (close - m50) / m50 * 100 if m50 else None
        out["indexes"][code] = {"name": name, "close": round(close, 2), "ma50": round(m50, 2) if m50 else None,
                                "dist_pct": round(dist, 1) if dist is not None else None}
        if m50 is not None and close <= m50:
            gate_ok = False

    # 创业板（辅助显示，不参与门控）
    cyb = read_day_all("sz399006", 100)
    if cyb:
        jc = locate(cyb, real_date)
        if jc is not None:
            cc = cyb[jc][1]
            m50c = ma50_at(cyb, jc)
            out["cyb"] = {"close": round(cc, 2),
                          "ma50": round(m50c, 2) if m50c else None,
                          "dist_pct": round((cc - m50c) / m50c * 100, 1) if m50c else None}

    out["gate"] = "ON" if gate_ok else "OFF"

    # 连续 OFF 天数（从 real_date 往回）
    if out["gate"] == "OFF":
        j0 = min(idx[c] for c in idx if idx[c] is not None)
        days = 0
        for k in range(idx[GATE_INDEXES[0][0]], j0 - 1, -1):
            close0 = seqs[GATE_INDEXES[0][0]][k][1]
            m500 = ma50_at(seqs[GATE_INDEXES[0][0]], k)
            j1 = locate(seqs[GATE_INDEXES[1][0]], seqs[GATE_INDEXES[0][0]][k][0])
            if m500 is None or j1 is None:
                break
            close1 = seqs[GATE_INDEXES[1][0]][j1][1]
            m501 = ma50_at(seqs[GATE_INDEXES[1][0]], j1)
            if m501 is None:
                break
            if close0 > m500 and close1 > m501:  # 该日为 ON（两指数均站上）→ 停止计数
                break
            days += 1
        out["off_days"] = days
    else:
        # ON 天数
        days = 0
        for k in range(idx[GATE_INDEXES[0][0]], -1, -1):
            close0 = seqs[GATE_INDEXES[0][0]][k][1]
            m500 = ma50_at(seqs[GATE_INDEXES[0][0]], k)
            j1 = locate(seqs[GATE_INDEXES[1][0]], seqs[GATE_INDEXES[0][0]][k][0])
            if m500 is None or j1 is None:
                break
            close1 = seqs[GATE_INDEXES[1][0]][j1][1]
            m501 = ma50_at(seqs[GATE_INDEXES[1][0]], j1)
            if m501 is None:
                break
            if not (close0 > m500 and close1 > m501):  # 该日为 OFF → 停止计数
                break
            days += 1
        out["on_days"] = days

    # C4 占比
    out["c4"] = parse_c4(c4) or parse_c4_from_report(str(real_date))

    if not out_dir:
        out_dir = MARKET_PULSE
    op = os.path.join(out_dir, f"market_state_{real_date}.json")
    os.makedirs(out_dir, exist_ok=True)
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("STATE:", out["gate"], "off_days=", out.get("off_days", 0), "| date", out["date"])
    for c, v in out["indexes"].items():
        print(f"  {v['name']} close={v['close']} MA50={v['ma50']} dist={v['dist_pct']}%")
    print("WROTE", op)


if __name__ == "__main__":
    main()
