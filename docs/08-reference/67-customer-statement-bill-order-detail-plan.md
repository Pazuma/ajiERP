---
title: 客户对账明细列出账单及对应订单方案
---

# 客户对账明细列出账单及对应订单方案

## 1. 状态与目标

本文件仅为方案文档，本次不修改业务代码。

当前页面能够计算期初余额和期间总账流水，但截图中出现“期初余额 CNY -375、期间 0 张凭证、0 条流水”，用户无法知道 `-375` 由哪张账单形成，也无法追溯对应销售订单。

改造目标：选择客户和日期后，对账明细同时列出：

1. 截至起始日期仍未结清的期初账单及对应订单；
2. 所选期间内新增的销售发票、收款、退款、贷项和调整流水；
3. 每张账单的原始金额、已结金额、未结金额；
4. 发票对应的销售订单和送货单；
5. 期间流水后的滚动余额。

期初未结账单用于解释期初余额，不重复计入本期借方或贷方。

筛选条件必须同时使用 `company + customer + from_date + to_date`。页面选择的公司是业务数据边界：只显示该公司名下与所选客户关联的订单、送货、发票、收款及调整，不得因为客户在其他公司也有业务而混入跨公司单据。

## 1.1 对账明细的完整范围

“对账明细”不是单一 GL Entry 表，也不是单一送货单表。目标展示范围为：

| 业务对象 | 是否显示 | 作用 |
| --- | --- | --- |
| Sales Order | 是 | 展示客户下单内容、订单金额及后续执行状态 |
| Delivery Note | 是 | 展示订单实际送货数量和送货金额 |
| Sales Invoice | 是 | 作为正式账单，展示开票金额和未结金额 |
| Payment Entry | 是 | 展示账单对应收款、退款及核销金额 |
| Journal Entry | 有客户往来分录时显示 | 展示手工调整、冲销等余额变化 |
| GL Entry | 作为金额主账 | 保证期初、本期借贷和期末余额正确 |

订单明细与财务账单需要同时显示，但承担不同作用：订单/送货用于说明业务内容，销售发票/收款/总账用于确认应收金额。未开票订单可以显示“未开票”，但不能直接计入应收余额。

## 2. 业务口径

### 2.1 两类明细

| 明细类型 | 日期范围 | 金额作用 |
| --- | --- | --- |
| 期初未结账单 | 发票日期早于起始日期，且截至起始日前仍有未结金额 | 解释期初余额，不计入本期借贷 |
| 本期往来流水 | 起始日期至截止日期内的 GL Entry | 计入本期借方、本期贷方和滚动余额 |

页面不能把期初发票原始金额再次加入本期借方，否则会重复计算。顶部汇总仍满足：

```text
期末余额 = 期初余额 + 本期借方 - 本期贷方
```

### 2.2 账单定义

首期“账单”以已提交、未取消的 `Sales Invoice` 为主，包括普通销售发票和退货/贷项。手工 Journal Entry 形成的客户期初余额无法对应销售订单，应独立显示为“期初调整项”，不能伪造成销售发票。

### 2.3 未结金额时间口径

不能直接使用 Sales Invoice 当前 `outstanding_amount` 解释历史起始日，因为该值反映当前状态。应优先复用 ERPNext Accounts Receivable / Payment Ledger 的历史截止日算法，按 `posting_date < from_date` 计算当时未结金额。

如标准应收报表无法提供所需字段，再新增只读聚合函数，但不得自行用当前未结金额倒推历史余额。

### 2.4 金额方向

- 普通销售发票通常形成客户应收；
- 退货/贷项冲减应收；
- 收款减少应收；
- 退款恢复应收；
- Journal Entry 按实际借贷方向处理。

最终金额方向以总账或付款台账结果为准，不根据单据名称硬编码正负号。

## 3. 页面预期

### 3.0 页面筛选及加载条件

用户依次选择：

```text
公司 -> 对账类型 Customer -> 往来单位 -> 起始日期 -> 截止日期
```

点击“加载往来账”后，服务端必须按当前公司查询该客户的完整关联链路。公司、客户或日期任一变化，当前明细立即标记为过期，必须重新加载。

### 3.1 期初账单区

在“余额”与“本期往来明细”之间新增只读表格“期初未结账单”。建议列：

| 字段 | 含义 |
| --- | --- |
| 发票日期 | Sales Invoice posting_date |
| 销售发票 | 可点击跳转的 Sales Invoice |
| 客户订单号 | 客户采购订单号，如可用 |
| 关联销售订单 | 一张发票可能对应多张 Sales Order |
| 关联送货单 | 一张发票可能对应多张 Delivery Note |
| 原始账单金额 | 发票原始应收金额 |
| 起始日前已结 | 截至起始日前累计核销金额 |
| 期初未结金额 | 起始日前仍未结部分 |
| 币种 | 对账币种 |

