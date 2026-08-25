---
name: trading-dashboard
description: 生成和维护统一A股交易看板HTML。当用户要求"更新看板""生成交易看板""明天的交易计划""复盘并生成看板""交易计划以看板形式列出"时使用。看板整合持仓状态、候选标的进场条件、止盈止损价位、市场状态、仓位分配、决策流程和禁止清单。每个标的名称必须带交易代码。规则/口径以 taobo-O'Neil 的《策略档案_市场环境-选股-仓位管理.md》为对外唯一口径，该档案变动须同步本 skill 的门控/仓位/市场脉搏呈现。
agent_created: true
---

# Trading Dashboard — 统一A股交易看板

## Purpose

Generate and maintain a unified, self-contained HTML trading dashboard that consolidates the user's currently tracked stocks (holdings, candidates, observation anchors, do-not-touch list) into a single page.

**The dashboard is a display framework, not a prescriptive rulebook.** Which stocks to track, how many, and what position sizing to apply are determined by the user's current portfolio and the analysis from `wb-finance-skill` references (trade-plan, position-sizing, stop-discipline, monitor-alert, market-state, etc.). This skill only governs the HTML output format and presentation.

## When to Use

Trigger when user says any of:
- "更新看板" / "生成看板" / "交易看板"
- "明天的交易计划" / "交易计划以看板形式列出"
- "复盘今天的盘面" + (implied: generate dashboard)
- "帮我更新交易看板数据"

## Prerequisite Skills

Before generating the dashboard, load these for data access and analysis:
- `taobo-O'Neil` skill — 提供每日筛选产出（`deliverables/taobo-daily/daily-screening-YYYY-MM-DD.md` 重点观察池）+ 仓位管理规则（R1-R7 / dr 引擎 / Al Brooks 止盈），本看板只做呈现
- **规则/口径唯一对外档案（2026-08-25 定稿）**：`taobo-O'Neil/策略档案_市场环境-选股-仓位管理.md`（三模块「市场环境辨别 · 选股 · 仓位管理」总结产物）。**该档案变动（引擎/门控/因子/排序/阈值等）审批通过后，须同步本 skill 的门控（market_state）、仓位（Position Sizing）、市场脉搏（M1-M5）呈现口径，保持两边一致**；本 skill 不另立规则，一律引用该档案 + taobo-O'Neil SKILL.md
- **数据源固定矩阵（本地-first，见下方「Data Access」）** — A股/ETF/指数收盘与K线取自本地 `vipdoc/*.day`，港股 WebSearch 兜底，期权 OI 取自 tdx MCP；**`neodata-financial-search` 已弃用（8/12 起路径不存在）**
- Market Pulse (M1-M5) 100% 本地通达信数据，仅需本 skill 自带 scripts（`scripts/` 下 market_breadth / industry_analysis / render_market_pulse / option_sentiment / base_count），无需额外 skill

## Data Access（数据源固定矩阵 · Local-First · 2026-08-13 定稿）

> 💰 **省接口费策略（用户指令 2026-08-07 强化，2026-08-13 定稿）**：**数据源矩阵已固定，直接照用，禁止每次重新探索**——完整清单见 `references/data-sources.md`。要点：
> - **A股/ETF/指数收盘与K线** → 本地 `D:\Sofeware\TongDaXin\vipdoc\{sh,sz,bj}\lday\*.day`（32字节/条 `<8I` 解析；**精度：A股/指数 ÷100，ETF ÷1000**——8/13 实测坑；上证指数必须显式读 `sh000001.day`；本地无港股）
> - **港股收盘** → WebSearch 兜底（`"股票名 代码 年月日 收盘价"`，8/13 验证可用）
> - **期权 OI（M4 唯一源）** → tdx MCP `tdx_kline`（**必带 target=1 + setcode=8，code=8位数字**）；MCP 断连则 M4 标注"数据截至最近可拉日"，不阻断
> - **实时行情/盘口** → tdx MCP（断连时本地 .day 兜底，ETF 行情 MCP 有 1 日滞后）
> - **选股/RPS/财务** → 本地管线（taobo-O'Neil：screener_pool_full.csv + extdata + fundamental_filter）
> - ~~neodata-financial-search~~ **已弃用**（8/12 起安装路径不存在，勿再尝试）
> - 本地读取脚本：`<PROJECT_ROOT>\scripts\tdx_local_reader.py`（read_day 接口，属项目根非 skill 自带；**读 ETF 需自行 ÷1000 校准**）
> - 本地读取验证基准（8/07 收盘）：药明康德 603259 154.82 / 贝达药业 300558 70.21 / 诺唯赞 688105 23.22 / 中船特气 688146 316.00

## Market Pulse Modules (市场脉搏模块 M1/M2/M3, 2026-08-12 并入)

