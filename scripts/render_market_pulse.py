# -*- coding: utf-8 -*-
"""
看板渲染 — 市场广度「下雨图」 + 行业温度(RPS/新高比例) HTML 区块
================================================================
输入: deliverables/taobo-daily/market_pulse/breadth_YYYYMMDD.json
      deliverables/taobo-daily/market_pulse/industry_YYYYMMDD.json
输出: 两个自包含 HTML 区块(深色主题, 与统一交易看板一致):
      1. 市场广度面板: 下雨图(SVG)+ 关键KPI + 自动分析文字
      2. 行业温度面板: 行业RPS TOP10 条形图 + 新高比例 + 自动分析文字

用法: python render_market_pulse.py --date 20260812 [--out-dir ...]
"""
import os, sys, json, datetime

BREADTH_DIR = r"<PROJECT_ROOT>\deliverables\taobo-daily\market_pulse"

# ---------- 图表样式(与看板深色主题一致) ----------
CHART_CSS = """
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
.rank-bar{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px}
.rank-bar .name{width:70px;text-align:right;color:#c8d0dc}
.rank-bar .bar{flex:1;height:14px;background:#2a2e38;border-radius:3px;overflow:hidden}
.rank-bar .fill{height:100%;border-radius:3px}
.rank-bar .val{width:52px;color:#9aa0b0;font-size:11px}
"""