表格底部显示“期初账单未结合计”。该合计应与可按发票追踪的期初余额一致；若存在手工调整，再单独显示期初调整项和差异解释。

### 3.2 本期往来明细区

现有 `China Reconciliation Line` 表格至少显示：

- 过账日期；
- 业务类型；
- 凭证类型和凭证号；
- 销售发票；
- 关联销售订单；
- 关联送货单；
- 摘要；
- 借方；
- 贷方；
- 滚动余额。

Payment Entry 通过 `Payment Entry Reference` 显示其核销的 Sales Invoice，再由发票明细反查订单和送货单。

### 3.3 订单及账单明细区

为了直接达到截图中红框区域的预期，建议对账明细按“订单/账单”一行或分组展示，至少包含：

| 字段 | 来源/说明 |
| --- | --- |
| 订单日期 | Sales Order.transaction_date |
| 销售订单 | Sales Order.name，可点击 |
| 客户订单号 | Sales Order.po_no 等客户参考号 |
| 产品编码/名称 | Sales Order Item |
| 订单数量 | Sales Order Item.qty |
| 订单金额 | Sales Order Item.amount/base_amount，按对账币种口径 |
| 已送数量 | Delivery Note Item 汇总 |
| 送货单 | 关联 Delivery Note 列表 |
| 销售发票 | 关联 Sales Invoice 列表 |
| 账单金额 | 发票应收金额 |
| 已收金额 | 截止日期前对该发票的有效核销金额 |
| 未结金额 | 截止日期时点账单未结金额 |
| 状态 | 未送货、部分送货、已送货、未开票、部分开票、已开票、部分收款、已结清 |

一张订单可能拆分为多张送货单和销售发票，一张发票也可能合并多个订单。实现时必须保留多对多关系，不能只取第一张订单或第一张发票。

建议页面分为两个视图：

- “订单账单明细”：面向业务核对，显示产品、数量、订单、送货、发票、已收和未结；
- “财务流水”：面向财务核对，显示 GL Entry 借贷和滚动余额。

两者使用同一批查询条件和同一快照，但只有财务流水参与余额公式。

### 3.4 无本期流水场景

当本期 0 张凭证但存在期初余额时，不显示空白页面。应显示：

```text
期初未结账单：若干张
本期往来流水：0 条
期末余额：等于期初余额
```

这样截图中的 `-375` 能被具体账单解释。

## 4. 数据来源与关联链路

### 4.0 公司边界

每个来源都必须带公司过滤或通过父单据校验公司：

```text
Sales Order.company = company
Delivery Note.company = company
Sales Invoice.company = company
Payment Entry.company = company
GL Entry.company = company
所有来源的 customer/party = customer
```

关联子表不能只凭订单号或发票号加入结果，还要复核父单据公司、客户、docstatus 和取消状态。

### 4.1 期初未结账单

```text
company + customer + from_date
  -> ERPNext Accounts Receivable / Payment Ledger（截止 from_date 前一天）
  -> 得到 Sales Invoice 在该时点的未结金额
  -> Sales Invoice
  -> Sales Invoice Item.sales_order
  -> Sales Invoice Item.delivery_note
  -> 汇总为每张发票一行
```

### 4.2 本期销售发票

```text
GL Entry.voucher_type = Sales Invoice
  -> GL Entry.voucher_no
  -> Sales Invoice
  -> Sales Invoice Item.sales_order / delivery_note
```

### 4.3 本期收款

```text
GL Entry.voucher_type = Payment Entry
  -> Payment Entry Reference
  -> reference_doctype = Sales Invoice
  -> reference_name
  -> Sales Invoice Item.sales_order / delivery_note
```

### 4.4 手工调整

```text
GL Entry.voucher_type = Journal Entry
  -> Journal Entry
  -> 如存在 against_voucher_type / against_voucher，则展示关联发票
  -> 无明确来源时显示“调整凭证”，订单留空
```

### 4.5 完整订单到账款链路

```text
Company + Customer + Date Range
  -> Sales Order
  -> Sales Order Item
       -> Delivery Note Item.against_sales_order / so_detail
       -> Sales Invoice Item.sales_order / so_detail
            -> Sales Invoice（正式账单）
                 -> Payment Entry Reference（收款核销）
                 -> GL Entry（应收主账金额）
  -> 汇总为订单账单明细
  -> 与财务流水及余额进行一致性校验
```