> 由 2023 年「周结果」Excel 半自动大盘分析表移植（详见 `周结果系统_设计原理解析_20260812.html`）。三个模块 **100% 本地数据、零接口费用**，自动分析文字随图生成。

### 更新频率（独立于 taobo 体系，按模块实际需求设置）
| 模块 | 内容 | 频率 | 触发时机 |
|------|------|------|----------|
| M1 市场广度 | 全A股 250日新高/新低 下雨图（窗口=近半年120交易日） | **每日** | 通达信盘后下载完成后（约 15:30-16:00） |
| M2 行业广度 | 56 行业新高家数/比例 | **每日** | 同上 |
| M3 行业RPS | 行业周涨幅排名 0-100 | **每周五** | 周五收盘后 |
| M4 期权情绪 | 沽购比 + 90/50/10分位带 | **每日**(数据源: 通达信MCP) | 收盘后, 合约每月滚动需重拉 |
| M5 基底计数 | 欧奈尔基底计数状态机 | **每周五** | 周线口径, 与选股配合 |

### 输出节奏（跟随交易看板 · 用户指令 2026-08-12 强制执行）

> M 模块**不独立输出**，按各自更新频率随统一交易看板（`统一交易看板_YYYYMMDD.html`）一起交付：**每日更新的模块 → 每个交易日看板都带；周频模块 → 仅周五看板带**。

| 看板输出日 | 附带模块 | 数据日期规则 |
|-----------|---------|-------------|
| 周二~周四（每交易日） | **M1 市场广度 + M2 行业广度 + M4 期权情绪** | 当日收盘后生成的数据（15:30 后） |
| 周五（周度看板） | **M1 + M2 + M4 + M3 行业RPS + M5 基底计数**（全量五模块） | M3/M5 用当日收盘数据正式更新 |
| 周一（及 M3/M5 未到周五的情况） | M1 + M2 + M4；M3/M5 沿用上周五数据并**标注「数据日期：上周五」** | 周频模块不重复跑 |

执行要点：
- 每次生成看板时，检查 `deliverables/taobo-daily/market_pulse/` 下当日 `breadth_YYYYMMDD.json` / `industry_YYYYMMDD.json` / `option_sentiment_panel_YYYYMMDD.html` / `market_pulse_panels_YYYYMMDD.html` 是否存在；缺失则先跑生成流水线再嵌入
- 嵌入位置：持仓面板之后、板块进场计划之前；以 `<div class="panel">` 包裹，M 模块分析文字随图（引用具体数值）
- 若当日数据未生成（如盘中建板），标注「M 模块数据截至最近收盘日」

### 数据源（全部本地, 免费）
- 个股日K: `vipdoc/{sh,sz,bj}/lday/*.day`（通达信盘后下载, 覆盖全A 5640 只）
- 全A代码清单 + 行业归属: `T0002/hq_cache/tdxhy.cfg`（第一列 0=深/1=沪/2=北, 取前5位T代码=二级行业）
- 行业名称: `T0002/hq_cache/tdxzs.cfg`（类型2 且 T代码长度=5, 排除 TDX 前缀）
- 上证指数: `vipdoc/sh/lday/sh000001.day`（注意: 000001 在 tdx_local_reader 的 _market_dir 会路由到 sz 目录=平安银行, 指数必须显式读 sh000001.day）

### 运行流水线（收盘后, 顺序执行）
```bash
cd ~/.workbuddy/skills/trading-dashboard/scripts
python market_breadth.py --days 120 --out "<PROJECT_ROOT>/deliverables/taobo-daily/market_pulse/breadth_YYYYMMDD.json"
python industry_analysis.py --out "<PROJECT_ROOT>/deliverables/taobo-daily/market_pulse/industry_YYYYMMDD.json"
python render_market_pulse.py --date YYYYMMDD --out-dir "<PROJECT_ROOT>/deliverables/taobo-daily/market_pulse"
```
- 窗口: **M1 默认 120 个交易日（半年, 2026-08-12 用户指令 60→120）**; 脚本已同步（market_breadth.py 默认 days=120, max_bars=450 支持 120+250 回看）
- 产出: `market_pulse_panels_YYYYMMDD.html`（两个自包含面板: 广度下雨图 + 行业温度）
- 看板集成: 将产出 HTML 嵌入统一看板正文（放在持仓面板之后、板块进场计划之前），或直接以 `{{MARKET_PULSE_PANELS}}` 占位符引用

