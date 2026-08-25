# -*- coding: utf-8 -*-
"""
M4 期权情绪引擎 — 沽购比 + 90/50/10分位带 + ETF价格对照
================================================================
数据源(通达信MCP拉取, 固化在 option_oi_*.json):
- 期权OI: tdx_kline(期权合约, setcode=8, target=1) VolInStock 字段
- ETF价格: 通达信本地 vipdoc/{sh,sz}/lday (510300=sh, 159915=sz)

计算:
- 每日沽购比 = Σ(认沽合约OI) / Σ(认购合约OI)
- 90/50/10 分位带 = PERCENTILE.INC(近60日沽购比序列, 0.9/0.5/0.1)
- 图: 折线/时间轴近60日 (2026-08-12 用户最终口径: M4 整体维持 60 日)
- ETF 价格线 + MA20 对照

用法: python option_sentiment.py [--data option_oi_510300_2612.json] [--etf 510300]
"""
import os, sys, json, struct, datetime

MKT_PULSE = r"<PROJECT_ROOT>\deliverables\taobo-daily\market_pulse"
TDX_ROOT = r"D:\Sofeware\TongDaXin"

def read_etf_close(code, root=TDX_ROOT, max_bars=300):
    """读ETF日K收盘(510300=sh, 159915=sz)"""
    mkt = "sh" if code.startswith(("5", "6")) else "sz"
    path = os.path.join(root, "vipdoc", mkt, "lday", f"{mkt}{code}.day")
    if not os.path.exists(path):
        return []
    data = open(path, "rb").read()
    n = len(data) // 32
    rows = []
    for i in range(max(0, n - max_bars), n):
        d, o, h, l, c, amt, vol, _ = struct.unpack("<8I", data[i*32:(i+1)*32])
        rows.append({"date": str(d), "close": c/100.0})
    return rows

def percentile(sorted_vals, p):
    """线性插值百分位(与 PERCENTILE.INC 一致)"""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = p * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac

def compute(data, etf_code):
    # 组装每日 Σ购OI / Σ沽OI
    calls = {k: v for k, v in data.items() if k.startswith("C")}
    puts = {k: v for k, v in data.items() if k.startswith("P")}
    all_dates = sorted(set(d for c in calls.values() for d in c))
    daily = []
    for d in all_dates:
        c_oi = sum(c.get(d, 0) for c in calls.values())
        p_oi = sum(p.get(d, 0) for p in puts.values())
        if c_oi > 0 and p_oi > 0:
            daily.append({"date": d, "call": c_oi, "put": p_oi,
                          "pcr": round(p_oi / c_oi, 3)})
    # 分位带(近60日口径, 2026-08-12 用户澄清: 分位带维持原状, 仅图时间轴半年)
    seq = [x["pcr"] for x in daily[-60:]]
    ss = sorted(seq)
    bands = {
        "p90": round(percentile(ss, 0.9), 3),
        "p50": round(percentile(ss, 0.5), 3),
        "p10": round(percentile(ss, 0.1), 3),
    }
    # ETF价格对照
    etf_rows = read_etf_close(etf_code)
    etf_by_date = {r["date"]: r["close"] for r in etf_rows}
    for x in daily:
        x["etf"] = round(etf_by_date.get(x["date"], 0), 3)
    return daily, bands

