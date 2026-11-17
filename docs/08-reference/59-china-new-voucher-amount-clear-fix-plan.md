# 新增凭证金额删除交互小增量修复方案

## 1. 文档目的

本文针对“新增凭证”页面中借方金额、贷方金额九格输入区的删除问题制定修复方案。

现象：用户在红框所示金额输入区已经录入金额后，按键盘 `Backspace` 或 `Delete` 不能稳定地将金额及其九格显示清空，导致用户无法按正常录入习惯更正金额。

本阶段仅沉淀方案，**不修改业务代码、不修改数据库、不执行会写入业务单据的测试**。

## 2. 目标、范围与约束

### 2.1 修复目标

在“新增凭证”每一条分录的借方、贷方金额区域中：

1. 光标位于金额输入区时，按 `Backspace` 可正常删除字符；删至空值后，金额九格显示同步清空。
2. 光标位于金额输入区时，按 `Delete` 可正常删除字符；删至空值后，金额九格显示同步清空。
3. 金额被清空后，借方合计、贷方合计、借贷平衡状态和合计大写金额立即重新计算。
4. 保留“一条分录只能填写借方或贷方之一”的既有会计规则；输入一方金额时，另一方金额及九格显示同步清空。
5. 不改变保存、提交、记账、生成 Journal Entry（会计凭证）和 GL Entry（总账分录）的现有逻辑。

### 2.2 不在本次范围

- 不改变凭证金额校验规则，例如借贷必须平衡、金额必须为非负数。
- 不将金额九格改造成新的控件或重做页面布局。
- 不修改 `Journal Entry`、`GL Entry`、`China Accounting Voucher` 的 DocType、字段、后端服务或数据库数据。
- 不修复与本问题无关的会计科目、现金流量、初始化或发票识别问题。

### 2.3 实施原则

- 小增量：只在“新增凭证”页面前端增加私有同步分支和测试脚本。
- 兼容优先：保留已有方法名、路由、RPC 方法签名和返回结构。
- 不覆盖老接口：不修改 `create_manual_voucher` 服务接口，不改调用方参数。
- 事件双保险：以浏览器原生 `input` 事件作为状态最终来源；只额外监听 `Backspace` / `Delete` 作为兼容与同步触发分支，不阻止浏览器默认删除行为。
- 可回滚：变更集中在单页 JS（及可选的少量 CSS）中，删除新增同步分支即可回到原行为。

## 3. 当前实现与问题定位

### 3.1 涉及页面

页面路由：

```text
China Finance 工作台
  -> 新增凭证（china-new-voucher）
```

页面文件：

```text
development/frappe-bench/apps/china_finance/china_finance/china_finance/page/
china_new_voucher/china_new_voucher.js
```

金额区由真实的透明文字输入框覆盖在“金额九格显示层”上：

```text
.cf-amount
  ├─ .cf-digit-cells       九格金额显示
  └─ input.cf-amount-input 实际接收键盘输入
```

### 3.2 当前数据与渲染逻辑

现有 `amount_editor(side)` 为借方或贷方生成金额输入框；`paint_amount(row, side)` 根据输入值重绘对应的九格；`update_totals()` 从每行输入框读取金额并刷新合计与借贷平衡提示。

当前行输入事件的核心逻辑等价于：

```javascript
input.oninput = () => {
    const other = row.querySelector(
        input.dataset.side === "debit" ? ".cf-credit-input" : ".cf-debit-input"
    );
    if (input.value) other.value = "";
    this.paint_amount(row, input.dataset.side);
    this.update_totals();
};
```

这里对“录入一方金额时清空另一方输入值”只处理了输入框值，没有同时重绘另一方九格。并且删除动作没有形成一个明确的、可复用的“输入值—九格—合计”同步路径。透明输入框与九格显示层叠加后，不同浏览器、输入法组合或焦点位置下，用户容易看到“键按了但显示没有清掉”的结果。

本次方案不假设问题来自后端：金额输入区没有向服务端逐字符保存，删除失败应先在页面事件和显示状态同步层解决。