### 图表下方自动分析（用户指令 2026-08-12: 每图必配）
- **广度面板分析规则**（render_market_pulse.py `analyze_breadth`）: 当日新高/新低/差值 → 差值5日斜率 → 新高占比 vs MA20（>1.3x 转强 / <0.7x 走弱）→ 新低压力阈值（≥20只警示）→ **上证指数 vs MA50 中期信号**（联动 taobo #8 门控: ON=允许新仓 / OFF=不建新仓）→ 综合裁决
- **行业面板分析规则**（`analyze_industry`）: 周度强势 TOP3 → 新高占比≥1% 的共振行业 → 弱势行业（RPS<10）→ **与持仓/观察池关联提示**（watch 映射表, 如 半导体→示例科技股 000999、医药→创新药ETF 513999）
- 分析文字必须引用具体数值（当日值 + 对比基准），禁止泛泛而谈

### 图形悬停提示（2026-08-12 用户指令：所有生成图形鼠标悬停显示具体数据）
- **方案（v2, 2026-08-12 17:57 用户反馈原生 title 不可靠后改）**：**自定义 JS tooltip**——数据元素加 `data-tip` 属性，面板内注入幂等脚本（`window.__mktTip` 防重复，只创建一个 `#mkt-tip` 固定定位提示框，跟随鼠标），浏览器环境均可用
- **SVG 图（M1 下雨图 / M4 折线图）**：M1 每根柱 `data-tip="日期 新高X / 新低Y / 差值±Z"` + 差值点透明 circle(r=5)；M4 每个折线点透明 circle(r=5) `data-tip="日期 沽购比X（沽a / 购b）ETF c"` + 分位线 `data-tip="90分位/中位/10分位 数值"`
- **HTML 条形图（M2/M3 行业）**：`.rank-bar` 加 `data-tip`（RPS/周涨幅/新高占比/新高-新低）
- 禁止再用浏览器原生 `<title>`（部分渲染环境不显示）；新增图形必须遵守 data-tip + 幂等 JS 模式
- **完整规范（含 JS 模板/格式表/接入步骤/验证清单/陷阱）见 `references/hover-tooltip.md`——新增或修改任何图形时必须照此执行**

### 已知口径注意
- "新高" = 最高价创 250 日新高（非历史新高），与 taobo RPS250 窗口口径一致
- 广度样本 = tdxhy.cfg 全部 A 股（5640 只, 缺失约 391 只因未下载日线, 覆盖率 ~93%）
- 行业粒度 = 通达信二级行业（56 个, 粒度≈申万一级）; 行业周涨幅 = 成分股等权平均（非指数涨幅）
- **M4 期权(2026-08-12 首期落地)**: 数据源=通达信MCP `tdx_kline`(期权合约 code=8位数字如 10011446, **必须带 target=1**, setcode=8, period=4) 的 **VolInStock 字段(未平仓量)**; 当前固化 300ETF(510300)12月合约平值±2档(4.6-4.9)8个合约 → `market_pulse/option_oi_510300_2612.json`; 计算脚本 `option_sentiment.py` → 沽购比+90/50/10分位带+ETF价格对照+自动分析。**⚠️ 口径(2026-08-12 用户最终拍板): M4 整体维持近 60 日（分位带 + 时间轴）**; 合约每月滚动, 需在每月20日前后重拉当月+季月合约更新固化数据。8/12: PCR=0.70, 60日分位带 90%=1.395/中位1.095/10%=0.65 中位下方偏多。**图表布局(2026-08-12 用户反馈): ETF 价格标签放右上角(text-anchor=end, x=W-pad_r, y=pad_t-3), 避免与日期刻度重叠**
- **M5 基底计数(2026-08-12 落地+网格验证)**: 状态机实现 基底.txt 五规则——周K合成(日K→ISO周), 突破新高且距上次突破涨幅≥20%=新基底+1; 突破后<20%再创新高=底上加底不计; 从高点回撤≥20%=趋势中断归零; 脚本 `base_count.py` → `market_pulse/base_count_YYYYMMDD.json`(每标的 base_count/突破记录)。**⚠️ 组合层面验证结论(2026-08-12 60组合交叉网格): 基底过滤(剔除4+基底信号) 11/30 正、19/30 负, 实盘骨架 8-6-4·G2·R72 +1025.9%→+740.2%(-285.7pp) → 不作为硬过滤实装**。根因: 4+基底信号 68 条中 81% 集中 2025 牛市, 事件研究(静态60日)与组合层面(动态净值+R7-2腾位)结论相反。**保留为候选排序次级信息(同分基底少排前), 不改 #6 主排序键**。报告: `deliverables/taobo-daily/base-filter-grid-compare-2016-2025.html`

## Reference Implementation（生成器范本 · 2026-08-21 落地）

> 统一看板渲染器 = `scripts/gen_dashboard.py`（通用，数据全 JSON 输入 + 模板 `data/dashboard_template.html`）；**排版基准 = 8/20 看板**（kpi/flow/footer 布局）。禁止再写 `gen_dashboard_YYYYMMDD.py` 这类一次性硬编码脚本（曾致 8/24 排版漂移成「板块/策略分区 + 全量汇总表」，已删）。

