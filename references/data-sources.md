# Data Sources 数据源固定矩阵（2026-08-13 验证定稿）

> **背景**：2026-08-13 通达信 MCP（tdx-connector）断连后，全量改用本地数据完成复盘与看板，以下数据源组合已验证可用。
> **原则**：本地优先 → MCP → 网络兜底。**不再使用 neodata-financial-search**（安装路径已变更，8/12 起不可用，勿再尝试）。

## 1. 通达信本地数据（主源 · 免费 · 已验证 ✅）

### 1.1 日K / 收盘价（A股 + ETF + 指数）
- 路径：`D:\Sofeware\TongDaXin\vipdoc\{sh,sz,bj}\lday\{市场}{代码}.day`
- 格式：32 字节/条，`struct.unpack("<8I")`：日期/开/高/低/收/成交额/成交量/保留
- **精度（8/13 实测坑，必须区分）**：
  - A股/指数：价格字段 **÷100**（2 位小数）
  - **ETF：÷1000**（净值 3 位小数，直接 ÷100 会得到 ×10 的错误值！如金ETF 9.466 存为 9466）
- 指数特殊：上证指数必须显式读 `sh000001.day`（000001 在通用路由会落到 sz=平安银行）；深证综指 `sz399106.day`；创业板指 `sz399006.day`
- 工具：`<PROJECT_ROOT>\scripts\tdx_local_reader.py`（`read_day(code)` 返回 list[dict]，**注意其统一 ÷100，读 ETF 需自行 ÷1000 校准**）
- 覆盖：全 A 约 5249 只有效日线（vipdoc 下载后 15:30-16:00 更新）
- **港股不在本地**（vipdoc 无 hk 目录）→ 见 §3

### 1.2 行业归属与名称（M2/M3）
- 个股行业：`D:\Sofeware\TongDaXin\T0002\hq_cache\tdxhy.cfg`（第一列 0=深/1=沪/2=北，取前 5 位 T 代码=二级行业）
- 行业名称：`T0002\hq_cache\tdxzs.cfg`（类型2 且 T 代码长度=5）
- 调用脚本：`market_breadth.py` / `industry_analysis.py`（trading-dashboard skill scripts，全部本地）

### 1.3 本地选股管线（taobo-O'Neil）
- RPS（EXTDATA 1-5/11-13）：通达信盘后扩展数据 → `rps_lookup.py`（taobo-O'Neil skill）
- 种子池：`deliverables/taobo-daily/screener_pool_full.csv`（546 只）
- 每日筛选：`scan_c4_today.py → fundamental_filter.py → generate_daily_report.py`（16:00 自动任务未触发时手动补跑，sed 改日期即可）

## 2. 通达信 MCP（tdx-connector · 断连中，恢复后启用）

| 工具 | 用途 | 备注 |
|------|------|------|
| `tdx_quotes` | 实时行情/盘口 | ETF 行情有 1 日滞后（8/12 实测），收盘价以本地 .day 为准 |
| `tdx_kline` | 日K/期权 OI | **期权合约拉取必带 `target=1` + `setcode=8`，code 用 8 位数字（如 10011446）；不带 target=1 返回空** |
| `tdx_option_t_quote` | 期权 T 型报价/合约代码 | underlyMarket=1, underlyCode=510300, month=2612 → 可查合约真实代码 |
| `tdx_lookup_stock` | 代码/名称检索 | 期权合约用 T 型报价确认代码，lookup 查不到 |

- **M4 期权 OI 唯一数据源**：期权未平仓量（VolInStock）只有 MCP 能拉；固化文件 `deliverables/taobo-daily/market_pulse/option_oi_510300_2612.json`（8 合约 × 76 天）；**MCP 断连期间 M4 无法更新，面板须标注"数据截至最近可拉日"**；12 月合约 4/23 上市（历史≤76天），每月 20 日前后需重拉滚动合约

## 3. 网络兜底（WebSearch）

- **港股收盘价**（本地无数据、MCP 断连时）：`WebSearch("股票名 代码 YYYY年M月D日 收盘价")`——8/13 实测可用，返回最新收盘/昨收/高低/涨跌幅（如 09999=36.60 / 09997=22.60 / 09998=9.90）
- 适用：港股三只（09999/09997/09998）等本地缺失标的

## 4. 已弃用

- ~~neodata-financial-search~~：`D:\Sofeware\WorkBuddy\...\builtin-skills\neodata-financial-search` 目录已不存在（8/12 起），勿再尝试，不再作为任何兜底

## 5. 取数优先级总表

| 数据需求 | 第一优先 | 第二优先 | 兜底 |
|---------|---------|---------|------|
| A股/ETF 收盘、K线 | 本地 vipdoc .day | tdx MCP（恢复后） | — |
| 指数（上证/深证/创业板） | 本地 .day（上证显式 sh000001） | tdx MCP | — |
| 行业归属/RPS | 本地 tdxhy.cfg / extdata | — | — |
| 港股收盘 | — | — | **WebSearch** |
| 期权 OI（M4） | **tdx MCP（唯一）** | — | 断连则标注滞后 |
| 实时行情/盘口 | tdx MCP | — | — |
| 选股/RPS/财务 | 本地管线（taobo-O'Neil） | — | — |

## 6. 数据新鲜度铁律（延续）

1. 收盘价以本地 .day 末根为准（通达信盘后下载后 15:30-16:00 更新），盘中用 tdx MCP
2. 所有数据标注来源 + 日期（YYYY-MM-DD HH:MM CST）
3. 报告必须附数据源新鲜度表（K线/RPS/财务/股本/板块快照日期，check_freshness.py）
4. MCP 断连时：能本地化的全部本地化，标注滞后项，不阻断流程