## 4. 目标调用链路

### 4.1 修复前

```text
键盘输入 / Backspace / Delete
  -> input.cf-amount-input 的值变化
  -> input.oninput
  -> paint_amount(当前借方或贷方)
  -> update_totals()
  -> entries()
  -> 页面合计、借贷平衡、合计大写
```

存在的薄弱点：

```text
输入借方金额
  -> 清空贷方 input.value
  └─ 未统一重绘贷方九格、未集中处理“空值”状态
```

### 4.2 修复后

```text
键盘输入 / Backspace / Delete
  -> 原生浏览器完成输入或删除
  -> keydown（仅标记删除同步，不 preventDefault）
  -> input 事件
  -> sync_amount_row(row, side, { deletionRequested })
       ├─ 当前值为空：清空当前九格
       ├─ 当前值非空：清空相反方向 input 和九格
       ├─ 重绘当前方向九格
       └─ 重算合计、借贷平衡及合计大写
  -> entries()
  -> 页面显示更新

用户点击“保存并记账”
  -> 既有 save()
  -> 既有 create_manual_voucher(company, posting_date, entries, remarks)
  -> Journal Entry
  -> GL Entry
  -> China Accounting Voucher
```

金额删除只发生在保存前的页面内存状态；未点击保存时不会创建或修改任何业务单据。

## 5. 拟修改文件与代码

| 文件 | 变更类型 | 拟修改内容 | 是否改老接口 |
| --- | --- | --- | --- |
| `development/frappe-bench/apps/china_finance/china_finance/china_finance/page/china_new_voucher/china_new_voucher.js` | 修改 | 新增页面内部金额同步辅助方法；将现有金额 `oninput` 逻辑切换到该方法；新增非阻断式删除按键分支。 | 否 |
| `development/frappe-bench/apps/china_finance/china_finance/public/css/china_new_voucher.css` | 可选修改 | 仅在复测证明焦点不可见或点击区域异常时，增加 `.cf-amount:focus-within` 焦点提示或输入层可点击性规则。 | 否 |
| `docs/playwright_china_new_voucher_amount_clear.mjs` | 新增 | 新增只操作页面、不保存凭证的 Playwright 回归用例。 | 不涉及业务接口 |
| `docs/08-reference/59-china-new-voucher-amount-clear-fix-plan.md` | 已新增 | 本修复方案。 | 不涉及 |
| `docs/08-reference/60-china-new-voucher-amount-clear-fix-record.md` | 后续新增 | 实施后的代码清单、自动化证据、人工复测结果和回滚记录。 | 不涉及 |

### 5.1 JS 小增量设计

在 `ChinaNewVoucher` 类中新增私有页面辅助方法，例如：

```javascript
sync_amount_row(row, side, options = {}) {
    const input = row.querySelector(`.cf-${side}-input`);
    const otherSide = side === "debit" ? "credit" : "debit";
    const other = row.querySelector(`.cf-${otherSide}-input`);

    if (input.value !== "") {
        other.value = "";
        this.paint_amount(row, otherSide);
    }

    this.paint_amount(row, side);
    this.update_totals();
}
```

`add_row()` 中不再把金额同步逻辑分散写在匿名 `oninput` 函数里，而是保持原入口但调用上述新方法：

```javascript
input.addEventListener("input", () => {
    this.sync_amount_row(row, input.dataset.side);
});
```

为处理用户明确提出的按键场景，新增 `keydown` 监听：

```javascript
input.addEventListener("keydown", (event) => {
    if (event.key !== "Backspace" && event.key !== "Delete") return;

    // 不调用 preventDefault；浏览器仍负责删除字符。
    // 如本轮键将使值清空，可在下一次 input 后走统一同步分支。
    queueMicrotask(() => this.sync_amount_row(row, input.dataset.side));
});
```

实施时须根据浏览器事件顺序确定采用 `queueMicrotask` 或仅以 `input` 事件为最终更新来源。推荐优先方案是：