### 本地 .day 读取（关键 helper）
```python
import struct, os
VIP = r"D:\Sofeware\TongDaXin\vipdoc"
def read_day(code, scale):  # scale: A股/指数=100, ETF=1000
    mkt = "sh" if code[0] in ("6","5","9") else "sz"   # ⚠️ 5/9 前缀为沪市 ETF，必须走 sh/lday（曾误路由 sz 导致文件缺失 → TypeError）
    recs = open(os.path.join(VIP, mkt, "lday", f"{mkt}{code}.day"), "rb").read()
    rows = [struct.unpack("<IIIIIfII", recs[i:i+32]) for i in range(0, len(recs), 32)]
    closes = [r[6]/scale for r in rows]
    return closes[-1], (closes[-1]/closes[-2]-1)*100
```
- 上证指数必须显式读 `sh000001.day`（000001 默认路由到 sz=平安银行）。
- 港股（09999/09997/09998）本地无数据，现价 **WebSearch 兜底**（`"股票名 代码 年月日 收盘价"`）。

### 周五全量五模块流水线（M1-M5）
生成看板前先跑（顺序）：
1. `market_breadth.py --days 120 --out .../breadth_YYYYMMDD.json`
2. `industry_analysis.py --out .../industry_YYYYMMDD.json`
3. `render_market_pulse.py --date YYYYMMDD --out-dir .../market_pulse` → `market_pulse_panels_YYYYMMDD.html`（M1+M2）
4. `option_sentiment.py --data option_oi_510300_2612.json --etf 510300` → M4 面板
5. `base_count.py` → `base_count_YYYYMMDD.json` → M5 面板（仅周五）
嵌入位置：持仓面板之后、板块进场计划之前，以 `<div class="panel">` 包裹。M4 期权 OI 数据日期为合约固化日（如 20260820）属正常，标注即可，不阻断。

### 看板内容映射（screening 报告 → 看板）
| screening 报告区块 | 看板目标区块 |
|-------------------|------------|
| 大盘环境判断（3 指数 vs MA50 / 中期信号 OFF） | Header 市场状态 + 决策流「不建新仓」 |
| 重点观察池 27 只（A/B/C 通道） | Top Watchlist Grid（按通道标色 + 回踩 10/20/50/120 日线目标） |
| 板块分布统计 | 板块进场计划（分组：5G / 黄金 / 苹果 / 芯片…） |
| 风险提示（不追高 / 单票≤20% / 半仓下） | Do-Not-Do List + 仓位分配 |
| （无，由用户持仓表提供） | Current Holdings 8 只完整交易计划 |

## Scripted Pipeline（脚本化流水线 · 2026-08-21 落地 · token 优化核心）

> **每日看板生成一律走脚本链，禁止手工逐块编辑看板 HTML**（曾消耗 ~80KB/次）。LLM 只做 4 件事：① 跑脚本链 ② 港股 3 行数字 WebSearch 回填 ③ 期权 8 个 VolInStock 数字回填 ④ 写判断文字（--notes/--flow）。

### 每日标准命令链（scripts/ 目录，按序）
```bash
# 1. 选股链（deliverables/taobo-daily/）
python scan_c4.py --date 2026-08-21          # C4 扫描 → signals_2026-08-21.csv + c4_today_20260821.json
python fundamental_filter.py --signals signals_2026-08-21.csv --preset quality_floor \
      --out signals_filtered_2026-08-21_quality_floor.csv --stats stats_2026-08-21_quality_floor.json
python generate_daily_report.py --date 2026-08-21   # 报告（漏斗数字/动量对比已动态化，无需手工修正）

# 2. 状态与数据（trading-dashboard/scripts/）
python market_state.py --date 20260821                       # 门控 ON/OFF + off_days + C4%（自动解析报告）
python position_status.py --date 20260821 \
      --hk "09999:37.54,09997:20.94,09998:9.73" --hk-chg "09999:+1.19,09997:-1.60,09998:+0.10"  # 港股需 WebSearch 回填
python watchlist_pullback.py --date 20260821                 # 观察池解析 + 回踩目标（顺延规则自动处理已破均线）

# 3. M 模块（周五全量五模块）
python market_breadth.py --days 120 --out .../breadth_YYYYMMDD.json
python industry_analysis.py --out .../industry_YYYYMMDD.json
python render_market_pulse.py --date YYYYMMDD --out-dir .../market_pulse
# M4: 先 MCP 拉 8 合约 OI（10011445-48 购 / 10011454-57 沽，wantNum=1，取 VolInStock），再:
python append_oi.py --date 20260821 C4600=3298 C4700=5405 C4800=7424 C4900=9517 P4600=4295 P4700=5165 P4800=4685 P4900=4558
python base_count.py                                            # 周五 M5

# 4. 生成看板（LLM 注入判断文字）
python gen_dashboard.py --date 20260821 \
      --notes "!!y <strong>⚠️ 大盘…</strong>…|!!g <strong>✅ …</strong>…|!!r <strong>⚠️ …</strong>…" \
      --flow "09:25|竞价|…" --dont "标题|原因" --core "一句话"
# notes 前缀: !!y=黄 !!g=绿 !!r=红 alert；段落以 | 分隔；缺省用模板默认
```

