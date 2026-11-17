---
title: 客户往来对账单完整账款流水改造方案
---

# 客户往来对账单完整账款流水改造方案

## 1. 文档状态

本文件仅为实施方案，本次不修改业务代码。

目标是把“中国财务 -> 对账单 -> 新建对账单”完善为真正的客户往来对账：选择公司、客户和日期后，预览该期间的应收账款流水、发生金额和余额，确认后保存为历史快照并导出给客户。

实施遵循以下原则：

- 小增量修改，优先新增客户往来账预览分支；
- 不修改现有 `generate_statement`、送货单预览和 PDF 导出接口的签名；
- 不修改销售发票、付款、总账、订单和送货单的记账逻辑；
- 对账金额以已提交、未取消的 `GL Entry` 为主账口径；
- 已保存对账单是快照，来源单据后续变化不能静默改变历史对账单；
- 订单、送货单信息只用于辅助追溯，不替代财务账款。

## 2. 当前缺口

当前页面已经可以选择 Customer，但还没有达到完整对账效果：

1. “加载对账数据”只查询 `Delivery Note` 商品行，不包含销售发票、收款、退款、贷项和手工调账；
2. 页面没有完整展示期初余额、本期应收、本期收款和期末余额；
3. 客户对账仍显示“往来类型”“银行账户”“银行或往来科目”等非当前场景字段，容易误解；
4. 选择客户和日期后需要再寻找按钮，缺少明确的“待加载/已加载/来源变化”状态；
5. 送货金额与财务应收金额可能因开票时间、税额、退货或调整而不一致；
6. 当前保存校验要求客户明细必须来自 Delivery Note，不接受真实的财务凭证流水；
7. 现有 PDF 模板以商品交付行为主，不能完整表达期初、本期借贷和滚动余额。

仓库已有 `china_finance.services.reconciliation.generate_statement`，它按 `GL Entry` 计算期初、本期借贷和期末余额。新方案应抽取/复用其只读取数能力，不复制另一套余额算法。

## 3. 业务口径

### 3.1 主账口径

客户对账主数据源为 `GL Entry`，筛选条件：

- `company = 对账单.company`；
- `party_type = Customer`；
- `party = 对账单.party`；
- `posting_date <= 截止日期`；
- `is_cancelled = 0`；
- 用户对来源凭证具有读取权限；
- 只统计客户应收应付性质的往来分录，不能混入与该客户无关的普通科目分录。

金额符号沿用总账：

```text
期初余额 = 起始日期前借方合计 - 贷方合计
本期增加 = 期间借方合计
本期减少 = 期间贷方合计
期末余额 = 期初余额 + 本期借方 - 本期贷方
```

一般情况下，销售发票增加客户应收，收款、贷项和退款冲抵应收；最终方向必须以实际 GL Entry 借贷为准，不按单据名称猜测金额符号。

### 3.2 页面业务分类

为了便于客户理解，可在不改变会计金额的前提下新增展示分类：

| 来源凭证 | 展示分类 | 典型效果 |
| --- | --- | --- |
| Sales Invoice | 销售发票/贷项 | 增加或冲减应收 |
| Payment Entry | 收款/退款 | 减少或恢复应收 |
| Journal Entry | 调整凭证 | 调整往来余额 |
| 其他合法 GL 来源 | 其他账款变动 | 按借贷方向计入 |

分类仅用于显示。借方、贷方、滚动余额必须直接采用主账取数结果。

### 3.3 送货与订单关联

`Sales Order`、`Delivery Note` 不直接决定应收余额。需要展示订单号或送货单号时，通过销售发票明细等标准关联只读补充；无法可靠关联时留空，不拼凑、不重复计入金额。

可保留现有“按送货单生成客户明细 PDF”作为独立业务清单入口，但页面文案应区分：

- 客户往来对账单：财务账款、发票、收款和余额；
- 订单/送货对账明细：商品、数量、单价和交付金额。

## 4. 目标页面

### 4.1 客户分支字段

客户对账显示：公司、币种、对账类型、往来单位、起始日期、截止日期、确认方式、余额汇总、往来账明细、差异和备注。

客户对账隐藏：只读的“往来类型”、银行账户、银行科目、银行快照字段、采购拦截和采购豁免字段。

供应商和银行对账继续走原有分支，字段显示规则不改变其业务能力。