def analyze(daily, bands):
    """自动分析文字(规则化, 基于过往数据)"""
    seq = [x["pcr"] for x in daily]
    cur = daily[-1]
    cur_pcr = cur["pcr"]
    p90, p50, p10 = bands["p90"], bands["p50"], bands["p10"]
    lines = []
    # 1. 当日定位
    if cur_pcr >= p90:
        zone = "90%分位上方(极度看跌/对冲)"
        cls = "sig-dn"
    elif cur_pcr <= p10:
        zone = "10%分位下方(极度乐观)"
        cls = "sig-up"
    elif cur_pcr >= p50:
        zone = "中位上方(偏空)"
        cls = "sig-nt"
    else:
        zone = "中位下方(偏多)"
        cls = "sig-nt"
    lines.append(f"最新日<b>{daily[-1]['date']}</b>: 沽购比 <b class='{cls}'>{cur_pcr}</b>(沽OI {cur['put']} / 购OI {cur['call']}), 处于近60日<b>{zone}</b>(90分位 {p90} / 中位 {p50} / 10分位 {p10})。")
    # 2. 趋势(5日)
    if len(seq) >= 6:
        d5 = seq[-1] - seq[-6]
        if d5 > 0.05:
            lines.append(f"沽购比近5日<b class='sig-dn'>上升 {seq[-6]}→{seq[-1]}(+{d5:.2f})</b>, 看跌/对冲力量增强。")
        elif d5 < -0.05:
            lines.append(f"沽购比近5日<b class='sig-up'>下降 {seq[-6]}→{seq[-1]}({d5:.2f})</b>, 看跌/对冲力量减弱。")
        else:
            lines.append(f"沽购比近5日 {seq[-6]}→{seq[-1]}({d5:+.2f}), 情绪平稳。")
    # 3. 极端信号
    if cur_pcr >= p90 * 0.98:
        lines.append(f"<b class='sig-dn'>沽购比逼近历史极端高位</b> — 拥挤看跌/对冲, 若价格企稳则为反向乐观信号(物极必反), 关注ETF价格是否出现底部背离。")
    elif cur_pcr <= p10 * 1.02:
        lines.append(f"<b class='sig-up'>沽购比处于历史极端低位</b> — 市场过度乐观, 警惕高位回落风险。")
    # 4. 与ETF价格背离判断
    etf_cur = daily[-1].get("etf", 0)
    if etf_cur > 0 and len(daily) >= 10:
        etf5 = [x["etf"] for x in daily[-5:] if x["etf"] > 0]
        if len(etf5) >= 3:
            etf_trend = etf5[-1] - etf5[0]
            pcr_trend = seq[-1] - seq[-6] if len(seq) >= 6 else 0
            if etf_trend > 0 and pcr_trend > 0.05:
                lines.append(f"价格上行(ETF {etf_cur})但沽购比同步上升 — <b class='sig-nt'>上涨伴随对冲增加, 健康度存疑</b>, 谨慎追高。")
            elif etf_trend < 0 and pcr_trend < -0.05:
                lines.append(f"价格下行但沽购比回落 — <b class='sig-up'>恐慌/对冲盘离场, 下跌动能衰减</b>, 关注企稳信号。")
    return "".join(f"<div>{l}</div>" for l in lines)