### 脚本清单与输入输出（全部 `scripts/`）
| 脚本 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `market_state.py` | --date | `market_pulse/market_state_YYYYMMDD.json` | 门控（上证+深证 MA50）、off_days、C4% |
| `position_status.py` | --date --hk --hk-chg | `position_status_YYYYMMDD.json` | 持仓价/盈亏/整体账/极端线/-25%复盘线 |
| `watchlist_pullback.py` | --date | `watchlist_YYYYMMDD.json` | 观察池解析（报告）+ MA10/20/50/120 + 回踩目标（RPS120 初选、跌破顺延） |
| `gen_dashboard.py` | --date + 上述 json + M 面板 | `统一交易看板_YYYYMMDD.html` | 面板式布局，模板 `data/dashboard_template.html` |
| `append_oi.py` | --date 合约=OI ×8 | 追加 option_oi json + 重跑 M4 | MCP 拉取仍需人工（OI 无本地源） |
| `data/holdings_config.json` | — | — | 8 只持仓 canonical 单一真源（含极端线/已清仓） |
| `data/dashboard_template.html` | — | — | head/CSS/tooltip JS 固定模板（{{TITLE}}/{{BODY}}/{{FOOTER}}） |
| `rules_config.py` | — | — | adaptive 参数/R1b/R7-2/R6/路径常量 |

### LLM 职责边界（强制）
- **不可脚本化（必须 LLM）**：复盘分析文字（notes）、当日决策流程调整（flow）、不碰清单调整（dont）、核心思路（core）；MCP 期权 OI 拉取；港股 WebSearch。
- **禁止**：手工读旧看板逐块 replace；手工修正报告残留数字（根因已修）；手工计算门控/盈亏/极端线。

### 排版锁定铁律（2026-08-24 定稿 · 用户指令）
- **排版只允许改两处**：`data/dashboard_template.html`（CSS/外壳）与 `gen_dashboard.py`（面板结构/字段渲染）。看板 HTML 文件本身**禁止手工编辑**。
- **禁止临时硬编码渲染脚本**：曾出现 `gen_dashboard_v3_YYYYMMDD.py` 导致 8/24 排版漂移成「板块/策略分区 + 全量汇总表」（已删）。每日看板一律 `python gen_dashboard.py --date ... --notes/--flow/--dont/--core`。
- **基准排版 = 8/20 看板**（kpi/flow/footer 布局 + 重点观察池大表 + 持仓完整交易计划矩阵）；8/21 的 hold-block 布局为历史跑偏产物，已废弃。凡与 8/20 不一致处即视为排版 bug，须在模板/脚本层修，不得手工 patch 看板。

## Determining Which Stocks to Include

**跟踪标的只取陶博士选股（用户指令 2026-08-07 起强制执行）。** 旧的板块跟随（有色/稀土/机器人/AI应用/半导体等）全部停止，不再纳入看板。

标的数据来源（优先级）：

1. **`taobo-O'Neil` skill 每日筛选产出**（`deliverables/taobo-daily/daily-screening-YYYY-MM-DD.md`）——**以报告的「重点观察池（规则达标制）」为看板候选清单的唯一权威来源（2026-08-21 用户指令：以该看板为模板）**：
   - 取报告中「重点观察池」全部达标标的（**不设数量上限**，2026-08-21 为 27 只）
   - 通道分级：**A 质量顶级**（加分≥10）/ **B 质量+三线红**（加分≥9 且 C6 三线红 RPS50/120/250 全≥90）/ **C 质量+板块共振**（加分≥8 且 双RPS 板块 RPS20≥90）
   - 每只候选须引用其在报告中的「当前价/回踩目标/所处通道/板块」，并在看板标注其报告内原始信号（如「双RPS共振 ✅」「8/10候选 ✅」），禁止只放名称+价格
   - 报告内「大盘环境判断」（3 指数 vs MA50 / 中期信号 ON·OFF）直接驱动看板的「市场状态 / OFF 不建新仓」结论
   - 报告内「板块分布统计」驱动看板的「板块进场计划」分组（如 5G概念13 / 黄金概念10 / 苹果概念6 / 工业母机6 / 芯片5）
