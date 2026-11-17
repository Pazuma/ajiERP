# 客户对账单优化方案（增量设计，暂不改代码）

## 1. 背景与现状

客户对账单目前存在两套数据口径：

- “订单账单明细”按销售订单明细关联送货单、销售发票和收款单，能够计算开票、收款及未结金额。
- “对账明细”按客户的 `GL Entry` 流水生成，当前只写入借方、贷方、余额等总账字段。

因此，对账明细中的 `billing_status`、`payment_status`、`original_amount`、`settled_amount`、`outstanding_amount` 没有赋值，Frappe 对 Currency 字段显示默认 `0.00`，状态字段为空；同时子表没有汇总行，用户无法看到明细合计与余额平衡关系。

## 2. 优化目标

在保留既有接口和 Ledger 对账口径的前提下，补充来源单据关联和结算信息，明确金额汇总关系，并修正订单明细的“部分开票”判断。

目标结果：

- 有发票但未全部开票时显示“部分开票”。
- 销售发票行显示原始金额、已结金额、未结金额和收款状态。
- 收款单行显示其关联发票及分摊金额，避免把未分配收款误判为已结清。
- 页面提供借方、贷方、原始金额、已结金额、未结金额合计，并能与期末余额核对。
- 旧调用方继续调用原有白名单方法，不改变参数和现有返回字段；新字段采用向后兼容的可选字段。

## 3. 拟修改文件与代码点

以下为后续实施时的文件清单，本次仅记录，不修改代码。

| 文件 | 拟修改内容 |
| --- | --- |
| `china_finance/china_finance/services/customer_reconciliation_statement.py` | 在现有 `get_customer_ledger_snapshot()` 的 Ledger 分支中增加行 enrich 分支；新增内部 `_build_invoice_settlement_map()`、`_classify_billing_status()` 等辅助函数；保留 `preview_customer_account_statement()` 的签名和既有核心返回字段。补充 `row` 级金额字段及 `summary` 汇总字段。修正 `get_customer_order_billing_details()` 的部分开票判断。 |
| `china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js` | 加载快照时兼容读取新增汇总字段；对账明细区域增加汇总展示或底部统计；旧站点缺少新字段时继续跳过，保持当前 `has_field/set_if_exists` 兼容逻辑。 |
| `china_finance/china_finance/doctype/china_reconciliation_line/china_reconciliation_line.json` | 视实际展示需要调整字段顺序、列可见性和说明；不删除现有字段，不改变字段名和类型。必要时为金额字段增加精度/说明。 |
| `china_finance/china_finance/doctype/china_reconciliation_order_billing_line/china_reconciliation_order_billing_line.json` | 若订单明细单独维护状态字段，则同步确认“部分开票”选项和金额字段；只做元数据增量调整。 |
| `china_finance/china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.json` | 如采用父表汇总字段，新增只读汇总字段（例如 `line_original_total`、`line_settled_total`、`line_outstanding_total`）；保留现有 `period_*` 和 `closing_balance` 字段。 |
| `china_finance/china_finance/tests/test_customer_reconciliation_statement.py` | 新增服务层测试，覆盖无发票、部分开票、全额开票、部分收款、已结清、未分配收款、期初账单和多凭证汇总。 |

## 4. 调用链路

```text
表单“加载往来账”按钮
  -> frappe.call("china_finance.services.customer_reconciliation_statement.preview_customer_account_statement")
  -> get_customer_ledger_snapshot()
      -> _validate_filters()
      -> 查询客户 GL Entry（期初 + 期间）
      -> 生成 Ledger rows（借/贷/余额）
      -> enrich_customer_ledger_rows(rows)
          -> 关联 Sales Invoice Item / Payment Entry Reference
          -> 生成发票、订单、送货单关联
          -> 新增结算金额和状态字段
      -> get_opening_customer_documents()
      -> get_customer_order_billing_details()
      -> 计算 period_debit / period_credit / period_balance / closing_balance
      -> 返回原字段 + 可选 summary
  -> china_reconciliation_statement.js 回填父表及 lines 子表
  -> Frappe 表单展示状态、金额及汇总
```

## 5. 关键业务规则

### 5.1 开票状态

按订单明细数量（必要时按金额兜底）判断：

- 发票数量为 0：`未开票`
- `0 < billed_qty < ordered_qty`：`部分开票`
- `billed_qty >= ordered_qty`：`已开票`

退货、取消单据不计入已开票数量；金额和数量均使用已提交单据。

### 5.2 收款状态

- 已分摊收款为 0：`未收款`
- `0 < settled_amount < original_amount`：`部分收款`
- `settled_amount >= original_amount`：`已收款`（展示层可映射为“已结清”）
- Payment Entry 未关联发票：`未分配`，不冲减某一张发票的未结金额。

### 5.3 金额口径与平衡

对账明细行：

```text
outstanding_amount = original_amount - settled_amount
period_balance = period_debit - period_credit
closing_balance = opening_balance + period_balance
```

汇总应同时返回借方、贷方和结算金额合计，允许前端显示：

```text
未结合计 = 原始账单合计 - 已结合计
```

结算汇总与总账余额不强行相等；差额应保留在 `opening_adjustment` 或差异说明中，避免掩盖跨期、未分配收款等真实差异。

## 6. 兼容与增量策略

- 不改动现有白名单方法名称、参数顺序和既有字段含义。
- 新增字段只追加到返回字典；旧客户端忽略未知字段即可正常工作。
- 前端继续使用 `has_field()` 和 `set_if_exists()`，旧站点未 migrate 时不阻断加载。
- 不直接修改销售订单、销售发票、收款单，仅建立只读快照。
- 先在 Ledger 分支实施；Delivery、Supplier、Bank 分支保持原逻辑，避免扩大影响面。
- 若需要持久化汇总，优先新增只读字段，不复用或重定义现有 `period_*` 字段。

## 7. 受影响模块

- China Finance：客户对账单服务、对账单表单、对账明细子表。
- ERPNext Accounts：Sales Order、Delivery Note、Sales Invoice、Payment Entry、Payment Entry Reference、GL Entry 的读取关系。
- 权限：仍沿用 Customer、来源凭证及对账单权限校验；无权限的来源凭证不得参与可见金额计算。
- 报表/导出：客户对账单 PDF 若读取 `lines`，需同步确认新列和汇总是否纳入导出。

## 8. 预期效果与验收

- 点击“加载往来账”后，对账明细每行不再因未赋值而显示空状态和 `0.00`（确无业务数据时才显示 0）。
- 部分开票、部分收款、已收款、未分配等状态与单据关系一致。
- 页面可见本期借方、本期贷方、本期余额、原始账单、已结、未结合计；期末余额计算可复核。
- 既有接口调用、旧数据打开、非客户对账类型均无回归。
- 自动化测试覆盖上述状态组合，并验证重复加载不会产生重复明细。

## 9. 实施前需确认的业务选择

1. “已结/未结”是否统一按销售发票口径计算，还是 Ledger 行仅展示总账金额、结算信息单独展示。
2. 汇总是采用父表新增只读字段，还是仅由前端对子表实时合计。
3. PDF 导出是否需要同步增加开票/收款状态和结算汇总。

