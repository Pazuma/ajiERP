# 新增凭证金额删除交互修复实施记录

## 1. 结论

已按《[新增凭证金额删除交互小增量修复方案](./59-china-new-voucher-amount-clear-fix-plan.md)》完成前端小增量修复。

在测试站点 `aki_test.localhost` 上的 Playwright 回归通过：

1. 借方金额录入后，金额九格正确显示。
2. 使用 `Backspace` 清空金额后，输入值、金额九格和借方合计同步清空。
3. 使用 `Delete` 清空金额后，输入值、金额九格和借方合计同步清空。
4. 同一行从借方改录贷方时，借方输入值与借方金额九格同步清空，贷方保留正确显示。

测试脚本没有点击“保存并记账”，没有调用凭证创建接口，因此本次验证**没有创建或修改 Journal Entry、GL Entry、China Accounting Voucher 或任何数据库业务数据**。

## 2. 实施信息

| 项目 | 内容 |
| --- | --- |
| 实施日期 | 2026-09-08 |
| 测试站点 | `http://aki_test.localhost:8300` |
| 页面 | `China Finance -> 新增凭证`（`/desk/china-new-voucher`） |
| 浏览器 | Playwright Chromium（容器内无头模式） |
| 数据写入 | 无；仅页面内存交互 |
| 实施原则 | 前端小增量、保留旧接口、不改数据库 |

## 3. 实际修改的文件

| 文件 | 修改类型 | 实际修改内容 |
| --- | --- | --- |
| `development/frappe-bench/apps/china_finance/china_finance/china_finance/page/china_new_voucher/china_new_voucher.js` | 修改 | 新增 `bind_amount_editor()` 与 `sync_amount_row()`；金额输入统一经同步方法更新九格、借贷互斥和合计。 |
| `docs/playwright_china_new_voucher_amount_clear.mjs` | 新增 | 新增不保存凭证的浏览器回归脚本，覆盖输入、Backspace、Delete 和借贷互斥。 |
| `docs/china-finance-test-evidence/new-voucher-amount-clear.json` | 自动生成 | 本次浏览器验证的结构化结果。 |
| `docs/china-finance-test-evidence/new-voucher-amount-clear.png` | 自动生成 | 本次浏览器验证截图。 |
| `docs/08-reference/60-china-new-voucher-amount-clear-fix-record.md` | 新增 | 本实施与验证记录。 |

未修改：

- `china_new_voucher.css`：实测焦点和点击区域可用，未引入非必要 CSS 改动。
- `china_finance.services.manual_voucher.create_manual_voucher`：接口、参数和返回结构均未变。
- 任何 Python 文件、DocType、数据库表或数据。

## 4. 代码变更说明

### 4.1 统一金额同步路径

新增：

```javascript
bind_amount_editor(row, input)
sync_amount_row(row, side)
```

原来每个金额输入框只在匿名 `oninput` 中局部处理当前金额。现在每个输入框统一绑定到 `bind_amount_editor()`：

```text
input 事件
  -> sync_amount_row(row, side)
  -> 重绘当前方向金额九格
  -> 如当前值非空，清空相反方向输入值与金额九格
  -> 重算借方合计、贷方合计、借贷平衡和大写金额
```

这使“真实透明输入框”“九格显示层”“合计显示”在同一同步路径内更新。

### 4.2 Backspace / Delete 兼容分支

在 `keydown` 中仅监听 `Backspace` 和 `Delete`，使用 `window.setTimeout(sync, 0)` 在浏览器执行默认删除后再次走统一同步方法。

关键约束：

- 未调用 `preventDefault()`，浏览器仍正常删除输入字符。
- `input` 事件仍是常规输入、粘贴、剪切和输入法变更的主要同步来源。
- 删除当前方向金额不会误删相反方向已经存在的有效值；只有录入当前方向的非空金额时，才按原有借贷互斥规则清空另一方。

### 4.3 补齐最少行“删除本行”时的显示同步

原页面保留至少五行。用户点击某一行删除按钮、且当前不足以真正移除该行时，页面原本会清空所有 `input` 值；本次在该分支中补充重绘借方和贷方的金额九格。

此补充不改变“至少保留五行”的旧行为，只避免输入值已清空而金额格残留显示。

## 5. 调用链路与接口影响

```text
用户在新增凭证金额格输入 / Backspace / Delete
  -> input.cf-amount-input
  -> bind_amount_editor
       -> input 事件（常规同步）
       -> keydown 删除键兼容分支（默认删除后同步）
  -> sync_amount_row
       -> paint_amount（借方/贷方九格）
       -> update_totals
       -> entries
       -> 合计、借贷平衡、合计大写

用户点击“保存并记账”（本次测试未执行）
  -> 既有 save()
  -> 既有 create_manual_voucher(company, posting_date, entries, remarks)
  -> Journal Entry
  -> GL Entry
  -> China Accounting Voucher
```