2. **用户当前实际持仓** — **必须全数保留在看板，且每只持仓必须含完整交易计划**（见下方「持仓清单 canonical 8 只」）
3. **用户明确要求跟踪的标的**

**持仓清单（canonical 4 只 · 2026-08-24 清仓后基准，须全数出现在看板；单一真源=`scripts/data/holdings_config.json`）**：

| 标的 | 代码 | 数量 | 成本 | 分组策略 |
|------|------|------|------|---------|
| 示例港股甲 | 09999 | 200 | 34.717 | 港股死拿（事件/基本面止损，-25%复盘线=26.04） |
| 示例港股乙 | 09998 | 600 | 10.299 | 港股死拿（事件/基本面止损，-25%复盘线=7.72） |
| 示例黄金ETF | 518999 | 3000 | 8.951 | 黄金·战略持有·逻辑止损（不做 Al Brooks 止盈） |
| 示例科技股 | 000999 | 300 | 60.867 | 已决持有·守极端线（8/20拍板，守37极端线，豁免 adaptive） |

> 已清仓（不进入盯盘，仅留已实现收益）：513999(8/12 （示例盈亏）)；002999 示例整车股 / 09997 示例智驾股 / 159999 示例卫星ETF / 563999 示例卫星ETF（8/24 清仓 4 只，合计 （示例盈亏））。
> ⚠️ 港股（09999/09998）本地无数据，现价须 **WebSearch 兜底**（格式 `"股票名 代码 年月日 收盘价"`）；ETF 本地 .day **÷1000** 校准；A股/指数 ÷100。
> ⚠️ **黄金 ETF 518999** 单票占比若超 R1 20% 上限属战略例外，看板须显式标注「战略例外·超 R1」。

⚠️ **禁止**：不再自行添加旧板块跟踪标的（示例历史标的A/示例历史标的B/示例历史标的C/示例历史标的D/示例历史标的E/示例历史标的F/示例历史标的G/示例历史标的H/示例历史标的I/示例历史标的J/示例有色股B/示例有色股等历史跟踪标的，除非重新通过陶博士选股或用户明确要求）。

**仓位规则一律引用 `taobo-O'Neil` skill**（选股+买点 → 本看板呈现 → taobo-O'Neil 管理仓位），不在本 skill 中另行规定。

Before generating the dashboard, scan these sources to identify:
- What stocks does the user currently hold? (持仓)
- Which taobo candidates have triggered/are near buy points? (等回踩/观察)
- What stocks has the user explicitly ruled out? (不碰)

The watchlist grid adapts to any count (4-col → 2-col → 1-col).

> ⚠️ **已清仓标的不进入盯盘清单（2026-08-17 用户指令）**：任何已清仓的标的（如 513999）不得再以"已清仓"卡片形式出现在 Top Watchlist Grid 盯盘清单中——清仓记录保留在持仓总览/历史记录区块（如"已实现收益"汇总、清仓记录表）即可，盯盘清单只放「当前持仓 + 候选/观察/不碰」。复盘文字中可提及历史清仓收益作为参考，但不占盯盘卡片位。

## Dashboard Structure (Mandatory Panels, in order)

The HTML MUST contain these panels in this exact order:

1. **Header** — Date, data source, market quick stats (volume, adv/dec, limit-up/down)
2. **Top Watchlist Grid** — One card per tracked stock with code, price, change, one-line signal. Color-coded by priority (红=持仓/首选, 黄=等回踩/次选, 蓝=观察, 灰=不碰)
3. **Current Holdings（持仓交易计划·MANDATORY）** — **每一只持仓股都必须包含完整交易计划，禁止只放价格快照**。每只持仓的区块必须包含：
   - **持仓基本信息**：数量、成本均价、现价、浮盈/浮亏（金额+百分比）、当日涨跌
   - **完整交易计划矩阵**（Al Brooks 移动止盈 + taobo-O'Neil 规则）：
     - 🔒 **移动止盈锚①（BE 保护）**：浮盈≥3% 后止损上移至成本价
     - 🔒 **移动止盈锚②（swing low）**：当前锚定的最近更高低点，触发描述"收盘跌破 X 则清仓"
     - ⬆ **加仓条件**：什么价位/什么量能触发加仓，加仓后锚点如何上移
     - ⬇ **减仓条件**：何种情况减半（如趋势结构破坏、区间市上沿）
     - 🛑 **硬止损（结构位）**：极端情况下的结构止损价
     - 📌 **仓位规则**：当前占用比例 vs O'Neil R1（单票≤20%）、R3/R6（浮盈>10% 移动止盈、≥10% 止损抬成本）
   - **当日操作指令**：明确的"做/不做"（如"收盘跌破9.195清仓，否则持有不动"）
