# Trading Dashboard · 统一 A 股交易看板 Skill

> 这是 **WorkBuddy**（AI 智能体工作台）的一个 *skill*（智能体技能），用于生成和维护一份**自包含的 HTML 交易看板**。
> 它不是独立程序，而是被 WorkBuddy 调用、按统一模板渲染看板的规则与方法。

## 这是什么

本 skill 把「当前跟踪标的（持仓 / 候选 / 观察锚点 / 禁止清单）」整合进**单一 HTML 页面**，统一呈现：

- 持仓状态与盈亏、进场条件、止盈 / 止损价位
- 市场脉搏模块（M1 市场广度、M2 行业广度、M3 行业 RPS、M4 期权情绪、M5 基底计数，100% 本地数据、零接口费）
- 仓位分配、决策流程、禁止操作清单

> **重要定位**：本 skill 是「展示框架」，不是「选股规则书」。选哪些标的、怎么定仓位，由你的实际持仓 + `taobo-O'Neil` skill 的分析口径决定；本 skill 只负责把结论漂亮地渲染成 HTML。

## 前置依赖

- **`taobo-O'Neil` skill**：本看板的规则 / 口径（门控、仓位、市场脉搏）唯一引用来源。建议同时安装 `taobo-O'Neil`。
- 本地 **通达信** `vipdoc` 数据（用于市场脉搏模块与行情读取）。

## 目录结构

```
trading-dashboard/
├── SKILL.md                     # 技能主文档（必读）
├── CHANGELOG.md                 # 版本变更记录
├── assets/template.html         # 看板 HTML 模板
├── references/                  # 数据源 / 更新流程 / 止盈规则等说明
└── scripts/                     # Python 渲染脚本
    ├── gen_dashboard.py         # 主生成脚本（读 holdings_config.json → 出 HTML）
    ├── market_breadth.py        # M1 市场广度
    ├── industry_analysis.py     # M2 行业广度 / M3 行业 RPS
    ├── option_sentiment.py      # M4 期权情绪
    ├── base_count.py            # M5 基底计数状态机
    └── data/
        └── holdings_config.json # ⚠️ 持仓配置（模板，需换成你自己的）
```

## 安装（WorkBuddy）

把整个 `trading-dashboard` 文件夹放入 WorkBuddy 的 skills 目录，**文件夹名即 skill 名**：

- 用户级：`~/.workbuddy/skills/trading-dashboard/`（推荐）
- 项目级：`<你的项目>/.workbuddy/skills/trading-dashboard/`

放入后，在对话里说「更新看板 / 生成交易看板 / 明天的交易计划」等，WorkBuddy 会自动调用本 skill。

## 配置你的持仓

仓库内的 `scripts/data/holdings_config.json` 是**占位模板**，打开后把示例数据替换为你的真实持仓（代码、名称、数量、成本等），再运行 `gen_dashboard.py` 即可生成看板。

> 本仓库发布版已做脱敏处理，`holdings_config.json` 不含有任何真实持仓，可直接公开。

## 占位符说明

部分脚本与文档中出现的路径占位符，使用时替换为你的本地实际路径即可：

- `<PROJECT_ROOT>`：你的项目根目录（原本指向本地通达信数据 / deliverables 工作区）
- `<TAOBO_SKILL_REFS>`：你本机 `taobo-O'Neil` skill 的 `references/` 目录绝对路径

这些占位符**不含任何个人路径信息**，纯为可移植性预留。

## 免责声明

本仓库仅提供看板**渲染框架与模板**，所有示例均为占位数据，不构成任何投资建议。