### 4.2 加载交互

选择客户和有效日期后，页面应出现“加载往来账”主操作。为了避免日期输入过程中频繁请求、以及自动覆盖未保存数据，首期不建议每次字段变化立即请求服务端。

交互状态：

```text
未选完整条件 -> 按钮禁用/不给予加载
条件完整     -> 显示“加载往来账”
加载成功     -> 展示摘要和明细，按钮变为“重新加载”
条件发生变化 -> 标记“查询条件已变化，请重新加载”
已有明细重载 -> 提示将替换当前未保存快照
无期间流水   -> 仍展示期初/期末；期初也为零时提示暂无往来账
```

### 4.3 汇总区

加载后至少显示：

- 期初余额；
- 本期应收增加（借方）；
- 本期收款/冲减（贷方）；
- 期末余额；
- 本期凭证数量、流水行数；
- 币种；
- 数据截止时间或快照时间。

如果同一客户存在多个应收币种，应按币种拆分对账单，禁止把不同币种直接加总。

### 4.4 明细区

建议展示字段：日期、业务类型、凭证类型、凭证号、发票号/参考号、摘要、借方、贷方、滚动余额、关联订单/送货单。

每行凭证号可跳转到用户有权限读取的来源单据。表格默认只读，不允许手工修改主账金额。

## 5. 建议新增接口

在现有 `china_finance.services.customer_reconciliation_statement` 中新增独立方法，不改变旧方法：

```python
@frappe.whitelist()
def preview_customer_account_statement(company, customer, from_date, to_date):
    """按总账口径返回客户往来账预览、汇总和来源版本标识，不写数据库。"""
```

建议将通用取数抽为非白名单内部函数：

```python
def get_party_ledger_snapshot(company, party_type, party, from_date, to_date):
    """返回期初、本期流水、滚动余额、币种及快照校验信息。"""
```

接口返回结构建议新增版本，不复用当前 Delivery Note 行结构冒充账款流水：

```python
{
    "company": company,
    "party_type": "Customer",
    "party": customer,
    "from_date": from_date,
    "to_date": to_date,
    "currency": "CNY",
    "opening_balance": 1000,
    "period_debit": 5000,
    "period_credit": 3000,
    "closing_balance": 3000,
    "voucher_count": 4,
    "row_count": 6,
    "snapshot_key": "...",
    "rows": []
}
```

后续如需保存服务端快照，优先新增：

```python
@frappe.whitelist()
def refresh_customer_account_statement(statement_name):
    """仅刷新未提交的客户对账单，并重新执行权限、币种和来源校验。"""
```

不修改以下旧接口签名：

- `generate_statement(...)`；
- `preview_customer_reconciliation_statement(...)`；
- `load_customer_reconciliation_lines(...)`；
- `preview_customer_reconciliation(...)`；
- `download_customer_reconciliation_pdf(...)`；
- `download_saved_customer_reconciliation_statement(...)`。

旧接口继续服务已有调用方；新建对账单页面改为调用新增的账款预览分支。

## 6. 调用链路

### 6.1 预览链路

```text
China Reconciliation Statement 新建页
  -> 选择 company + Customer + from_date + to_date
  -> 点击“加载往来账”
  -> preview_customer_account_statement
  -> 校验角色、Customer 读取权限、公司和日期
  -> get_party_ledger_snapshot
  -> 查询起始日前 GL Entry，计算期初余额
  -> 查询期间 GL Entry，计算借方、贷方和逐行余额
  -> 批量补充来源凭证展示信息及订单/送货关联
  -> 校验币种和来源单据读取权限
  -> 返回汇总、流水和 snapshot_key
  -> 前端填入只读摘要及 China Reconciliation Line
```

### 6.2 保存链路

```text
用户保存草稿
  -> ChinaReconciliationStatement.validate
  -> 新增 Customer Ledger 分支
  -> 重新校验公司、客户、期间、币种和来源 GL Entry
  -> 校验 snapshot_key 或逐行来源标识
  -> 来源变化则拒绝保存并提示重新加载
  -> 来源未变化则保存对账快照
```

原客户 Delivery Note 校验应保留为旧快照兼容分支，通过明确的快照来源字段识别，不能直接删除。

### 6.3 导出与确认链路