4. **Market Pulse（市场脉搏·MANDATORY when data available）** — `{{MARKET_PULSE_PANELS}}` 占位符嵌入 `render_market_pulse.py` 产出的两个面板：
   - 🌧️ 市场广度·下雨图（250日新高/新低家数 + 差值 + 新高占比MA20 + 上证指数 vs MA50）+ 自动分析文字
   - 🏭 行业温度（行业RPS TOP10 条形图 + 行业新高比例 + 强势/弱势/共振行业）+ 自动分析文字
   - 数据缺失时注明"等待通达信盘后下载"而非留空
5. **Sector/Strategy Sections** — One panel per active strategy direction. Group stocks that share a common thesis. Each panel has: a qualitative assessment box, an entry plan table (entry zone, stop, target, position size, conditions)
6. **All-Stock Summary Table** — Every tracked stock in one table: name+code, close, direction, entry, stop, target, position, status badge
7. **Decision Flow** — Timeline grid from market open preparation through close. Only include time slots relevant to tomorrow's plan. Example structure: 09:00前 → 09:25竞价 → 09:30-10:00 → 10:00-11:00 → 全天 → 14:30尾盘
8. **Observation Indicators** — Table of key indicators to monitor throughout the day with: what to watch, data source, judgment criteria, corresponding action
9. **Position Allocation** — Total allocation summary showing per-stock weight and total cap. The specific limits come from the analysis, not from this skill
10. **Do-Not-Do List** — Numbered list of prohibited actions with specific reasons tied to current market conditions
11. **Core Message** — One-line strategy summary in centered panel at the bottom

## Design System

The HTML template is at `assets/template.html`. Key design rules:

