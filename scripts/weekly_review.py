# -*- coding: utf-8 -*-
"""S4 weekly_review.py —— 周五选股复盘回查（2026-08-21 落地）
口径: taobo-O'Neil 每周流程（周五 20:00）——候选逐只回查条件（RPS 延续/掉出/新进/买点触发）
输入: --end YYYYMMDD（周五，默认取 signals_filtered 最新）+ 该周各日 quality_floor CSV
输出: weekly_review_YYYYMMDD.md（结构化表格；LLM 只写偏差分析）
用法: python weekly_review.py --end 20260821 [--out-dir 默认 taobo-daily]
"""
import os, sys, json, csv, glob, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import TAOBO_DAILY
sys.path.insert(0, r"<TAOBO_SKILL_REFS>/references")
import rps_lookup as R


def weekday(d):
    return datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday()  # 4=周五


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", required=True, help="周五日期 YYYYMMDD")
    ap.add_argument("--out-dir", default=TAOBO_DAILY)
    a = ap.parse_args()

    # 收集本周（含 end 前 5 个自然日）的 quality_floor CSV
    files = []
    end_dt = datetime.date(int(a.end[:4]), int(a.end[4:6]), int(a.end[6:]))
    for i in range(7):
        d = (end_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        p = os.path.join(a.out_dir, f"signals_filtered_{d}_quality_floor.csv")
        if os.path.exists(p):
            files.append((d, p))
    files.sort()
    if not files:
        sys.exit("本周无 signals_filtered 文件")

    # 本周各日 A+B 代码集合
    day_sets = {}
    day_ab = {}
    for d, p in files:
        codes = set()
        ab = set()
        with open(p, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                code = r["code"].strip().zfill(6)
                codes.add(code)
                if r.get("fund_grade", "C") in ("A", "B"):
                    ab.add(code)
        day_sets[d] = codes      # 全 C4
        day_ab[d] = ab           # 仅 A+B（质量地板通过）

    all_codes = set().union(*day_ab.values()) if day_ab else set()
    first_day = files[0][0]
    last_day = files[-1][0]

    # 新进/掉出（A+B 口径）
    new_in = sorted(day_ab[last_day] - day_ab[first_day])
    dropped = sorted(day_ab[first_day] - day_ab[last_day])

    # 今日 RPS 延续（对最后一日 A+B 重查）
    rows = []
    still_c4 = 0
    for code in sorted(day_ab[last_day]):
        try:
            rps = R.get_stock_rps(code)
        except Exception:
            rps = None
        if not rps:
            continue
        r250 = rps.get("RPS250")
        r120 = rps.get("RPS120")
        c4 = bool(r250 and r250 >= 90) or bool(r120 and r120 >= 90)
        if c4:
            still_c4 += 1
        rows.append({"code": code, "rps250": r250, "rps120": r120, "c4": c4})

    c4_cnt = sum(1 for x in rows if x["c4"])
    drop_c4 = [x["code"] for x in rows if not x["c4"]]

    # 输出 md
    lines = [f"# 周度选股复盘 · {last_day}（周五）",
             "",
             f"> 数据范围：{first_day} ~ {last_day}，A+B 候选逐日留存；今日 RPS 重查（{len(rows)} 只）。",
             "",
             "## 一、本周候选留存",
             "",
             "| 指标 | 数值 |",
             "|------|------|",
             f"| 周一 A+B | {len(day_ab[first_day])} 只 |",
             f"| 周五 A+B | {len(day_ab[last_day])} 只 |",
             f"| 本周新进 | {len(new_in)} 只（{'、'.join(new_in[:20])}） |",
             f"| 本周掉出 | {len(dropped)} 只（{'、'.join(dropped[:20])}） |",
             f"| 周五仍 C4 一线红 | {c4_cnt} 只 |",
             f"| 周五掉出一线红 | {len(drop_c4)} 只（{'、'.join(drop_c4[:20])}） |",
             "",
             "## 二、周五候选 RPS 明细（Top20）",
             "",
             "| 代码 | RPS250 | RPS120 | C4 |",
             "|------|--------|--------|-----|",
             ]
    for x in sorted(rows, key=lambda r: -(r["rps250"] or 0))[:20]:
        lines.append(f"| {x['code']} | {x['rps250']} | {x['rps120']} | {'✅' if x['c4'] else '❌'} |")
    lines.append("")
    lines.append("## 三、偏差分析（LLM 填写）")
    lines.append("")
    lines.append("- 新进/掉出标的归因：")
    lines.append("- 候选 RPS 延续性判断：")
    lines.append("- 下周观察重点：")

    op = os.path.join(a.out_dir, f"weekly_review_{a.end}.md")
    open(op, "w", encoding="utf-8").write("\n".join(lines))
    print(f"周复盘: {first_day}~{last_day} | A+B {len(day_ab[first_day])}→{len(day_ab[last_day])} | 新进 {len(new_in)} / 掉出 {len(dropped)} | 仍C4 {c4_cnt}")
    print("WROTE", op)


if __name__ == "__main__":
    main()