# ---------- 全局悬停 tooltip JS(幂等: 只创建一次#mkt-tip, 2026-08-12 用户指令: 原生title不可靠, 改自定义) ----------
TIP_JS = """
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

def fmt_date(d):
    """20260812 -> 08-12"""
    return f"{d[4:6]}-{d[6:]}"

# ---------- M1 广度: 自动分析文字(基于过往数据规则) ----------
def analyze_breadth(b):
    s = b["series"]
    dates = s["dates"]
    n = len(dates)
    nh, nl, net = s["new_highs"], s["new_lows"], s["net"]
    hp, hpma20 = s["high_pct"], s["high_pct_ma20"]
    ic, ima = s["idx_close"], s["idx_ma50"]

    lines = []
    # 1. 当日状态
    cur_net = net[-1]; cur_hp = hp[-1]; cur_nl = nl[-1]
    lines.append(f"最新日<b>{fmt_date(dates[-1])}</b>: 新高 <b class='sig-up'>{nh[-1]}只</b> / 新低 <b class='sig-dn'>{nl[-1]}只</b> / 差值 <b>{cur_net:+d}</b>, 新高占比 {cur_hp:.2f}%(MA20 {hpma20[-1]:.2f}%)。")

    # 2. 差值趋势(5日斜率)
    net5 = net[-5:]
    slope = net5[-1] - net5[0]
    if slope > 15:
        lines.append(f"差值近5日 <b class='sig-up'>上升 {net5[0]}→{net5[-1]}(+{slope})</b>, 广度在扩张。")
    elif slope < -15:
        lines.append(f"差值近5日 <b class='sig-dn'>下降 {net5[0]}→{net5[-1]}({slope})</b>, 广度在收缩。")
    else:
        lines.append(f"差值近5日 {net5[0]}→{net5[-1]} 变化不大({slope:+d}), 广度平稳。")

    # 3. 新高占比 vs 20日均
    cur_hp20 = hpma20[-1]
    if cur_hp > cur_hp20 * 1.3:
        lines.append(f"新高占比({cur_hp:.2f}%)显著高于20日均({cur_hp20:.2f}%), <b class='sig-up'>个股层面转强</b>。")
    elif cur_hp < cur_hp20 * 0.7:
        lines.append(f"新高占比({cur_hp:.2f}%)显著低于20日均({cur_hp20:.2f}%), <b class='sig-dn'>个股层面走弱</b>。")
    else:
        lines.append(f"新高占比({cur_hp:.2f}%)与20日均({cur_hp20:.2f}%)接近, 广度中性。")

    # 4. 新低压力
    if cur_nl >= 20:
        lines.append(f"新低家数 {cur_nl} 只(≥20), <b class='sig-dn'>下方破位压力明显</b>, 警惕补跌。")
    elif cur_nl <= 5:
        lines.append(f"新低家数仅 {cur_nl} 只, 下方抛压有限。")

    # 5. 指数 vs MA50(中期信号门控)
    if ic[-1] is not None and ima[-1] is not None:
        above = ic[-1] > ima[-1]
        dist = (ic[-1] / ima[-1] - 1) * 100
        if above:
            lines.append(f"上证指数 {ic[-1]:.0f} 站上MA50({ima[-1]:.0f}, +{dist:.1f}%), <b class='sig-up'>中期信号ON</b>(#8门控: 允许新仓)。")
        else:
            lines.append(f"上证指数 {ic[-1]:.0f} 位于MA50({ima[-1]:.0f}, {dist:+.1f}%), <b class='sig-nt'>中期信号OFF</b>(#8门控: 不建新仓, 已持仓按纪律管理)。")

    # 6. 综合
    if cur_net > 0 and (ic[-1] is not None and ima[-1] is not None and ic[-1] > ima[-1]):
        verdict = "广度与趋势共振偏强"
        cls = "sig-up"
    elif cur_net < -30:
        verdict = "广度显著恶化, 防御优先"
        cls = "sig-dn"
    elif cur_net > 0:
        verdict = "广度改善但趋势未确认, 结构市特征"
        cls = "sig-nt"
    else:
        verdict = "广度中性偏弱, 等趋势确认"
        cls = "sig-nt"
    lines.append(f"<b>综合: <span class='{cls}'>{verdict}</span></b>。")
    return "".join(f"<div>{l}</div>" for l in lines)

# ---------- M1 广度: SVG 下雨图 ----------
def render_breadth_svg(b, max_bars=120):
    """下雨图窗口=近半年120交易日(2026-08-12 用户指令 45→120)"""
    s = b["series"]
    dates = s["dates"][-max_bars:]
    nh = s["new_highs"][-max_bars:]
    nl = [-x for x in s["new_lows"][-max_bars:]]
    net = s["net"][-max_bars:]

    W, H = 640, 240
    pad_l, pad_r, pad_t, pad_b = 34, 8, 12, 20
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    maxv = max(max(nh), max(abs(x) for x in nl), 10)
    mid = pad_t + plot_h * (maxv / (2 * maxv))  # 中线(0点)
    bar_w = plot_w / len(nh)

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="min-width:{W}px">']
    # 网格线
    for g in range(0, 5):
        gy = pad_t + plot_h * g / 4
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W-pad_r}" y2="{gy:.1f}" stroke="#2e3340" stroke-width="1"/>')
    # 0 轴
    parts.append(f'<line x1="{pad_l}" y1="{mid:.1f}" x2="{W-pad_r}" y2="{mid:.1f}" stroke="#4a5060" stroke-width="1.2"/>')
    # 柱: 新高红(向上), 新低绿(向下); data-tip 悬停显示当日数据(自定义tooltip JS, 2026-08-12)
    for i in range(len(nh)):
        x = pad_l + i * bar_w + bar_w * 0.18
        bw = bar_w * 0.64
        d = fmt_date(dates[i])
        tip = f"{d} 新高{nh[i]} / 新低{abs(nl[i])} / 差值{net[i]:+d}"
        if nh[i] > 0:
            hh = plot_h * nh[i] / (2 * maxv)
            parts.append(f'<rect x="{x:.1f}" y="{mid-hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="#ec4e4e" opacity="0.85" rx="1" data-tip="{tip}"/>')
        if nl[i] < 0:
            hh = plot_h * abs(nl[i]) / (2 * maxv)
            parts.append(f'<rect x="{x:.1f}" y="{mid:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="#3ec97e" opacity="0.85" rx="1" data-tip="{tip}"/>')
    # 差值折线
    pts = []
    for i in range(len(net)):
        x = pad_l + i * bar_w + bar_w / 2
        y = mid - plot_h * net[i] / (2 * maxv)
        pts.append(f"{x:.1f},{y:.1f}")
    parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#e8a830" stroke-width="1.6"/>')
    # 差值点悬停提示(透明圆点, r=5 便于命中)
    for i in range(len(net)):
        x = pad_l + i * bar_w + bar_w / 2
        y = mid - plot_h * net[i] / (2 * maxv)
        d = fmt_date(dates[i])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="transparent" data-tip="{d} 差值 {net[i]:+d}"/>')
    # 日期标注(首/中/末)
    for idx in [0, len(dates)//2, len(dates)-1]:
        x = pad_l + idx * bar_w + bar_w / 2
        parts.append(f'<text x="{x:.1f}" y="{H-6}" font-size="9" fill="#6b7180" text-anchor="middle">{fmt_date(dates[idx])}</text>')
    # Y轴刻度
    parts.append(f'<text x="{pad_l-5}" y="{mid+3:.1f}" font-size="9" fill="#6b7180" text-anchor="end">0</text>')
    parts.append(f'<text x="{pad_l-5}" y="{pad_t+4}" font-size="9" fill="#ec4e4e" text-anchor="end">{2*maxv}</text>')
    parts.append(f'<text x="{pad_l-5}" y="{H-pad_b-2}" font-size="9" fill="#3ec97e" text-anchor="end">-{2*maxv}</text>')
    parts.append("</svg>")
    return "".join(parts)

# ---------- M2/M3 行业: 自动分析文字 ----------
def analyze_industry(ind):
    items = ind["industries"]
    if not items:
        return "<div>无行业数据</div>"
    top3 = items[:3]
    bot3 = items[-3:]
    # 新高比例>1% 的行业
    hot = [r for r in items if r["high_ratio"] >= 1.0]
    lines = []
    tnames = "、".join(f"<b>{r['name']}</b>(RPS{r['rps']:.0f})" for r in top3)
    lines.append(f"周度强势行业: {tnames}。")
    if hot:
        hnames = "、".join(f"{r['name']}({r['high_ratio']:.1f}%)" for r in hot[:5])
        lines.append(f"新高家数占比较高的行业: {hnames} — 板块内部共振明显的方向。")
    else:
        lines.append("全行业新高占比均低于1%, <b class='sig-dn'>当前无板块出现广度共振</b>, 市场以存量轮动为主。")
    if bot3:
        bnames = "、".join(f"{r['name']}(RPS{r['rps']:.0f}·{r['week_chg']:+.1f}%)" for r in bot3)
        lines.append(f"弱势行业: {bnames}, 暂回避。")
    # 与持仓/观察池相关的行业提示(若有)
    watch = {"医药": "示例创新药ETF 513999/医药持仓", "半导体": "示例科技股 000999", "元器件": "示例科技股 000999",
             "有色": "示例有色股类/示例有色股B 601999", "黄金": "", "汽车类": "示例整车股 002999", "房地产": ""}
    hits = []
    for r in items[:10]:
        if r["name"] in watch and watch[r["name"]]:
            hits.append(f"{r['name']}(RPS{r['rps']:.0f})→{watch[r['name']]}")
    if hits:
        lines.append(f"与持仓/观察池相关: {'; '.join(hits)}。")
    return "".join(f"<div>{l}</div>" for l in lines)

# ---------- M2/M3 行业: TOP10 条形图 ----------
def render_industry_bars(ind, topn=10):
    items = ind["industries"][:topn]
    parts = []
    maxrps = max(r["rps"] for r in items) if items else 100
    for r in items:
        w = max(4, r["rps"] / maxrps * 100)
        color = "#ec4e4e" if r["rps"] >= 80 else ("#e8a830" if r["rps"] >= 50 else "#3ec97e")
        # data-tip 悬停显示具体数据(自定义tooltip JS, 2026-08-12)
        tip = f"{r['name']} RPS {r['rps']:.0f} · 周涨幅 {r['week_chg']:+.1f}% · 新高占比 {r['high_ratio']:.2f}% · 新高{r.get('new_highs',0)}/新低{r.get('new_lows',0)}"
        parts.append(
            f'<div class="rank-bar" data-tip="{tip}"><span class="name">{r["name"]}</span>'
            f'<div class="bar"><div class="fill" style="width:{w:.0f}%;background:{color}"></div></div>'
            f'<span class="val">RPS {r["rps"]:.0f} · {r["week_chg"]:+.1f}%</span></div>'
        )
    return "".join(parts)

# ---------- 组装两个面板 ----------
def build_panels(breadth, industry, asof):
    css = f"<style>{CHART_CSS}</style>"
    # M1 广度面板
    s = breadth["series"]
    kpi = [
        ("新高", f'<span class="sig-up">{s["new_highs"][-1]}</span>', "只"),
        ("新低", f'<span class="sig-dn">{s["new_lows"][-1]}</span>', "只"),
        ("差值", f'{s["net"][-1]:+d}', "新高-新低"),
        ("新高占比", f'{s["high_pct"][-1]:.2f}%', f'MA20 {s["high_pct_ma20"][-1]:.2f}%'),
        ("样本", breadth["total_stocks"], "只A股(250日)"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{k}{u}</div></div>'
        for k, v, u in kpi
    )
    m1 = f"""
