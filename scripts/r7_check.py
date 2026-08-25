# -*- coding: utf-8 -*-
"""S2 r7_check.py —— 淘弱留强 R7-2 检查（2026-08-21 落地）
口径: position-rules.md R7-2 —— 新信号 RPS250≥90 且双RPS（板块 RPS20≥90）→ 满仓腾位换强（卖最弱1只，池内分位）
输入: --date YYYYMMDD + market_state（R1b 上限）+ position_status（当前持仓数）
      c4_today_YYYYMMDD.json（新信号 double 字段判定双RPS）
输出: r7_check_YYYYMMDD.json {new_r72:[...], position_count, r1b_limit, is_full, weakest, action}
用法: python r7_check.py --date 20260821 [--out-dir ...]
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import MARKET_PULSE, R1B, R7_2_RPS250_TH, TAOBO_DAILY
sys.path.insert(0, r"<TAOBO_SKILL_REFS>/references")
import rps_lookup as R

A_SHARE_PREFIX = ("0", "3", "6", "8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", default=MARKET_PULSE)
    a = ap.parse_args()

    ymd = a.date.replace("-", "")
    ms = json.load(open(os.path.join(a.out_dir, f"market_state_{ymd}.json"), encoding="utf-8"))
    ps = json.load(open(os.path.join(a.out_dir, f"position_status_{ymd}.json"), encoding="utf-8"))
    c4 = json.load(open(os.path.join(TAOBO_DAILY, f"c4_today_{ymd}.json"), encoding="utf-8"))

    # R1b 上限：门控 OFF=weak(4) / ON=trend(8)；中间态按震荡(6)由 LLM 判断，脚本按门控输出
    env = "weak" if ms["gate"] == "OFF" else "trend"
    r1b_limit = R1B[env]

    # 新信号中 R7-2 达标（C4 全满足 RPS250≥90，需双RPS：double.best_board.RPS20≥90）
    r72 = []
    for rec in c4.get("c4", []):
        dbl = rec.get("double") or {}
        bb = dbl.get("best_board") or {}
        rps20 = bb.get("RPS20")
        if rps20 is not None and rps20 >= 90:
            r72.append({"code": rec["code"], "name": rec["name"],
                        "board": bb.get("name"), "board_rps20": rps20,
                        "rps250": rec.get("RPS250")})

    # 持仓数（A股个股计入 R1b；战略持有 ETF/港股不计入——按 position-rules：R1b 约束 AI 策略仓）
    ai_pos = [h for h in ps["positions"] if h["strat"] in ("反弹清仓", "已决持有·守极端线") and h["mkt"] == "A"]
    pos_cnt = len(ai_pos)
    is_full = pos_cnt >= r1b_limit

    # 满仓 → 持仓 RPS250 重查 → 卖最弱（池内分位最低）
    weakest = None
    if is_full and r72:
        best = None
        for h in ai_pos:
            try:
                rps = R.get_stock_rps(h["code"])
                r250 = rps.get("RPS250") if rps else None
            except Exception:
                r250 = None
            cand = {"code": h["code"], "name": h["name"], "rps250": r250}
            if best is None or (r250 is not None and (best["rps250"] is None or r250 < best["rps250"])):
                best = cand
        weakest = best

    action = "暂不触发（未满仓）"
    if r72:
        if is_full:
            action = (f"⚠️ 满仓（{pos_cnt}/{r1b_limit}）且新信号 {len(r72)} 只达标 → "
                      f"建议卖最弱 {weakest['name']} {weakest['code']}（RPS250={weakest['rps250']}）腾位换强"
                      if weakest else "满仓且新信号达标，需腾位（持仓 RPS 均无数据）")
        else:
            action = f"未满仓（{pos_cnt}/{r1b_limit}）→ 新信号 {len(r72)} 只可直接建仓，无需腾位"

    out = {"date": a.date, "gate": ms["gate"], "r1b_limit": r1b_limit,
           "ai_position_count": pos_cnt, "is_full": is_full,
           "new_r72": r72[:20], "new_r72_count": len(r72),
           "weakest": weakest, "action": action}
    op = os.path.join(a.out_dir, f"r7_check_{ymd}.json")
    json.dump(out, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"R7-2: 新信号 {len(r72)} 只达标 | 持仓 {pos_cnt}/{r1b_limit} | {action[:80]}")
    print("WROTE", op)


if __name__ == "__main__":
    main()