def render_svg(daily, bands):
    """沽购比折线 + 分位带 (时间轴=近60日, 2026-08-12 用户最终口径: M4 整体维持 60 日)"""
    W, H = 640, 220
    pad_l, pad_r, pad_t, pad_b = 34, 8, 12, 22
    plot_w, plot_h = W - pad_l - pad_r, H - pad_t - pad_b
    seq = [x["pcr"] for x in daily[-60:]]
    vmax = max(seq) * 1.15
    vmin = min(seq) * 0.85
    vrange = max(vmax - vmin, 0.1)

    def y(v):
        return pad_t + plot_h * (vmax - v) / vrange
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="min-width:{W}px">']
    # 分位带填充(90-10)
    parts.append(f'<rect x="{pad_l}" y="{y(bands["p90"]):.1f}" width="{plot_w:.1f}" height="{y(bands["p10"])-y(bands["p90"]):.1f}" fill="#2a3050" opacity="0.35"/>')
    for p, color in [(bands["p90"], "#5aa8f0"), (bands["p50"], "#e8a830"), (bands["p10"], "#5aa8f0")]:
        yy = y(p)
        name = "90分位" if p == bands["p90"] else ("中位" if p == bands["p50"] else "10分位")
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{W-pad_r}" y2="{yy:.1f}" stroke="{color}" stroke-width="1" stroke-dasharray="4,3" data-tip="{name} {p}"/>')
        parts.append(f'<text x="{W-pad_r-2}" y="{yy-3:.1f}" font-size="9" fill="{color}" text-anchor="end">{p}</text>')
    # PCR 折线
    n = len(seq)
    bw = plot_w / n
    pts = []
    for i in range(n):
        x = pad_l + i * bw + bw / 2
        pts.append(f"{x:.1f},{y(seq[i]):.1f}")
    parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#ec4e4e" stroke-width="1.8"/>')
    # 折线点悬停提示: 透明圆点 + data-tip(自定义tooltip, 2026-08-12; r=5 便于命中)
    dts = [x["date"] for x in daily[-60:]]
    daily60 = daily[-60:]
    for i in range(n):
        x = pad_l + i * bw + bw / 2
        yy = y(seq[i])
        dd = dts[i]
        rec = daily60[i]
        tip = f"{dd} 沽购比 {seq[i]}（沽 {rec['put']} / 购 {rec['call']}）ETF {rec.get('etf', 0)}"
        parts.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="5" fill="transparent" data-tip="{tip}"/>')
    # ETF价格(右上角小字, 2026-08-12 用户反馈: 右下会与末日期刻度重叠, 改放右上)
    etfs = [x["etf"] for x in daily[-60:]]
    if etfs and etfs[-1] > 0:
        _d = daily[-1]["date"]
        parts.append(f'<text x="{W-pad_r}" y="{pad_t-3}" font-size="9" fill="#6b7180" text-anchor="end">ETF {daily[-1]["etf"]} ({_d[4:6]}-{_d[6:]})</text>')
    # 日期标注(首/中/末)
    for idx in [0, n//2, n-1]:
        x = pad_l + idx * bw + bw / 2
        parts.append(f'<text x="{x:.1f}" y="{H-6}" font-size="9" fill="#6b7180" text-anchor="middle">{dts[idx][4:6]}-{dts[idx][6:]}</text>')
    parts.append("</svg>")
    return "".join(parts)

def main():
    data_file = os.path.join(MKT_PULSE, "option_oi_510300_2612.json")
    etf_code = "510300"
    etf_name = "沪深300ETF"
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--data" and i+1 < len(args):
            data_file = args[i+1]
        if a == "--etf" and i+1 < len(args):
            etf_code = args[i+1]

    raw = json.load(open(data_file, encoding="utf-8"))
    daily, bands = compute(raw, etf_code)
    asof = daily[-1]["date"]
    print(f"沽购比序列 {len(daily)} 日, 最新 {asof}: PCR={daily[-1]['pcr']} (购{daily[-1]['call']}/沽{daily[-1]['put']})")
    print(f"分位带: 90%={bands['p90']} 中位={bands['p50']} 10%={bands['p10']}")

    # 渲染面板
    css = """
<style>
.mkt-panel{background:#22252e;border:1px solid #333842;border-radius:10px;padding:14px 16px;margin-bottom:14px}
.mkt-panel h3{font-size:14px;color:#b8bfce;margin-bottom:10px}
.mkt-kpi{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.mkt-kpi .kpi{background:#2a2e38;border-radius:8px;padding:7px 11px;min-width:84px;text-align:center}
.mkt-kpi .kpi .v{font-size:16px;font-weight:700}
.mkt-kpi .kpi .l{font-size:10px;color:#6b7180;margin-top:2px}
.mkt-chart{width:100%;overflow-x:auto;margin-bottom:8px}
.mkt-note{font-size:12px;color:#9aa0b0;margin:6px 0}
.mkt-analysis{background:#262a35;border-left:3px solid #5aa8f0;border-radius:6px;padding:9px 13px;margin-top:10px;font-size:12px;color:#c8d0dc;line-height:1.7}
.mkt-analysis b{color:#f0f2f5}
.sig-up{color:#ec4e4e}.sig-dn{color:#3ec97e}.sig-nt{color:#e8a830}
</style>"""
    cur = daily[-1]
    kpi = [
        ("沽购比", cur["pcr"], f'90分位 {bands["p90"]}'),
        ("购OI", cur["call"], "张"),
        ("沽OI", cur["put"], "张"),
        ("ETF", cur.get("etf", "-"), etf_name),
        ("样本", len(daily), "日(12月合约平值±2档)"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{k}{u}</div></div>' for k, v, u in kpi)
    # 全局悬停 tooltip JS(幂等, 与 market_pulse 面板共用 #mkt-tip, 2026-08-12)
    tip_js = """
<script>
(function(){ if (window.__mktTip) return; window.__mktTip = 1;
var d = document.createElement('div'); d.id = 'mkt-tip';
d.style.cssText = 'position:fixed;z-index:99999;pointer-events:none;display:none;background:rgba(18,20,26,.96);color:#e8ecf4;font-size:11px;line-height:1.55;padding:6px 10px;border-radius:6px;border:1px solid #3a4060;box-shadow:0 3px 12px rgba(0,0,0,.45);white-space:nowrap;font-family:Consolas,"Microsoft YaHei",monospace';
document.body.appendChild(d);
document.addEventListener('mouseover', function(e){
  var t = e.target && e.target.closest ? e.target.closest('[data-tip]') : null;
  if (!t) { d.style.display = 'none'; return; }
  d.textContent = t.getAttribute('data-tip'); d.style.display = 'block';
});
document.addEventListener('mousemove', function(e){
  if (d.style.display === 'block') {
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + 260 > window.innerWidth) x = e.clientX - 270;
    if (y + 70 > window.innerHeight) y = e.clientY - 50;
    d.style.left = x + 'px'; d.style.top = y + 'px';
  }
});
})();
</script>
"""
    html = f"""
{css}
{tip_js}
<div class="mkt-panel">
  <h3>📉 期权情绪·沽购比分位带 ({etf_name} {etf_code} 12月合约 平值±2档) — {asof}</h3>
  <div class="mkt-kpi">{kpi_html}</div>
  <div class="mkt-chart">{render_svg(daily, bands)}</div>
  <div class="mkt-note">红线=沽购比(沽OI/购OI) · 蓝虚线=90%/10%分位 · 黄虚线=中位 · 数据源: 通达信MCP期权OI(VolInStock, 免费)</div>
  <div class="mkt-analysis">{analyze(daily, bands)}</div>
</div>"""
    out = os.path.join(MKT_PULSE, f"option_sentiment_panel_{asof}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已输出: {out}")

if __name__ == "__main__":
    main()