<div class="mkt-panel">
  <h3>🌧️ 市场广度·下雨图 (250日新高/新低) — {fmt_date(asof)}</h3>
  <div class="mkt-kpi">{kpi_html}</div>
  <div class="mkt-chart">{render_breadth_svg(breadth)}</div>
  <div class="mkt-note">红柱=创250日新高家数(向上) · 绿柱=创新低家数(向下) · 黄线=差值(新高−新低) · 数据源: 通达信本地vipdoc({breadth["total_stocks"]}只, 免费)</div>
  <div class="mkt-analysis">{analyze_breadth(breadth)}</div>
</div>"""

    # M2/M3 行业面板
    ind = industry["industries"]
    top_rps = ind[0]["rps"] if ind else 0
    hot_cnt = sum(1 for r in ind if r["high_ratio"] >= 1.0)
    kpi2 = [
        ("行业数", len(ind), "个(通达信)"),
        ("RPS榜首", ind[0]["name"] if ind else "-", f'RPS {top_rps:.0f}'),
        ("共振行业", hot_cnt, "个(新高占比≥1%)"),
    ]
    kpi2_html = "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{k}{u}</div></div>'
        for k, v, u in kpi2
    )
    m2 = f"""
<div class="mkt-panel">
  <h3>🏭 行业温度 (行业RPS=周涨幅排名0-100 · 行业新高比例) — {fmt_date(asof)}</h3>
  <div class="mkt-kpi">{kpi2_html}</div>
  <div class="mkt-chart">{render_industry_bars(industry)}</div>
  <div class="mkt-note">RPS≥80 红(强) · 50-80 黄(中) · &lt;50 绿(弱) · 数据源: 通达信本地(行业归属 tdxhy.cfg + 日K vipdoc, 免费)</div>
  <div class="mkt-analysis">{analyze_industry(industry)}</div>
</div>"""
    return TIP_JS + css + m1 + m2

def main():
    date_arg = None
    out_dir = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--date" and i + 1 < len(args):
            date_arg = args[i + 1]
        if a == "--out-dir" and i + 1 < len(args):
            out_dir = args[i + 1]
    if not date_arg:
        date_arg = datetime.date.today().strftime("%Y%m%d")

    bpath = os.path.join(BREADTH_DIR, f"breadth_{date_arg}.json")
    ipath = os.path.join(BREADTH_DIR, f"industry_{date_arg}.json")
    if not os.path.exists(bpath):
        print(f"缺少广度数据: {bpath}")
        sys.exit(1)
    if not os.path.exists(ipath):
        print(f"缺少行业数据: {ipath}")
        sys.exit(1)

    breadth = json.load(open(bpath, encoding="utf-8"))
    industry = json.load(open(ipath, encoding="utf-8"))
    html = build_panels(breadth, industry, date_arg)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"market_pulse_panels_{date_arg}.html")
    else:
        out = os.path.join(BREADTH_DIR, f"market_pulse_panels_{date_arg}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已输出: {out}")

if __name__ == "__main__":
    main()
