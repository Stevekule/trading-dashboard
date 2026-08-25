# -*- coding: utf-8 -*-
"""规则常量模块（B3）——交易看板/判定脚本共用，规则单点维护。
与 taobo-O'Neil SKILL.md / position-rules.md 同源（2026-08-14 定稿版）。
"""
import os

# ---------- adaptive 组合A 离场引擎（2026-08-14 拍板，仅 A 股个股） ----------
ADAPTIVE = {
    "stop_pct": 0.08,           # -8% 盘中止损（low 触及即触发）
    "trend": (0.10, 0.15),      # 趋势市峰值回撤：10% 减半 / 15% 清仓
    "range_": (0.08, 0.12),     # 震荡市：8% / 12%
    "weak": (0.06, 0.10),       # 弱势市：6% 减半 / 10% 清仓 + AlBrooks 锚（G2 门控下不触发）
    "expire_days": 250,         # 250 日到期强制平仓
    "protect": (0.15, 0.08),    # 辅层保护：浮盈曾≥15% 回撤≥8% 减半
    "peak": "close",            # peak = 收盘价最高
}

# ---------- 仓位规则 ----------
R1B = {"trend": 8, "range": 6, "weak": 4}   # R1b 持仓只数环境自适应
R1_SINGLE_MAX = 0.20                        # R1 单票 ≤ 总资金 20%
R2_FIRST_PCT = 0.10                         # R2 动态净值×10% 首笔
R6_BE_TH = 0.08                             # R6 BE 阈值 8%（2026-08-12 10%→8%，--be-stop-th 0.08）
R7_2_RPS250_TH = 90                         # R7-2 腾位新信号门槛 RPS250≥90（2026-08-12 95→90）

# ---------- 中期信号门控（taobo #8，2 指数标准） ----------
GATE_INDEXES = [
    ("sh000001", "上证", 100),
    ("sz399106", "深证综指", 100),
]
GATE_MA = 50

# ---------- 持仓触发线（见 holdings_config.json extreme_lines） ----------
HK_REVIEW25_MULT = 0.75      # 港股单票 -25% 复盘线 = 成本×0.75

# ---------- 本地数据路径 ----------
TDX_VIP = r"D:\Sofeware\TongDaXin\vipdoc"
PROJ = r"<PROJECT_ROOT>"
TAOBO_DAILY = os.path.join(PROJ, "deliverables", "taobo-daily")
MARKET_PULSE = os.path.join(TAOBO_DAILY, "market_pulse")
DASHBOARD_DIR = PROJ
