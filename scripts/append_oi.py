# -*- coding: utf-8 -*-
"""A4 append_oi.py —— M4 期权 OI 追加 + 自动重跑（2026-08-21 落地）
MCP 拉取（8 合约 VolInStock）仍需人工执行（OI 无本地源），本脚本固化「追加 json + 重跑 option_sentiment.py」。
用法: python append_oi.py --date 20260821 C4600=3298 C4700=5405 C4800=7424 C4900=9517 P4600=4295 P4700=5165 P4800=4685 P4900=4558
"""
import os, sys, json, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import MARKET_PULSE

OI_JSON = os.path.join(MARKET_PULSE, "option_oi_510300_2612.json")
SENT_SCRIPT = os.path.join(HERE, "option_sentiment.py")

CONTRACTS = ["C4600", "C4700", "C4800", "C4900", "P4600", "P4700", "P4800", "P4900"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="交易日期 YYYYMMDD")
    ap.add_argument("oi", nargs="+", help="合约=OI，如 C4600=3298")
    a = ap.parse_args()

    d = json.load(open(OI_JSON, encoding="utf-8"))
    for pair in a.oi:
        k, v = pair.split("=")
        assert k in CONTRACTS, f"未知合约 {k}"
        assert "202608" in a.date, "日期格式应 YYYYMMDD"
        if a.date in d[k]:
            print(f"WARN {k} 已有 {a.date}，跳过")
            continue
        d[k][a.date] = int(v)
    json.dump(d, open(OI_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"APPENDED {a.date} OK; days now:", len(d["C4700"]))

    r = subprocess.run([sys.executable, SENT_SCRIPT], capture_output=True, text=True)
    print(r.stdout[-500:])
    if r.returncode != 0:
        print("STDERR:", r.stderr[-500:])
        sys.exit(1)


if __name__ == "__main__":
    main()