日期建议支持两种明确口径：

- 业务期间：订单、送货、发票任一业务日期落在区间内则展示；
- 对账期间：期初未结账单 + 期间财务流水为金额口径。

首期页面仍使用同一组起止日期，但服务端返回时给每行标记 `included_reason`，例如“期间订单”“期间发票”“期初未结”，避免用户不清楚为什么该订单被纳入。

## 5. 建议新增接口

保留现有 `preview_customer_account_statement` 参数不变。优先扩展其返回结构，旧字段继续保留，并新增：

```python
{
    "opening_documents": [],
    "opening_document_count": 0,
    "opening_document_total": 0,
    "opening_adjustment": 0,
    "rows": []
}
```

建议新增内部函数：

```python
def get_opening_customer_documents(company, customer, from_date):
    """返回起始日前的未结发票和不可按发票归属的调整项。"""

def get_sales_invoice_links(invoice_names):
    """批量返回发票对应的销售订单、送货单和客户订单号。"""

def enrich_customer_ledger_rows(rows):
    """批量为本期总账流水补充发票、订单和送货关联。"""
```

为订单账单视图建议新增内部函数：

```python
def get_customer_order_billing_details(company, customer, from_date, to_date):
    """读取指定公司客户的订单、送货、发票、核销和未结关系，不写业务数据。"""
```

`preview_customer_account_statement` 返回结构新增 `order_billing_rows`，旧的 `rows`、余额和快照字段保持不变。

不新增同义白名单接口，避免前端再次出现多个取数口径。旧 Delivery 预览和旧 PDF 接口继续保留。

## 6. 建议修改文件与代码

| 文件 | 小增量修改 |
| --- | --- |
| `china_finance/services/customer_reconciliation_statement.py` | 新增期初历史未结取数、发票关联批量查询、本期流水关联补充；扩展现有预览返回结构。 |
| `china_reconciliation_statement.json` | 新增订单账单明细子表、期初账单子表、期初账单合计和期初调整金额；客户 Ledger 分支显示。 |
| `china_reconciliation_statement.js` | 加载往来账时分别填充订单账单明细、期初账单和财务流水，提示中显示订单数、账单数、本期凭证数和期末余额。 |
| `china_reconciliation_statement.py` | 保存时重新校验期初账单快照、本期 GL 快照及汇总关系；旧 Delivery 分支保留。 |
| `china_reconciliation_line.json` | 本期流水新增/显示销售发票、关联销售订单和关联送货单；复用现有 order_no、delivery_note。 |
| `china_reconciliation_opening_document.json` | 新增只读子表，保存期初发票、订单、原始金额、已结和未结快照。 |
| `china_reconciliation_order_billing_line.json` | 新增只读子表，保存订单行、送货、发票、收款和未结金额的关联快照。 |
| `client_akivision/utils/customer_reconciliation_pdf.py` | Ledger PDF 分支增加期初未结账单与订单，旧商品 PDF 分支不变。 |
| `client_akivision/templates/customer_account_statement_pdf.html` | PDF 分为“期初未结账单”和“本期往来流水”两张表。 |
| `china_finance/tests/test_customer_account_statement.py` | 补期初未结、部分收款、多订单发票、退款、贷项、调账和历史截止日测试。 |

## 7. 数据结构建议

新增子表 `China Reconciliation Opening Document`，建议字段：

```text
posting_date
sales_invoice
customer_po_no
related_sales_orders
related_delivery_notes
original_amount
settled_amount
outstanding_amount
currency
snapshot_reference
```

一张发票可能关联多张订单，因此 `related_sales_orders` 和 `related_delivery_notes` 使用只读 Data/Small Text，而不是单值 Link。销售发票字段保留 Link，便于跳转。

本期明细建议新增：

```text
sales_invoice
related_sales_orders
related_delivery_notes
```

新增子表 `China Reconciliation Order Billing Line`，建议字段：

```text
sales_order / sales_order_item
order_date / customer_po_no
item_code / item_name / uom
ordered_qty / delivered_qty / billed_qty
order_amount / billed_amount / paid_amount / outstanding_amount
delivery_notes / sales_invoices
billing_status / payment_status
included_reason / currency
```

只有唯一订单/送货单时才同步写入已有 `order_no`、`delivery_note`，以兼容旧导出和旧代码。

## 8. 保存与快照校验

预览快照标识必须同时覆盖：

- 查询条件；
- 期初未结发票及历史时点未结金额；
- 期初调整项；
- 本期 GL Entry 名称、修改时间、借贷金额；
- 发票到订单/送货单的关联结果。

