# Daily Update Workflow

## When to Update

The dashboard should be updated daily after market close (after ~15:30 CST, typically around 18:00-20:00 when all data is settled).

## Trigger Phrases

User will say things like:
- "明天的交易计划" / "更新看板" / "生成看板"
- "今天的盘面复盘"
- "帮我更新交易看板数据"

## Standard Update Workflow

### Phase 1: Determine the Stock List

**跟踪标的只取陶博士选股（用户指令 2026-08-07 起强制），旧板块跟随全部停止。**

1. **读取当日陶博士筛选报告**：`deliverables/taobo-daily/daily-screening-YYYY-MM-DD.md`
   - **取「重点观察池」（三通道达标制 · 2026-08-10 起）全量标的**——通道A 加分≥10 / 通道B 加分≥9 且 C6三线红 / 通道C 加分≥8 且 双RPS板块共振，**达标即入、不限数量**（取代旧「重点关注标的 TOP5」固定概念）
   - 另取「本周累计观察池」+ 满足 C12/C13 买点或综合得分 ≥7 的标的
2. **用户当前持仓** — 必须保留（如示例黄金ETF 518999）
3. **用户明确要求跟踪的标的**
4. ⚠️ 不再纳入：旧板块跟踪标的（有色/稀土/机器人/AI/半导体等历史标的），除非重新通过陶博士选股或用户明确要求
5. 仓位规则引用 taobo-O'Neil skill（不在看板 skill 中另行规定）

### Phase 2: Data Collection

Query each stock individually (batch queries may return partial results):

1. **Market overview** — 1 query
   ```bash
   cd "<neodata-dir>" && python scripts/query.py --query "上证指数收盘、涨跌幅、两市成交额、涨停跌停、涨跌家数" --data-type api
   ```

2. **Each tracked stock** — 1 query each (use `--data-type api`)
   ```bash
   cd "<neodata-dir>" && python scripts/query.py --query "<name> <code> 最新收盘价、涨跌幅、成交额、换手率、量比、PE、总市值" --data-type api
   ```

3. **Holdings with fund flow** — additional query for held stocks
   ```bash
   cd "<neodata-dir>" && python scripts/query.py --query "<name> <code> 主力资金净流入" --data-type api
   ```

4. **K-line for support/resistance** — for stocks where price levels have shifted
   ```bash
   cd "<neodata-dir>" && python scripts/query.py --query "<name> <code> 最近20个交易日K线数据 最高价最低价收盘价" --data-type api
   ```

### Phase 3: Analysis

For each tracked stock, determine:

1. **State classification** (持仓 / 等回踩 / 观察 / 不碰) based on current analysis
2. **Key price levels** — support, resistance, entry zone, stop-loss, trailing-stop anchor (Al Brooks)
3. **Entry conditions** — specific triggers that must be met before taking action
   - 若为「等回踩」标的：**必须写明「建议观察回踩目标：X 日线」**（X ∈ {10 / 20 / 50 / 120}，依据个股所处阶段与第二阶段确认度选取；对应 taobo-O'Neil R2 建仓前提 / 选股 skill B4 回踩均线买点）。禁止只写"等回踩"而不指定具体均线。
4. **Position sizing** — 引用 taobo-O'Neil skill 规则（R1-R6、止盈引擎），不在看板中另行计算
5. **Grouping** — cluster stocks by shared thesis (陶博士主线板块) into strategy sections
6. **移动止盈锚** — 每只持仓/候选标注当前 swing low / 移动止损价（Al Brooks 法）

### Phase 4: HTML Generation

1. Start from `assets/template.html`
2. Replace all `{{PLACEHOLDER}}` tags with generated content:
   - `{{DATE_TITLE}}` → "YYYY.M.D 周X"
   - `{{DATA_DATE}}` → "M/D"
   - `{{MARKET_STATS}}` → `<span>` tags with market data
   - `{{WATCHLIST_CARDS}}` — one `.watch-card` per stock, priority class derived from state
   - `{{HOLDINGS_SECTION}}` — KPI row + operations table (only for held stocks)
   - `{{SECTOR_SECTIONS}}` — one panel per strategy direction
   - `{{SUMMARY_TABLE}}` — all stocks in one summary table
   - `{{DECISION_FLOW}}` — time-slot flow items for tomorrow's action plan
   - `{{OBSERVATION_INDICATORS}}` — table of key indicators to watch
   - `{{POSITION_ALLOCATION}}` — allocation table reflecting analysis conclusions
   - `{{DONT_DO_LIST}}` — prohibition list tied to current market conditions
   - `{{CORE_MESSAGE}}` — one-line strategy summary
   - `{{GENERATION_TIME}}` — current timestamp (YYYY-MM-DD HH:MM CST)

3. Save as `统一交易看板_YYYYMMDD.html` in the project directory

### Phase 5: Output

1. Call `present_files` with the generated HTML
2. Write a concise summary of key decisions and changes
3. Update the daily work log

## Naming Convention — CRITICAL

**Every stock name in the HTML MUST be followed by its trading code.**

```
✅ 示例有色股 600999
❌ 示例有色股
```

Applies to every occurrence: cards, tables, headers, alerts, flow items, KPI labels — no exceptions.

## Data Freshness Rules

1. Always query real-time data — never reuse old numbers without re-querying
2. If neodata returns wrong-year data (e.g., 2023 instead of 2026), re-query with `--data-type api` flag
3. If first query returns partial results, query remaining stocks individually
4. Market close data available after ~15:30 CST
5. Label all data with source and timestamp

## Update the Existing File

When updating an existing dashboard (same date), edit the file in place. When creating a new date's dashboard, create a new file with the date suffix.