- **Theme**: Dark (#1a1d23 background, #22252e panels, #d0d4dc text)
- **Color convention**: Chinese market — 涨红跌绿 (up=#ec4e4e red, down=#3ec97e green)
- **Price tags**: 4 variants — `.price-trigger` (red/breakout), `.price-support` (green/support), `.price-neutral` (yellow/zone), `.price-target` (blue/target)
- **Alert boxes**: 4 variants — `.alert-r` (danger/red), `.alert-g` (safe/green), `.alert-y` (warning/yellow), `.alert-b` (info/blue)
- **Signal tags**: 4 variants — `.sig-green`, `.sig-yellow`, `.sig-red`, `.sig-blue`
- **Typography**: "Microsoft YaHei", "PingFang SC", monospace for prices
- **Responsive**: 4-col grid → 2-col at 900px → 1-col at 500px
- **Stock cards**: 4 priority levels with colored left borders (`priority-1`=red, `priority-2`=yellow, `priority-3`=blue, `priority-4`=gray)

## CRITICAL: Stock Naming Convention

**Every single occurrence of a stock name in the HTML MUST include its trading code.**

```
✅ 示例有色股 600999     ❌ 示例有色股
✅ 示例历史标的D 002998     ❌ 示例历史标的D
```

This applies everywhere: watchlist cards, table cells (`<td>`), section headers (`<h3>`), alert boxes, flow items, KPI labels, summary tables — zero exceptions.

## Key Level Calculation Rules

These are analytical guidelines from the `wb-finance-skill` methodology, used when generating price levels for each stock:

### Support Level
- Recent swing low (from K-line data)
- Psychological round numbers nearby
- Key moving averages (MA20/MA60) if price is above them
- Take the HIGHER of: technical support vs psychological support

### Resistance Level
- Recent swing high
- Prior congestion zone
- Gap fill targets

### Stop-Loss
- Below a clear structural support level (not arbitrary)
- Distance from entry depends on stock volatility and market regime
- For reference, typical Chinese A-share ranges: 3-5% below support for volatile stocks (创业板/科创板), 2-4% for stable stocks (沪市主板)
- Actual stop distance is determined by the analysis, not a fixed formula

### Take-Profit — Al Brooks 移动止盈法（MANDATORY，替代固定目标价）

**默认止盈方式为 Al Brooks 价格行为移动止盈法。禁止使用固定 T1/T2 目标价作为离场依据。**

> ⚠️ **例外（2026-08-14 用户拍板）**：**黄金标的（如金ETF 518999）不做 Al Brooks 移动止盈**——黄金作为避险/长期配置类资产，归入「战略持有·逻辑止损」管理（类同港股死拿/示例整车股长持）：以金价长期趋势与宏观逻辑（实际利率、美元、央行购金等）为离场依据，不因短期 swing low 破位离场。看板中黄金 ETF 不再标注移动止盈锚，改为标注"逻辑止损（金价趋势/宏观）"。

核心规则（详见 `references/al-brooks-trailing-stop.md`）：

1. **不设固定目标价**：取消"止盈T1/T2"预设。盈利是否离场完全由价格结构决定，而非预定价位。
2. **盈亏平衡保护（BE）**：进场后一旦出现盈利（通常 +2%~+3% 或达到 1R），立即将止损上移至成本价（BE），本金零风险后让利润奔跑。
3. **移动止损锚点**：
   - 上升趋势中：止损设在**最近一个更高低点（swing low）下方**（低点下方 1~2% 或 1 tick）
   - 每出现新的 swing low，止损同步上移（只上不下）
   - 强势趋势可辅助用 **20 EMA / 5日线** 作为跟随基准，跌破且收盘确认才离场
4. **离场信号（满足其一）**：
   - 收盘跌破最近 swing low（盘中假破不卖）
   - 趋势结构破坏：不再创新高 + 跌破前低
   - 出现反转信号（如急跌大阴线、趋势通道反转）
5. **分批离场（可选）**：可 1/3 仓位在 BE 附近保护，其余跟随移动止损；但 Al Brooks 更推崇"趋势结束才全出"
6. **区间市例外**：若进入横盘交易区间（不再创新高/新低），在区间上沿减仓，不使用趋势移动止盈

**看板呈现**：表格中"止盈"列改为展示"移动止盈锚"（当前 swing low / 移动止损价）而非固定目标价。触发条件描述为"收盘跌破 X 则离场"而非"涨到 X 减仓"。

## Position Sizing

**仓位规则一律引用 `taobo-O'Neil` skill（用户指令 2026-08-07 起强制执行），本 skill 不另行规定。**

核心仓位规则（详见 taobo-O'Neil skill · 2026-08-14 v3.4 定稿）：
- **R1**：单票 ≤ 总资金 20%
- **R1b**：持仓只数环境自适应（趋势≤8 / 震荡≤6 / 弱势≤4，先采用 8-6-4）
- **R2**：动态净值×10% 三次建仓（10%→6%→4%）；禁固定金额
- **R3/R4 离场引擎 = adaptive 组合A（2026-08-14 拍板切换，仅限 A 股个股）**：①-8% 盘中止损（low 触及即触发）②环境自适应峰值回撤——trend 10% 减半/15% 清仓、range 8%/12%、weak 6% 减半/10% 清仓 + AlBrooks 锚（G2 门控下 weak 不触发）③250 日到期 ④辅层保护（浮盈曾≥15% 回撤≥8% 减半）；peak=收盘价最高；**dr 退居备选**
- **R6**：浮盈 ≥8% 止损线抬升至成本线（BE 保护，只上移）
- **止盈分层（2026-08-14 终稿）**：A股个股 → adaptive 组合A（仅 A 股）；非黄金 ETF → Al Brooks 移动止盈锚（8/11 拍板：ETF 不参与引擎清仓）；**黄金标的（如 518999）→ 战略持有·逻辑止损，不做 Al Brooks 止盈（8/14 拍板）**

The dashboard's Position Allocation panel reflects the *conclusion* of the taobo-O'Neil analysis, and the panel itself is the display of those rules.

## State Classification

Each stock is classified into one of 4 states based on analysis (not pre-assigned):

| State | Badge CSS | Meaning |
|-------|-----------|---------|
| 持仓 | `badge-hold` (green) | Currently held, manage existing position |
| 等回踩 | `badge-buy` (red) | Entry plan ready, waiting for pullback to zone |
| 观察 | `badge-watch` (gray) | Anchor stock or future candidate, no current action |
| 不碰 | `badge-dont` (dark red) | Explicitly ruled out: overheated, broken thesis, or too risky |

## Update vs Create

- **Same date update**: Edit the existing `统一交易看板_YYYYMMDD.html` in place
- **New date**: Create new `统一交易看板_YYYYMMDD.html`
- **User says "更新" without date change**: Edit existing file
- **User says "明天的" or new date**: Create new file

## After Generating

1. Call `present_files` to show the HTML to the user
2. Write a brief summary of key changes in the text reply
3. Update the daily work log at `.workbuddy/memory/YYYY-MM-DD.md`

## Change Management（变更治理 · 2026-08-25 建立）

- **每次实质改动（SKILL.md / references / scripts）必须在 `CHANGELOG.md` 登记**：日期 / 类型 / 内容 / 建立理由。
- **规则/口径改动的同步链路**：先引用 taobo-O'Neil 的《策略档案_市场环境-选股-仓位管理.md》→ 同步更新档案（taobo-O'Neil 侧）→ 同步本 skill 呈现口径（`market_state` 门控 / `Position Sizing` 仓位 / M1-M5 市场脉搏）→ 在本文件登记。
- 本 skill 不另立规则，任何规则/口径一律以 taobo-O'Neil 档案 + SKILL.md 为唯一来源。