保存前服务端重新生成快照。如果期间补记发票、补录收款、取消凭证、修改发票订单关联或历史未结金额变化，应提示重新加载。

已提交对账单继续保存当时快照，不因后续收款自动变化。后续变化通过新版本或替代对账单体现。

## 9. 金额核对关系

```text
期初余额
  = 期初可追踪未结账单合计
  + 期初调整项

期末余额
  = 期初余额
  + 本期借方
  - 本期贷方
```

如果两组关系不能在容差范围内成立，页面应明确显示差异并禁止提交，不能为了让数字一致而隐去账单。

## 10. 受影响模块

| 模块 | 影响 | 预期效果 |
| --- | --- | --- |
| 客户对账单 | 增加期初账单和本期流水两类明细 | 余额可以追溯到具体账单和订单 |
| 销售订单及订单明细 | 按公司、客户、日期只读查询 | 红框明细区能看到订单产品、数量和金额 |
| Accounts Receivable / Payment Ledger | 只读复用历史截止日算法 | 正确还原起始日前的未结金额 |
| Sales Invoice | 只读获取账单及明细关联 | 显示原始账单、订单和送货单 |
| Payment Entry | 只读获取核销发票 | 收款行可解释对应哪张账单和订单 |
| Journal Entry | 只读获取调整来源 | 无法对应订单时明确显示调整项 |
| Sales Order / Delivery Note | 只读关联 | 不参与重复计价，不修改原业务单据 |
| PDF 导出 | Ledger 分支增加两张明细表 | 导出内容与页面及快照一致 |
| 供应商/银行对账 | 不修改 | 原流程保持不变 |

## 11. 兼容策略

- 不修改 `generate_statement`、`preview_customer_account_statement` 的入参；
- 预览接口只新增返回字段，不删除旧字段；
- 不改变 `download_saved_customer_reconciliation_statement` URL，在 Ledger 内部分支增强模板；
- 历史 `statement_basis = Delivery` 单据继续使用旧校验和旧模板；
- 不修改 Sales Invoice、Payment Entry、Journal Entry、GL Entry 的写入和提交逻辑；
- 不把订单金额、送货金额和总账金额重复累计；
- 不要求历史数据迁移，历史 Ledger 快照缺少期初子表时仍可查看，重新生成的新版本才使用增强结构。

## 12. 异常与边界

- 期初余额为零：不显示期初未结区或显示 0 条；
- 期初有余额但找不到发票：显示期初调整项，不伪造发票；
- 一张发票对应多张订单：完整列出，不只取第一张；
- 一笔收款核销多张发票：完整列出全部关联发票和订单；
- 预付款尚未分配发票：显示“未分配收款/预收款”，订单为空；
- 发票跨币种：按币种拆分，禁止直接加总；
- 退货/贷项：按应收报表和 GL 方向冲减；
- 截止日之后发生收款：不得影响历史起始日未结金额；
- 无来源单据读取权限：拒绝生成，避免金额与可见明细不一致。

## 13. 测试场景

1. 起始日前一张未付款发票，对应一张销售订单；
2. 起始日前一张部分收款发票，验证原始、已结和未结；
3. 起始日前发票，截止日之后才收款，验证历史未结不受影响；
4. 一张发票对应多张销售订单和送货单；
5. 一笔 Payment Entry 核销多张发票；
6. 预收款未分配发票；
7. 期初仅有 Journal Entry 调整；
8. 本期销售发票、收款、退款和贷项完整流水；
9. 多币种、取消单、权限不足和预览后来源变化；
10. 历史 Delivery 对账、供应商对账和银行对账回归。

## 14. 最终预期效果

以截图数据为例，页面不再只显示“期初余额 CNY -375、0 条流水”。加载后应在“期初未结账单”中列出构成 `-375` 的具体销售发票、对应销售订单、送货单、原始金额、已结金额和期初未结金额；本期没有新业务时，“本期往来流水”仍为 0 条，期末余额保持 `-375`。

当期间内存在发票或收款时，本期明细逐笔显示其对应发票、订单、借方、贷方和滚动余额。页面汇总、保存快照及 PDF 导出保持一致，同时不创建或修改任何订单、送货单、发票、付款或总账数据。

最终红框内不再是仅有“过账日期、单据、余额”的空表，而是能直接看到所选公司与客户关联的订单行、产品、数量、送货单、销售发票、账单金额、已收金额和未结金额；同时可以切换查看对应财务流水。跨公司数据不会出现，未开票订单会明确标记但不会计入应收余额。