```text
已保存客户往来对账单
  -> 新增 download_saved_customer_account_statement 分支
  -> 读取已保存快照，不实时重算
  -> 输出期初、发票/收款流水、借贷、滚动余额和期末余额
  -> 客户确认后上传 confirmation_file
  -> 有差异则复用 China Reconciliation Difference
  -> 提交后快照不可修改
```

现有商品型 `download_saved_customer_reconciliation_statement` 保留，避免改变旧 PDF 格式和调用方。

## 7. 建议修改文件

### 7.1 新增文件

| 文件 | 作用 |
| --- | --- |
| `china_finance/services/customer_account_statement.py` | 新增客户往来账总账取数、期初/期间/余额计算、来源补充和快照校验；也可在现有 customer_reconciliation_statement.py 新增独立分支，二选一，以避免循环依赖为准。 |
| `china_finance/tests/test_customer_account_statement.py` | 覆盖发票、收款、退款、贷项、调账、期初、多币种、权限、取消和来源变化。 |
| `client_akivision/templates/customer_account_statement_pdf.html` | 财务往来对账单模板，区别于现有订单/送货商品模板。 |
| `client_akivision/public/css/customer_account_statement_pdf.css` | 新模板打印样式。 |

### 7.2 增量修改文件

| 文件 | 建议修改代码 |
| --- | --- |
| `china_reconciliation_statement.json` | 增加快照口径/来源标识及必要的只读统计字段；为 party_type、bank_account、account、银行/采购区配置按 statement_type 显隐；不删除旧字段。 |
| `china_reconciliation_statement.js` | 新增 Customer Ledger 加载、重载、条件变更提示和汇总展示分支；保留供应商豁免、银行快照、差异登记及旧导出按钮。 |
| `china_reconciliation_statement.py` | `validate` 中新增 Customer Ledger 快照校验分支；保留现有 Delivery Note 快照校验，按来源类型分流。 |
| `china_reconciliation_line.json` | 优先复用 posting_date、voucher_type、voucher_no、account、remarks、debit、credit、balance；只新增业务分类、参考号、来源 GL Entry、关联单据等缺失字段。 |
| `china_finance/services/reconciliation.py` | 仅抽取可复用的只读总账快照函数，或让旧 `generate_statement` 调用新内部函数；白名单函数签名和返回字段保持兼容。 |
| `client_akivision/utils/customer_reconciliation_pdf.py` | 新增财务往来快照导出方法，保留现有销售订单/送货单及旧保存快照导出方法。 |
| `docs/08-reference/index.md` | 增加本方案入口。 |

### 7.3 不建议修改

- `Sales Invoice`、`Payment Entry`、`Journal Entry`、`GL Entry` 的提交和取消流程；
- 销售订单、送货单及其库存流程；
- 银行对账快照及采购齐套校验服务；
- 现有列表页 `generate_statement` 调用参数；
- 现有订单/送货单 PDF、Excel 导出接口和模板。

## 8. 数据结构兼容策略

建议在对账单头增加 Select 字段，例如 `statement_basis`：

```text
Ledger
Delivery
Bank
```

默认规则：新客户对账为 `Ledger`，历史客户单据字段为空时按 `Delivery` 兼容，供应商沿用 Ledger，银行为 Bank。该字段只增加新分支，不改 `statement_type` 的 Customer/Supplier/Bank 语义。

明细优先复用现有字段。为保证来源变化校验，可新增隐藏只读字段 `gl_entry`；为改善展示，可新增 `transaction_category`、`reference_no`、`linked_documents`。不得删除 `order_no`、`delivery_note`、商品字段和采购字段，以免破坏历史快照与旧导出。

## 9. 权限、币种和一致性

- 预览与保存都执行服务端权限校验，不能只依赖 Link 选择权限；
- 不返回用户无权读取的凭证敏感摘要；若该分录影响余额但无来源单据权限，应拒绝生成并提示联系财务管理员，不能静默排除导致余额错误；
- 总账公司币种与账户币种应明确。首期建议按账户币种生成，存在多币种时拆单；
- 预览生成 `snapshot_key`，至少覆盖 GL Entry 名称、修改时间、借贷金额、凭证状态和查询条件；
- 保存前重新校验，防止预览后发生取消、冲销或补记；
- 已提交对账单只读，后续账务变化通过新版本/替代单处理；
- SQL 或 `frappe.get_all` 必须以白名单排序字段稳定排序，滚动余额顺序建议为 `posting_date, creation, name`。