1. `input` 事件始终调用 `sync_amount_row()`，确保粘贴、剪切、输入法确认和程序性值变化后的普通录入路径正确。
2. `keydown` 只在实测需要时增加，且不得抢先清空值、不得拦截默认按键、不得重复改变借贷关系。
3. 如果 Chrome/Playwright 已证明 `input` 对 Backspace/Delete 足够稳定，则保留更小的改动：不增加 `keydown`，只使用集中后的 `sync_amount_row()`。文档中的 `keydown` 是兼容性预案，不应为了“看上去处理了按键”而无必要引入双重更新。

这样既能覆盖 Backspace/Delete，又不会影响复制粘贴、中文输入法和移动端数字键盘。

### 5.2 空值与借贷互斥规则

统一方法遵循以下状态表：

| 当前编辑方向 | 当前输入值 | 相反方向输入/九格 | 当前方向九格 | 合计与平衡 |
| --- | --- | --- | --- | --- |
| 借方或贷方 | 非空且可解析 | 清空 | 按金额重绘 | 立即重算 |
| 借方或贷方 | 空字符串 | 保持原值 | 清空 | 立即重算 |
| 借方或贷方 | 非法文本 | 当前 `paint_amount()` 规则显示为空 | 保持原值 | 按现有 `entries()` 规则计为 0 |

特别说明：删除借方金额时，不应顺带清空同一行贷方的有效金额；只有用户重新在某一方向输入非空金额时，才清空另一方向。这符合“借贷互斥”且避免删除动作误伤用户已经录入的另一边数据。

### 5.3 CSS 预案

默认不改 CSS。若人工复测确认透明输入层造成焦点难以辨识，可只增加如下视觉提示：

```css
.cf-amount:focus-within {
    outline: 2px solid rgba(37, 99, 235, .45);
    outline-offset: -2px;
}
```

该变更只用于提示焦点位置，不改变九格宽度、金额格式、输入类型或页面结构。若无需提示，则不提交 CSS 修改。

## 6. 预期效果

修复完成后，用户可以按照标准桌面表格录入习惯修改凭证金额：

1. 在借方输入 `100.00`，借方九格显示 `00000010000` 对应的金额位。
2. 按 `Backspace` 或选中后按 `Delete`，输入框字符被浏览器正常删除。
3. 值被删空时，该方向的九格立即全部为空，借方/贷方合计随之减少，借贷平衡状态随之刷新。
4. 在同一行录入贷方金额时，借方输入值和借方九格均被清空，反之亦然。
5. 仍需在凭证层面满足“总借方 = 总贷方”才能提交；这是正常会计控制，不是本缺陷。

## 7. 受影响模块与影响边界

| 模块 | 影响 | 说明 |
| --- | --- | --- |
| 中国财务工作台 / 新增凭证 Page | 直接影响 | 金额输入、九格显示、合计显示和焦点体验。 |
| 手工凭证保存前校验 | 间接影响 | `entries()` 读取到的金额将与页面显示一致。 |
| `create_manual_voucher` | 无接口变更 | 仍使用原参数 `company`、`posting_date`、`entries`、`remarks`。 |
| Journal Entry | 无逻辑变更 | 仍只在用户点击保存后由原服务创建。 |
| GL Entry / China Accounting Voucher | 无逻辑变更 | 仍由既有凭证记账链路生成。 |
| 现金流、报表、税务、公司初始化 | 无影响 | 本次不进入这些模块。 |

## 8. 测试与验收方案

### 8.1 自动化回归（实施后执行）

新增 Playwright 脚本仅测试页面交互，不点击“保存并记账”、不创建凭证：

```text
登录 aki_test.localhost
  -> 打开 china-new-voucher
  -> 定位第一行借方金额输入框
  -> 输入 100.00，断言借方九格、借方合计
  -> 使用 Backspace 删除至空，断言九格为空、合计更新
  -> 输入 100.00 后全选，按 Delete，断言九格为空、合计更新
  -> 输入借方 100.00，再输入贷方 100.00
  -> 断言借方 input 与借方九格同步清空，贷方显示正确
  -> 记录截图、控制台错误、网络异常
```