接口影响结论：

- `create_manual_voucher` 未修改。
- `save()` 未修改。
- 后端校验、借贷平衡规则和下游记账链路未修改。
- 本次仅修复保存前页面的金额输入与显示一致性。

## 6. 自动化验证

### 6.1 执行命令

在 `devcontainer-frappe-1` 容器的 `/workspace` 中执行：

```bash
node --check development/frappe-bench/apps/china_finance/china_finance/china_finance/page/china_new_voucher/china_new_voucher.js
node --check docs/playwright_china_new_voucher_amount_clear.mjs
node docs/playwright_china_new_voucher_amount_clear.mjs
```

结果：

- 两个 JavaScript 文件语法检查通过。
- Playwright 进程退出码为 `0`。
- 所有四项业务交互断言通过。

### 6.2 通过项

| 用例 | 操作 | 结果 |
| --- | --- | --- |
| 金额九格渲染 | 借方输入 `100.00` | 通过；借方金额九格显示非空。 |
| Backspace 清空 | `Ctrl+A` 后按 `Backspace` | 通过；借方 input、九格和合计均清空。 |
| Delete 清空 | `Ctrl+A` 后按 `Delete` | 通过；借方 input、九格和合计均清空。 |
| 借贷互斥 | 输入借方 `100.00`，再输入贷方 `100.00` | 通过；借方 input 和九格清空，贷方显示正确。 |
| 业务写入保护 | 脚本不点击“保存并记账” | 通过；结果文件标记 `writes_business_documents: false`。 |

测试证据：

- [结构化结果 JSON](../china-finance-test-evidence/new-voucher-amount-clear.json)
- [页面截图 PNG](../china-finance-test-evidence/new-voucher-amount-clear.png)

## 7. 页面既有异常（未归因于本次改动）

本次浏览器运行仍记录到以下问题，但金额删除断言全部通过，且这些异常不由本次 JS 改动引入：

| 分类 | 现象 | 已知线路 | 本次处理 |
| --- | --- | --- | --- |
| 静态资源 404 | `/custom_filters/public/js/naming_series_i18n.js` 返回 404（本次出现两次） | Desk 公共资源加载链路 | 不改动，已在既有中国财务问题记录中跟踪。 |
| 路由/资源 404 | `/undefined` 返回 404（本次出现一次） | 页面公共脚本或资源拼接链路 | 不改动，需后续按请求发起方分类。 |
| 浏览器运行时错误 | `Cannot read properties of null (reading 'join')`（本次出现两次） | Desk 公共脚本链路 | 不改动，需单独定位空值来源。 |
| Socket 连接 | `socket.io: Unauthorized: TypeError: fetch failed` | 无头浏览器实时通讯链路 | 不影响本页面交互断言；未修改认证或 Socket 配置。 |

上述条目不是“通过”的代替条件；它们仍应在总问题表中持续跟踪。本次结论仅限新增凭证的金额删除功能。

## 8. 人工复测流程

自动化已覆盖核心交互，但发布前仍建议按以下步骤人工确认：

1. 浏览器登录 `aki_test.localhost`，进入“中国财务 -> 新增凭证”。
2. 在第一行借方金额输入 `1234.56`，确认九格和借方合计变化。
3. 连续按 `Backspace` 至金额清空，确认九格、合计、借贷平衡提示同步变化。
4. 再输入 `1234.56`，全选后按 `Delete`，确认结果相同。
5. 输入借方 `100.00` 后，在同一行贷方输入 `100.00`，确认借方输入值和九格同步清空。
6. 在借方、贷方之间用鼠标点击和 `Tab` 切换焦点，重复删除操作。
7. 不点击“保存并记账”；退出或点击“清空”，确认不会产生业务单据。

人工复测状态：**待执行**。执行时应补充浏览器版本、截图与实际结果，不应将本自动化结果替代为人工通过。

## 9. 回滚方案

本次没有数据库或接口变更。若发现输入法、特定浏览器或移动端兼容问题：

1. 优先仅移除 `keydown` 的删除键兼容分支，保留 `input -> sync_amount_row()` 的统一同步路径。
2. 如仍需完整回滚，恢复 `add_row()` 原有金额输入绑定方式并移除新增的两个页面私有方法。
3. 删除新增 Playwright 脚本不会影响业务运行。

无需执行数据库回滚或数据修复。