## 10. 受影响模块及预期效果

| 模块 | 影响方式 | 预期效果 |
| --- | --- | --- |
| 中国财务/对账单 | 新增客户往来账分支与摘要 | 选择客户和日期后能看到完整账款流水和余额 |
| 总账 GL Entry | 只读查询 | 成为对账金额唯一主账口径，不修改原账 |
| 销售发票 | 只读追溯 | 已提交发票/贷项按实际借贷进入明细 |
| 付款凭证 | 只读追溯 | 收款、退款及核销变化体现在客户余额中 |
| 手工凭证 | 只读追溯 | 合法的客户往来调整不会遗漏 |
| 销售订单/送货单 | 可选只读关联 | 展示业务来源，但不重复累计应收金额 |
| 对账明细子表 | 复用字段并少量新增追溯字段 | 每行可追溯、金额不可在浏览器伪造 |
| 客户对账 PDF | 新增财务往来模板分支 | 文件包含期初、流水、借贷和期末，可供客户确认 |
| 对账差异 | 复用旧模块 | 客户反馈差异时登记事项，不直接改账 |
| 供应商对账 | 保留旧分支 | 采购齐套、豁免和提交逻辑不受影响 |
| 银行对账 | 保留旧分支 | 银行账户、科目和快照逻辑不受影响 |

## 11. 异常场景

- 客户或日期未选完整：不允许加载；
- 起始日期晚于截止日期：明确提示；
- 期间无新流水但有期初余额：展示期初等于期末，不报“无数据”；
- 期初和期间均为零：提示该期间暂无客户往来账；
- 多应收账户或多币种：按明确规则汇总或要求拆分，不能直接混加；
- 来源凭证已取消：排除取消分录；预览后取消则保存时提示重载；
- 同一凭证多条 GL Entry：逐分录计算，界面可按凭证展示但不能丢失科目维度；
- 退款、贷项、冲销：按借贷方向反映，不能固定视为收款；
- 用户无来源权限：拒绝生成，避免余额与可见明细不一致；
- 已有相同公司、客户和期间的有效对账单：提示创建新版本或替代原单；
- 历史 Delivery 快照：继续按旧校验和旧导出处理。

## 12. 测试范围

至少准备以下数据组合：

1. 期初有欠款，本期一张销售发票和一次部分收款；
2. 本期全额收款，期末为零；
3. 销售退货/贷项冲减应收；
4. 客户退款恢复应收；
5. Journal Entry 调整客户余额；
6. 期间无流水但存在期初余额；
7. 预览后取消发票或收款，再保存；
8. 同客户多个应收科目、账户币种或公司币种；
9. 无权限用户、跨公司客户数据；
10. 历史 Delivery 快照、供应商对账、银行对账回归。

关键断言：

```text
期末余额 = 期初余额 + 本期借方 - 本期贷方
页面汇总 = 明细计算结果
保存快照 = 导出数据
新版本生成不修改旧版本
对账操作不创建或修改任何业务/会计凭证
```

## 13. 实施顺序

1. 增加 `statement_basis` 和最少来源追溯字段，配置三类表单显隐；
2. 抽取/新增统一的只读 `get_party_ledger_snapshot`；
3. 新增 `preview_customer_account_statement`，先完成真实总账数据预览；
4. 前端新增“加载往来账”、摘要和条件变化提示；
5. 保存校验新增 Ledger 分支，旧 Delivery 分支保留；
6. 新增客户财务往来 PDF 模板和导出接口；
7. 补自动化测试与真实站点浏览器验收；
8. 验证稳定后，再评估供应商是否复用同一预览组件。

## 14. 最终预期效果

用户新建客户对账单，选择“华润万家”和日期范围后，点击“加载往来账”，页面立即展示该客户截至起始日前的期初欠款、期间内每笔销售发票、收款、退款/贷项和调整凭证，以及每笔发生后的滚动余额。顶部汇总显示本期增加、本期减少和期末应收金额。

用户保存后得到不可静默变化的对账快照，可以导出正式客户往来对账单；客户存在异议时继续使用现有差异登记和确认附件流程。整个过程不创建、不修改销售订单、送货单、发票、付款或总账记录，旧生成和导出接口继续可用。