验收断言：

- `Backspace` 与 `Delete` 都能使真实 `input.value` 变为空。
- 对应 `.cf-digit-cells span` 的文本都为空。
- `.cf-total-debit` / `.cf-total-credit` 与当前输入值一致。
- `.cf-voucher-balance` 按既有规则显示“借贷不平衡”或“借贷平衡”。
- 脚本运行期间没有创建 `Journal Entry`、`GL Entry` 或 `China Accounting Voucher`。

### 8.2 人工复测流程（实施后执行）

测试前准备：

- 登录测试站点 `aki_test.localhost`。
- 进入“中国财务 > 新增凭证”。
- 不点击“保存并记账”，避免写入测试单据。

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 1 | 点击第一行借方金额九格区域，输入 `1234.56`。 | 借方九格、借方合计更新。 |
| 2 | 连续按 `Backspace`，直到金额为空。 | 每次按键可删除；最终九格清空、借方合计减少为 `0.00`。 |
| 3 | 再输入 `1234.56`，按 `Ctrl/Cmd + A`，按 `Delete`。 | 输入值和九格均清空；不需要刷新页面。 |
| 4 | 在借方输入 `100.00`，随后在同一行贷方输入 `100.00`。 | 借方的输入值和九格清空，贷方保留 `100.00`。 |
| 5 | 删除贷方金额。 | 贷方九格和贷方合计清空；借贷状态即时变化。 |
| 6 | 用鼠标离开再返回金额格、用 Tab 进入金额格，重复步骤 2 和 3。 | 焦点正常，删除行为一致。 |
| 7 | 取消离开页面或点击“清空”。 | 不提交、不生成凭证。 |

人工复测需记录浏览器名称和版本、页面截图、实际与预期是否一致，以及任何控制台/网络异常 URL。

## 9. 风险、兼容性与回滚

### 9.1 风险控制

1. 不能在 `keydown` 中调用 `preventDefault()`，否则可能反而导致 Backspace/Delete 无法删除。
2. 不能把“当前方向为空”误处理成“清空另一方向”，否则用户可能误删有效金额。
3. 不能在金额输入事件中调用保存接口，删除只是前端编辑行为。
4. 需验证粘贴金额、输入法编辑、移动端输入不会触发重复合计或错误互斥。
5. 测试脚本必须禁止点击保存按钮，避免污染测试数据。

### 9.2 回滚方案

若出现兼容性问题：

1. 先移除新增的 `keydown` 分支，保留以 `input` 事件为核心的统一同步方法。
2. 若仍异常，再将 `add_row()` 的金额事件恢复为原有匿名 `oninput` 实现。
3. 删除可选 CSS 焦点样式不会影响数据与记账。

本方案不涉及数据库迁移、数据修复或后端接口变更，因此无需数据回滚。

## 10. 实施完成后的沉淀要求

获准实施后，新增：

```text
docs/08-reference/60-china-new-voucher-amount-clear-fix-record.md
```

该记录应至少包含：

1. 实际修改的文件与精确代码位置。
2. 最终采用的是“仅 input 事件”还是“input + keydown 兼容分支”。
3. 自动化测试命令、执行日期、结果与截图/审计文件路径。
4. 人工复测步骤、测试浏览器、结果。
5. 是否创建任何业务单据（预期为否）。
6. 已知限制、风险、回滚结果与后续优化建议。

## 11. 执行结论

推荐将本问题作为“新增凭证金额输入与显示同步”缺陷处理，而不是修改凭证保存或数据库金额字段。最小实施路径是：在 `china_new_voucher.js` 中新增统一同步方法，确保空值、借贷互斥、九格和合计都从同一条前端路径更新；必要时才补充不拦截默认行为的删除按键兼容分支。

这样能解决用户的删除体验问题，同时保持现有会计控制、保存接口和下游凭证/总账数据链路不变。
