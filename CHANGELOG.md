# trading-dashboard · 变更日志

> 自 2026-08-25 起建立独立 CHANGELOG 机制（此前变更内嵌 SKILL.md 日期标注，如「2026-08-12 用户指令」「2026-08-24 定稿」等）。**此后任何实质改动（SKILL.md / references / scripts）必须在本文件登记**：日期 / 类型 / 内容 / 理由。

## v1.0 (2026-08-25 · 建立 CHANGELOG 机制 + 引用策略档案)

- **背景**：用户「把市场环境辨别、选股、仓位管理整理为策略档案提交审核，作为 taobo-O'Neil 的总结产物长期更新，策略改动须同步；trading-dashboard 也引用该档案，保持口径一致；并建立与 taobo-O'Neil 相同的 CHANGELOG 机制」。
- **SKILL.md 变更**：
  ① frontmatter description 末尾加「规则/口径以 taobo-O'Neil 的《策略档案_市场环境-选股-仓位管理.md》为对外唯一口径，该档案变动须同步本 skill 的门控/仓位/市场脉搏呈现」；
  ② Prerequisite Skills 新增「规则/口径唯一对外档案」条目 + 同步义务（引擎/门控/因子/排序/阈值变动审批后，须同步 `market_state` / `Position Sizing` / M1-M5 呈现口径）；
  ③ 新增「Change Management」章节（本机制的落地规则）。
- **建立理由**：trading-dashboard 此前变更散落在 SKILL.md 各处日期标注，无统一追溯；且本 skill 定位为「看板呈现层，规则一律引用 taobo-O'Neil」，需明确「档案=唯一对外口径 + 同步义务」的治理闭环，防止呈现口径与规则脱节。
- **详细规则说明**：规则/口径改动 → 先引用 taobo-O'Neil 档案 → 同步更新档案（taobo-O'Neil 侧）→ 同步本 skill 呈现口径（market_state 门控 / Position Sizing 仓位 / M1-M5 市场脉搏）→ 在本文件登记。

## v1.1 (2026-08-25 · 修复「不碰清单」板块排版 bug)

- **现象**：`gen_dashboard.py` 生成的「🚫 绝不做的 N 件事」板块与 8/20 基准排版不一致——数据行渲染成嵌套 `<tr>`（`<tr><td>编号</td><tr><td>❌标题</td><td>原因</td></tr></tr>`），导致编号列悬空、与 3 列表头错位。
- **根因**：`dont_items` 列表每项存的是**带 `<tr>` 标签的 2 列表格行 HTML**，渲染时又用 `f'<tr><td>{i}</td>{x}</tr>'` 给编号单独包一层 `<tr>` 再与 `{x}` 拼接 → 双重 `<tr>` 嵌套。
- **修复（gen_dashboard.py，4 处）**：① `dont_items` 改存 `(标题, 原因)` 元组（两处 append，含 defaults 分支）；② 渲染行改为单层 `f'<tr><td>{i}</td><td>❌ {t}</td><td>{why}</td></tr>'`；③ 板块标题 `今日` → `{weekday_cn(D)}`（带星期几，与 8/20「周四绝不做的 8 件事」一致）。
- **建立理由**：排版锁定铁律「基准排版=8/20 看板」，凡与 8/20 不一致处即排版 bug，须在 `gen_dashboard.py` 层修，不得手工 patch 看板 HTML。
