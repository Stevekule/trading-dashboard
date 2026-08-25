# 图形悬停提示规范（Hover Tooltip）— trading-dashboard

> 建立时间：2026-08-12（用户指令：所有生成图形鼠标悬停显示具体数据）
> 版本：v2（2026-08-12 17:57 用户反馈原生 `<title>` 在部分渲染环境不显示，改自定义 JS tooltip；**v1 方案作废，禁止回退**）

## 1. 规则（MANDATORY）

**所有生成图形（SVG 图 / HTML 条形图 / 未来任何新图）的每个数据元素，鼠标悬停时必须能显示该元素的具体数值**（如某日柱=多少、某点=多少、某行业=多少），禁止无提示的纯视觉图形。

## 2. 实现方案：data-tip + 幂等 JS tooltip

### 2.1 元素侧：加 `data-tip` 属性（替代原生 `<title>`）

- SVG 元素（rect/circle/line 等）与 HTML 元素（div 等）均可直接加 `data-tip="..."` 属性，无需 JS 绑定
- 属性值内**禁止使用双引号**（属性本身用双引号包裹），内容中的引号用中文括号「（）」或省略
- 悬停命中区域：折线/散点类用**透明 circle（r≥5）**叠在每个数据点上（r=5 保证易点中；禁止 r<4）
- 柱状图每根柱直接加在柱元素上；同一数据点的多个元素（如红柱+绿柱）可重复携带同一 data-tip（无害）

### 2.2 面板侧：注入幂等 JS（每个面板 HTML 内自带一份）

```html
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
```

要点：
- **幂等**：`window.__mktTip` 标记保证多个面板/多次注入只创建一个 `#mkt-tip` 提示框（全局唯一，后注入的脚本直接 return）
- `mouseover` 委托到 document，对动态/内嵌内容天然有效
- `position:fixed` 不随滚动丢失；靠近右/下边缘时自动翻转到鼠标左侧/上方
- `pointer-events:none` 保证提示框本身不遮挡交互

### 2.3 data-tip 内容格式（现有图形标准，新图形参照此风格：日期/数值/单位齐全）

| 图形 | 元素 | data-tip 格式 |
|------|------|--------------|
| M1 下雨图 | 每根柱（红/绿） | `{MM-DD} 新高{n} / 新低{m} / 差值{±k}` |
| M1 下雨图 | 差值折线点（透明 circle r=5） | `{MM-DD} 差值{±k}` |
| M2/M3 行业条形 | 每个 `.rank-bar` | `{行业名} RPS {r} · 周涨幅 {±x}% · 新高占比 {y}% · 新高{a}/新低{b}` |
| M4 期权折线 | 每个折线点（透明 circle r=5） | `{MM-DD} 沽购比 {p}（沽 {a} / 购 {b}）ETF {c}` |
| M4 期权分位线 | 分位线 line | `90分位 {v}` / `中位 {v}` / `10分位 {v}` |

## 3. 接入步骤（新增/修改图形时）

1. 渲染脚本中给每个数据元素拼 `data-tip="{内容}"`（注意转义：内容不得含双引号）
2. 面板 HTML 组装处，在 `<style>` 之后、面板 div 之前插入 2.2 的幂等 JS 模板
3. 重跑渲染脚本 → 校验生成 HTML：`grep -c 'data-tip=' 面板.html` 数量符合预期、`grep -c '__mktTip'` ≥1
4. 嵌入统一看板（M 区块替换脚本保持 script 标签原样保留）

## 4. 验证清单

- [ ] 生成的 HTML 中所有图形数据元素均有 `data-tip`（柱/点/线/条形各覆盖）
- [ ] 面板内包含幂等 JS（`window.__mktTip` 恰好 1 次生效标记）
- [ ] 嵌入看板后预览：鼠标悬停任意图形元素出现跟随提示框且数值正确
- [ ] 无残留原生 `<title>`（head 页面标题除外）
- [ ] 提示框内容无引号冲突（data-tip 值内无 `"`）

## 5. 已知陷阱

- 原生 `<title>`/`title` 属性：WorkBuddy 内置预览等环境可能不显示 → **一律不用**
- SVG 内 `<title>` 子元素在某些解析器下会被吞 → 一律改用 `data-tip` 属性
- data-tip 值含双引号会破坏属性解析 → 内容用中文括号或去掉引号
- 透明 circle 太小（r<4）几乎点不中 → 统一 r=5
