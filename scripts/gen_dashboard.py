# -*- coding: utf-8 -*-
"""D1 gen_dashboard.py —— 统一交易看板通用渲染器（面板式布局，数据全 JSON 输入）
输入（均在 market_pulse 目录或由前置脚本产出）：
  --date YYYYMMDD（必填）
  market_state_YYYYMMDD.json       ← market_state.py
  position_status_YYYYMMDD.json    ← position_status.py（含港股回填）
  watchlist_YYYYMMDD.json          ← watchlist_pullback.py
  market_pulse_panels_YYYYMMDD.html + option_sentiment_panel_YYYYMMDD.html + base_count_YYYYMMDD.json
  --notes "复盘文字（可多行，含\n）" 可选；缺省用默认复盘模板
  --flow "09:25|竞价|内容" 多条用 \n 分隔，可选（缺省按门控自动生成默认流程）
输出: 统一交易看板_YYYYMMDD.html（面板式：头部/复盘/盯盘/持仓总览/M1-M5/观察池/决策流/观察指标/仓位/不碰/核心思路/页脚）
"""
import os, sys, json, re, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules_config import PROJ, MARKET_PULSE, DASHBOARD_DIR

TPL = os.path.join(HERE, "data", "dashboard_template.html")
CFG = os.path.join(HERE, "data", "holdings_config.json")

WEEKDAY = {"1": "周一", "2": "周二", "3": "周三", "4": "周四", "5": "周五", "6": "周六", "0": "周日"}


def load_json(p):
    return json.load(open(p, encoding="utf-8"))


def fmt_date(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def weekday_cn(d):
    import datetime
    return WEEKDAY[str(datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday() + 1)]


def strip_fragment(path):
    html = open(path, encoding="utf-8").read()
    html = re.sub(r"<style[\s\S]*?</style>", "", html)
    html = re.sub(r"<script[\s\S]*?</script>", "", html)
    return html.strip()


def up(x):
    return "up" if x >= 0 else "down"


def sig_tag(channel):
    if channel.startswith("A"):
        return "sig-green"
    if channel.startswith("B"):
        return "sig-yellow"
    return "sig-blue"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--notes", default="", help="复盘文字（\n 分隔多段）")
    ap.add_argument("--flow", default="", help="决策流程：'时间|动作|说明' 多条用 \\n 分隔")
    ap.add_argument("--dont", default="", help="不碰清单：'标题❌|原因' 多条用 \\n 分隔")
    ap.add_argument("--core", default="", help="核心思路一句话")
    ap.add_argument("--out-dir", default=DASHBOARD_DIR)
    a = ap.parse_args()

    D = a.date
    mp = MARKET_PULSE

    # ---------- 读数据 ----------
    ms = load_json(os.path.join(mp, f"market_state_{D}.json"))
    ps = load_json(os.path.join(mp, f"position_status_{D}.json"))
    wl = load_json(os.path.join(mp, f"watchlist_{D}.json"))
    cfg = load_json(CFG)

    m1m2m3 = strip_fragment(os.path.join(mp, f"market_pulse_panels_{D}.html"))
    m4 = strip_fragment(os.path.join(mp, f"option_sentiment_panel_{D}.html"))
    bc = load_json(os.path.join(mp, f"base_count_{D}.json"))
    dist, tot = bc["distribution"], bc["total"]
    b0, b1, b2, b3 = dist.get("0", 0), dist.get("1", 0), dist.get("2", 0), dist.get("3", 0)
    pct = lambda x: f"{x / tot * 100:.1f}%"
    m5 = f"""
<div class="mkt-panel">
  <h3>🧱 M5 基底计数（欧奈尔周线基底状态机 · {fmt_date(D)} · 全A {tot}只）</h3>
  <div class="mkt-kpi"><div class="kpi"><div class="v">{pct(b1)}</div><div class="l">基底1({b1}只)</div></div><div class="kpi"><div class="v">{pct(b0)}</div><div class="l">基底0({b0}只)</div></div><div class="kpi"><div class="v">{pct(b2)}</div><div class="l">基底2({b2}只)</div></div><div class="kpi"><div class="v">{pct(b3)}</div><div class="l">基底3({b3}只)</div></div><div class="kpi"><div class="v">{pct(b2 + b3)}</div><div class="l">2+基底({b2 + b3}只)</div></div></div>
  <div class="mkt-note">基底计数状态机: 周K合成 · 突破新高且距上次突破涨幅≥20%=新基底+1 · 从高点回撤≥20%=趋势中断归零 · 规则源自基底.txt(已硬编码, 2026-08-12 网格验证)</div>
  <div class="mkt-analysis"><div>{fmt_date(D)} 全市场基底分布: <b>基底1占 {pct(b1)}</b>({b1}只), 基底0 {pct(b0)}, 基底2 {pct(b2)}, 基底3 {pct(b3)}。</div><div>事件研究(2026-08-12 回测): 第1/2基底突破胜率 <b class='sig-up'>48.7%/+5.31%</b> vs 3+基底 <b class='sig-dn'>37.7%/+0.31%</b> — 优先关注 1-2 基底标的。</div><div><b class='sig-nt'>组合层面结论: 4+基底过滤不作硬实装(60组合交叉证伪), 仅作候选排序同分微调(基底少排前)</b>。</div></div>
</div>"""

    # ---------- 1. Header ----------
    idx0 = list(ms["indexes"].values())[0]
    gate = ms["gate"]
    off_txt = f"第{ms.get('off_days', 0)}日" if gate == "OFF" else f"第{ms.get('on_days', 0)}日"
    c4 = ms.get("c4") or {}
    c4_txt = f"{c4.get('pass', '?')}/{c4.get('total', 546)}（{c4.get('pct', '?')}%）" if c4 else "—"
    mkt_chips = []
    for c, v in ms["indexes"].items():
        d_cls = "down" if v["dist_pct"] is not None and v["dist_pct"] < 0 else "up"
        mkt_chips.append(f"<span>{v['name']} <b>{v['close']}</b> <span class='{d_cls}'>MA50{'上' if v['dist_pct'] and v['dist_pct'] >= 0 else '下'}{abs(v['dist_pct']):.1f}%</span></span>")
    if ms.get("cyb"):
        cyb = ms["cyb"]
        mkt_chips.append(f"<span>创业板 <b>{cyb['close']}</b> <span class='{'up' if cyb['dist_pct'] and cyb['dist_pct']>=0 else 'down'}'>MA50{'上' if cyb['dist_pct'] and cyb['dist_pct']>=0 else '下'}{abs(cyb['dist_pct']):.1f}%</span></span>")
    mid_icon = "🟢" if gate == "ON" else "🔴"
    mid_desc = f"{off_txt} · 3指数全线跌破50日线" if gate == "OFF" else off_txt
    mkt_chips.append(f"<span>中期信号 <span class='{'up' if gate=='ON' else 'down'}'> {mid_icon} {gate}（{mid_desc}）</span></span>")
    mkt_chips.append(f"<span>C4一线红 {c4_txt}</span>")
    mkt_chips.append(f"<span>重点观察池 <b>{len(wl)}只</b>（规则达标制）</span>")
    env = "弱势市" if gate == "OFF" else "趋势市"
    mkt_chips.append(f"<span>环境：<b class='{'down' if gate=='OFF' else 'up'}'> {env}</b></span>")

    body = []
    title = f"统一交易看板 — {D[:4]}.{int(D[4:6])}.{int(D[6:])} {weekday_cn(D)}"
    body.append(f"""
<div class="panel header-panel">
  <h1>📋 {title}</h1>
  <div class="date">基于 {fmt_date(D)} 收盘数据 | 跟踪=陶博士{D[4:6]}/{D[6:]}重点观察池{len(wl)}只 + {len(ps['positions'])}只持仓 | 仓位=taobo-O'Neil | 止盈=adaptive组合A(A股个股)/移动止盈锚(ETF)/黄金战略持有 | ⚠️ 不构成投资建议</div>
  <div class="mkt-stats">{''.join(mkt_chips)}</div>
</div>""")

    # ---------- 2. 复盘 ----------
    notes_html = a.notes.replace("\\n", "\n")
    if notes_html.strip():
        paras = []
        for seg in notes_html.strip().split("\n"):
            seg = seg.strip()
            if not seg:
                continue
            if seg.startswith("!!r"):
                paras.append(f"<div class='alert-r'>{seg[3:].strip()}</div>")
            elif seg.startswith("!!g"):
                paras.append(f"<div class='alert-g'>{seg[3:].strip()}</div>")
            elif seg.startswith("!!y"):
                paras.append(f"<div class='alert-y'>{seg[3:].strip()}</div>")
            elif seg.startswith("!!"):
                paras.append(f"<div class='alert-r'>{seg[2:].strip()}</div>")
            else:
                paras.append(f"<div class='alert-y'>{seg}</div>")
        review = f"<h2>📊 {fmt_date(D)} 复盘</h2>" + "\n".join(paras)
    else:
        tot = ps["totals"]
        review = f"""<h2>📊 {fmt_date(D)} 复盘</h2>
  <div class="alert-y"><strong>⚠️ 大盘：中期信号 {gate}（{off_txt}）</strong>——{idx0['name']} {idx0['close']}（MA50 {idx0['ma50']}，{idx0['dist_pct']:+.1f}%）。弱势市维持，观察池 {len(wl)} 只只观察不建仓。</div>
  <div class="alert-g"><strong>✅ 整体账：≈{tot['overall']:,} 元</strong>（持仓市值 {tot['mkt_val']:,} + 已实现 {tot['realized']:,}）。</div>"""
    body.append("<div class='panel'>" + review + "</div>")

    # ---------- 3. 盯盘清单（持仓卡 + 观察池 TOP 卡） ----------
    cards = []
    for h in ps["positions"]:
        p_cls = "priority-1" if h["strat"].startswith("战略") else ("priority-2" if "死拿" in h["strat"] else "priority-3")
        cards.append(f"""
    <div class="watch-card {p_cls}">
      <div class="wc-badge badge-hold">{'战略持有' if h['strat'].startswith('战略') else ('死拿' if '死拿' in h['strat'] else '持仓')}</div>
      <div class="wc-code">{h['code']}</div>
      <div class="wc-name">{h['name']}</div>
      <div class="wc-price {up(h['pnl_pct'])}">{h['price']:.3f}</div>
      <div class="wc-signal">{h['qty']} 成本{h['cost']:.3f}<br>{h['pnl_pct']:+.1f}%·{h['status']}</div>
    </div>""")
    for w in wl[:8]:
        p_cls = "priority-1" if w["channel"].startswith("A") else ("priority-2" if w["channel"].startswith("B") else "priority-3")
        tags = ""
        if w.get("c6"):
            tags += "<span class='wc-tag tag-c6'>C6</span>"
        if w.get("dbl"):
            tags += "<span class='wc-tag tag-dbl'>双RPS</span>"
        cards.append(f"""
    <div class="watch-card {p_cls}">
      <div class="wc-badge badge-buy">{w['channel'].split()[0]}·{w['score']}</div>
      <div class="wc-code">{w['code']}</div>
      <div class="wc-name">{w['name']}</div>
      <div class="wc-price">{w.get('close', '—')}</div>
      <div class="wc-signal">{w['board']}·回踩{w['pullback']['target_ma']}日线≈{w['pullback']['value']}{tags}</div>
    </div>""")
    body.append(f"""
<div class="panel">
  <h2>🔭 {weekday_cn(D)}盯盘清单（持仓 {len(ps['positions'])} + 观察池 {len(wl)} · 精选 TOP 卡）</h2>
  <div class="watch-grid">{''.join(cards)}
  </div>
</div>""")

    # ---------- 4. 持仓交易计划矩阵（完整） ----------
    ext_lines = cfg.get("extreme_lines", {})
    hk_mult = cfg.get("hk_review25_mult", 0.75)
    tot_cost = ps["totals"]["cost"]
    cash = cfg["total_invested"] - tot_cost + ps["totals"]["realized"]
    tot_eq = cash + ps["totals"]["mkt_val"]

    hold_blocks = []
    for h in ps["positions"]:
        code, strat = h["code"], h["strat"]
        price, cost, qty = h["price"], h["cost"], h["qty"]
        pnl_pct, pnl_amt, mkt_val = h["pnl_pct"], h["pnl_amt"], h["mkt_val"]
        wt_total = mkt_val / tot_eq * 100
        wt_mv = mkt_val / ps["totals"]["mkt_val"] * 100
        cls = "up" if pnl_pct >= 0 else "down"
        border = "#3ec97e" if pnl_pct >= 0 else "#ec4e4e"
        color = "#ec4e4e" if pnl_pct >= 0 else "#3ec97e"

        if strat == "港股死拿":
            review_line = cost * hk_mult
            gap = (price / review_line - 1) * 100
            plan_rows = f"""
      <tr><td>🔒 策略</td><td>港股死拿·事件/基本面止损</td><td>不设价格止损</td></tr>
      <tr><td>🔒 止损</td><td>-25%复盘线 = {review_line:.2f}</td><td>当前 {price:.2f}（距复盘线 +{gap:.0f}%）</td></tr>
      <tr><td>⬆ 加仓</td><td>—</td><td>无(不补仓)</td></tr>
      <tr><td>⬇ 减仓</td><td>触发-25%复盘线后复核</td><td>—</td></tr>
      <tr><td>📌 仓位</td><td>R1 ≤ 20%</td><td>{wt_total:.1f}%（占总资金）/ {wt_mv:.1f}%（占持仓市值）</td></tr>
      <tr><td>当日操作</td><td colspan="2"><b>持有不动，不补仓，不设价格止损</b></td></tr>"""
        elif strat == "战略持有·逻辑止损":
            plan_rows = f"""
      <tr><td>🔒 策略</td><td>战略持有·逻辑止损</td><td>不做Al Brooks止盈(8/14拍板)</td></tr>
      <tr><td>🔒 止损</td><td>逻辑止损(金价趋势/实际利率/美元/央行购金)</td><td>逻辑破坏才评估退出，不因短期破位离场</td></tr>
      <tr><td>⬆ 加仓</td><td>—</td><td>无(战略持有)</td></tr>
      <tr><td>⬇ 减仓</td><td>—</td><td>金价长期趋势破坏才评估</td></tr>
      <tr><td>📌 仓位</td><td>R1 ≤ 20%</td><td class='down'>{wt_total:.1f}%·战略例外·超R1</td></tr>
      <tr><td>当日操作</td><td colspan="2"><b>逻辑破坏才评估退出，不因短期破位离场</b></td></tr>"""
        elif strat == "已决持有·守极端线":
            ext = ext_lines.get(code)
            ext_txt = f"{ext}" if ext else "—"
            hit = f"⚠️ 已触及 {price:.2f}！" if ext and price <= ext else "未触及"
            plan_rows = f"""
      <tr><td>🔒 策略</td><td>已决持有·守极端线（8/20拍板）</td><td>豁免adaptive单一止损</td></tr>
      <tr><td>🔒 极端线</td><td>{ext_txt}</td><td class='down'><b>{hit}</b></td></tr>
      <tr><td>🔒 复核</td><td>破{ext_txt}极端线或重大利空才重评</td><td>用户复核：<b>维持持有、不补仓</b></td></tr>
      <tr><td>⬆ 加仓</td><td>—</td><td>无(不补仓)</td></tr>
      <tr><td>⬇ 减仓</td><td>重大利空或逻辑破坏</td><td>—</td></tr>
      <tr><td>📌 仓位</td><td>R1 ≤ 20%</td><td>{wt_total:.1f}%（占总资金）/ {wt_mv:.1f}%（占持仓市值）</td></tr>
      <tr><td>当日操作</td><td colspan="2"><b>守{ext_txt}极端线，用户已复核维持持有；仅重大利空/逻辑破坏才重评</b></td></tr>"""
        else:
            plan_rows = f"""
      <tr><td>🔒 策略</td><td>{strat}</td><td>{h.get('plan', '')}</td></tr>"""

        hold_blocks.append(f"""
  <div class="panel" style="border-left:3px solid {border}">
    <h3>{h['name']} <span class="code">{code}</span>
      <span style="float:right;font-size:13px;color:{color}">
        {price:.3f} <span class="{cls}">{pnl_pct:+.2f}%</span>
      </span>
    </h3>
    <div class="kpi-row">
      <div class="kpi"><div class="v">{qty:,}</div><div class="lbl">数量</div></div>
      <div class="kpi"><div class="v">{cost:.3f}</div><div class="lbl">成本</div></div>
      <div class="kpi"><div class="v {cls}">{price:.3f}</div><div class="lbl">现价</div></div>
      <div class="kpi"><div class="v {cls}">{pnl_amt:+,.0f}</div><div class="lbl">盈亏(元)</div></div>
      <div class="kpi"><div class="v">{wt_mv:.1f}%</div><div class="lbl">占持仓市值</div></div>
    </div>
    <div class="alert-y" style="margin:6px 0"><b>📌 {strat}</b></div>
    <table style="font-size:12px;margin:8px 0">
      <tr><th>规则</th><th>参数</th><th>当前状态</th></tr>
{plan_rows}
    </table>
  </div>""")

    body.append(f"""
<div class="panel">
  <h2>💼 持仓交易计划（{len(ps['positions'])}只 · {fmt_date(D)} 收盘 · 完整矩阵）</h2>
  <div class="alert-b" style="margin-bottom:10px"><b>⚠️ 持仓市值 ≈ {ps['totals']['mkt_val']:,} 元 | 已实现 {ps['totals']['realized']:+,} 元 | 合计 <b class='down'>{ps['totals']['overall']:,} 元</b> | 可用现金 ≈ {cash:,.0f} 元</b></div>
</div>
{''.join(hold_blocks)}""")

    # ---------- 5. M 区块 ----------
    m4_date = D
    m5_date = D
    body.append(f"""
<div class="panel" style="margin-bottom:8px">
  <div style="font-size:12px;color:#9aa0b0;margin-bottom:10px">
    📌 <b style="color:#b8bfce;">市场脉搏 M 模块</b>（按数据更新频率跟随看板输出）：<b>每日</b>=M1 市场广度 + M2 行业广度 + M4 期权情绪；<b>每周五</b>额外=M3 行业RPS + M5 基底计数。<b>窗口：M1 图=半年（120 交易日）</b>；<b>M4 整体=近 60 日</b>。<b>全部图形鼠标悬停显示具体数值</b>。本次数据日期：<b>M1/M2/M3 = {fmt_date(D)} 收盘</b>；<b>M4 = {fmt_date(m4_date)}</b>；<b>M5 = {fmt_date(m5_date)}</b>。
  </div>
  {m1m2m3}
  {m4}
  {m5}
</div>""")

    # ---------- 6. 观察池表格 ----------
    wrows = []
    for i, w in enumerate(wl, 1):
        wrows.append(f"""<tr><td>{i}</td><td><span class="signal-tag {sig_tag(w['channel'])}">{w['channel']}</span></td><td><strong>{w['name']}</strong> {w['code']}</td><td>{w['score']}</td><td>{'✅' if w.get('c6') else '—'}</td><td>{'✅' if w.get('dbl') else '—'}</td><td>{w.get('rps250', '—')}/{w.get('rps120', '—')}</td><td>{w['board']}</td><td>{w['pullback']['target_ma']}日线≈{w['pullback']['value']}</td><td>0（{'门控OFF' if gate=='OFF' else '待回踩'}）</td></tr>""")
    boards = {}
    for w in wl:
        boards[w["board"]] = boards.get(w["board"], 0) + 1
    board_top = " / ".join(f"{k} {v}" for k, v in sorted(boards.items(), key=lambda x: -x[1])[:5])
    body.append(f"""
<div class="panel">
  <h2>🎯 重点观察池（{fmt_date(D)} 选股 · 规则达标制 · {len(wl)} 只 · {'门控 OFF 只观察不建仓' if gate=='OFF' else '门控 ON 等回踩'}）</h2>
  <div class="alert-{'r' if gate=='OFF' else 'y'}">
    <strong>{'🔴 门控 OFF' if gate=='OFF' else '🟢 门控 ON'}（{off_txt}）：</strong>观察池 {len(wl)} 只<b>全部只观察</b>{'，等门控重新 ON + 回踩企稳再考虑首笔 10%' if gate=='OFF' else '，等回踩目标企稳再考虑首笔 10%'}。
  </div>
  <table>
    <tr><th>#</th><th>通道</th><th>标的</th><th>加分</th><th>C6三线红</th><th>双RPS</th><th>RPS250/120</th><th>板块*</th><th>建议观察回踩目标</th><th>仓位</th></tr>
    {''.join(wrows)}
  </table>
  <div class="alert-b" style="margin-top:10px"><strong>📌 板块结构：</strong>{board_top}。完整清单见 <span class="code">signals_filtered_{D}_quality_floor.csv</span>。</div>
</div>""")

    # ---------- 7. 决策流程 ----------
    flow_items = []
    if a.flow.strip():
        for ln in a.flow.replace("\\n", "\n").strip().split("\n"):
            if "|" in ln:
                t, act, note = [x.strip() for x in ln.split("|", 2)]
                flow_items.append(f"<div class='flow-item'><div class='fi-time'>{t}</div><div class='fi-action'>{act}</div><div class='fi-note'>{note}</div></div>")
    if not flow_items:
        defaults = [
            ("09:25", "竞价：指数定调", f"{idx0['name']}能否{'守住' if gate=='OFF' else '站稳'}50日线({idx0['ma50']})"),
            ("09:30-10:00", f"{'🔴 门控 OFF 确认' if gate=='OFF' else '🟢 门控 ON 确认'}", f"观察池{len(wl)}只只观察，不追高不抄底"),
            ("全天", "持仓管理", "按持仓状态表执行；触发极端线才评估"),
            ("14:30", "尾盘评估", "门控状态 + 持仓守线确认，决定次日攻守"),
        ]
        for t, act, note in defaults:
            flow_items.append(f"<div class='flow-item'><div class='fi-time'>{t}</div><div class='fi-action'>{act}</div><div class='fi-note'>{note}</div></div>")
    body.append(f"""
<div class="panel">
  <h2>🔄 {weekday_cn(D)}开盘决策流程（{('门控 OFF · 全面防守' if gate=='OFF' else '门控 ON · 等回踩')}）</h2>
  <div class="flow">{''.join(flow_items)}</div>
  <div class="alert-{'r' if gate=='OFF' else 'y'}" style="margin-top:10px"><strong>📌 纪律：</strong>{'不追高、不抄底、不摊平；观察池只观察；现金留待门控重新 ON。' if gate=='OFF' else '只做回踩买点不追高；首笔 10%（R2 动态净值×10%）；同日最多 1-2 只。'}</div>
</div>""")

    # ---------- 8. 观察指标 ----------
    irows = []
    for c, v in ms["indexes"].items():
        irows.append(f"<tr><td><strong>{v['name']} vs 50日线（{v['ma50']}）</strong></td><td>{v['close']}（{v['dist_pct']:+.1f}%）</td><td>{'站上→门控贡献' if v['dist_pct'] is not None and v['dist_pct']>=0 else '下方→门控缺口'}</td></tr>")
    irows.append(f"<tr><td><strong>中期信号（taobo #8 两指数门控）</strong></td><td>{gate}（{off_txt}）</td><td>{'可建仓（等回踩）' if gate=='ON' else '不建仓，只观察'}</td></tr>")
    body.append(f"""
<div class="panel">
  <h2>📡 核心观察指标</h2>
  <table>
    <tr><th>指标</th><th>当前值</th><th>对应操作</th></tr>
    {''.join(irows)}
  </table>
</div>""")

    # ---------- 9. 仓位管理 ----------
    tot = ps["totals"]
    ai_cnt = sum(1 for h in ps["positions"] if h["strat"] in ("已决持有·守极端线", "反弹清仓"))
    strat_cnt = len(ps["positions"]) - ai_cnt
    r1b_lim = "≤ 4 只" if gate == "OFF" else "≤ 8 只"
    body.append(f"""
<div class="panel">
  <h2>💰 仓位管理（taobo-O'Neil · {'门控 OFF · 弱势市' if gate=='OFF' else '门控 ON · 趋势市'}）</h2>
  <table>
    <tr><th>规则</th><th>参数</th><th>当前状态</th></tr>
    <tr><td>R1b 环境持仓</td><td>{r1b_lim}</td><td>AI策略仓 {ai_cnt} 只，战略持有 {strat_cnt} 只不计入</td></tr>
    <tr><td>R1 单票上限</td><td>≤ 总资金 20%</td><td>按持仓表 weight 标注超限项（战略持有例外）</td></tr>
    <tr><td>总仓位</td><td>{'弱势市 ≤ 半仓' if gate=='OFF' else '趋势市可加仓'}</td><td>持仓市值≈{tot['mkt_val']/10000:.2f}万 + 现金留用</td></tr>
    <tr><td>R2 建仓节奏</td><td>10%→6%→4%（动态净值×10%）</td><td>{'门控 OFF 暂停 R2' if gate=='OFF' else '门控 ON 可启动（等回踩）'}</td></tr>
    <tr><td>R3/R4 止盈</td><td>adaptive 组合A（仅 A 股个股）；ETF 用 Al Brooks 锚；黄金战略持有逻辑止损</td><td>按持仓状态表执行</td></tr>
    <tr><td>R7-2 淘弱留强</td><td>新信号 RPS250≥90 且双RPS</td><td>持仓未满暂不触发</td></tr>
  </table>
</div>""")

    # ---------- 10. 不碰清单 ----------
    dont_items = []
    if a.dont.strip():
        for ln in a.dont.replace("\\n", "\n").strip().split("\n"):
            if "|" in ln:
                t, why = [x.strip() for x in ln.split("|", 1)]
                dont_items.append((t, why))
    if not dont_items:
        defaults = [
            ("门控 OFF 下建新仓（观察池）", "3 指数 50 日线下，建仓条件不满足"),
            ("追高观察池标的", "等回踩目标均线企稳，不追涨"),
            ("给深套仓补仓摊平", "深套只做反弹减仓/事件止损，绝不摊平"),
            ("对黄金 ETF 按 Al Brooks 破锚减/清", "8/14 拍板：黄金战略持有·逻辑止损"),
        ]
        for t, why in defaults:
            dont_items.append((t, why))
    body.append(f"""
<div class="panel">
  <h2>🚫 {weekday_cn(D)}绝不做的{len(dont_items)}件事</h2>
  <table>
    <tr><th>#</th><th>不做什么</th><th>原因</th></tr>
    {''.join(f'<tr><td>{i}</td><td>❌ {t}</td><td>{why}</td></tr>' for i, (t, why) in enumerate(dont_items, 1))}
  </table>
</div>""")

    # ---------- 11. 核心思路 ----------
    core = a.core if a.core.strip() else (f"门控 {gate} · 谨慎防守：观察池 {len(wl)} 只只观察，持仓按纪律管理，不追高不抄底。" if gate == "OFF" else f"门控 ON · 等回踩：观察池 {len(wl)} 只回踩企稳后首笔 10%。")
    body.append(f"<div class='panel' style='text-align:center;background:#262a35;border-color:#333842;'><div style='font-size:15px;color:#9aa0b0;'>🎯 核心思路：<b style='color:#e0e4ec;'>{core}</b></div></div>")

    # ---------- Footer ----------
    footer = f"⚠️ 本文仅作方法论演算，不构成投资建议。股市有风险，投资需谨慎。 | 数据来源：通达信本地 .day + tdx MCP + 陶博士筛选（taobo-O'Neil {fmt_date(D)}）+ WebSearch（港股收盘） | 生成时间：{D[:4]}-{D[4:6]}-{D[6:]} CST"

    # ---------- 组装 ----------
    tpl = open(TPL, encoding="utf-8").read()
    html = tpl.replace("{{TITLE}}", title).replace("{{BODY}}", "\n".join(body)).replace("{{FOOTER}}", footer)

    out = os.path.join(a.out_dir, f"统一交易看板_{D}.html")
    open(out, "w", encoding="utf-8").write(html)
    print("WROTE", out, len(html), "bytes")


if __name__ == "__main__":
    main()
