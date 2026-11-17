---
title: 对账单往来单位选择化改造实施说明
---

# 对账单往来单位选择化改造实施说明

## 目标与原则

将“中国财务 -> 对账单 -> 新建对账单”的“往来单位”改为可搜索选择，并根据对账类型限定数据来源：客户对账选择 Customer，供应商对账选择 Supplier，银行对账不要求往来单位。

本次采用小增量改造：保留字段名 `party`、字段类型 Dynamic Link、服务端参数和已保存数据，不修改既有生成、加载、导出接口；只补充前端联动分支和元数据约束。

## 修改文件与代码

| 文件 | 修改内容 |
| --- | --- |
| `china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.json` | 对账类型默认值设为 Customer；往来单位在 Customer/Supplier 类型下动态必填。字段仍为 Dynamic Link，继续通过 `party_type` 指向主数据。 |
| `china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js` | 新增统一的 `set_party_type` 分支，在新建页面加载和对账类型变化时同步 Dynamic Link 目标；类型切换时清除原往来单位，防止把客户值带入供应商或银行对账。已有单据刷新时不写值。 |
| `docs/08-reference/64-reconciliation-party-selection-implementation.md` | 记录本次改造、调用链路、影响范围、兼容策略和验收效果。 |

核心映射如下：

| 对账类型 | `party_type` | 往来单位选择来源 | 是否必填 |
| --- | --- | --- | --- |
| Customer | Customer | Customer | 是 |
| Supplier | Supplier | Supplier | 是 |
| Bank | 空 | 不使用 | 否 |

## 调用链路

新建表单选择链路：

```text
打开 China Reconciliation Statement
  -> 新建表单 onload
  -> set_party_type(statement_type)
  -> party_type 写入 Customer 或 Supplier
  -> party Dynamic Link 读取 party_type
  -> Frappe Link 搜索对应客户或供应商主数据
  -> 保存
  -> ChinaReconciliationStatement.validate
  -> 服务端再次按 statement_type 固化 party_type 并校验 party
```

类型切换链路：

```text
statement_type 变化
  -> set_party_type(frm, true)
  -> 更新 party_type
  -> 清空旧 party
  -> 用户从新类型对应的主数据中重新选择
```

客户对账关联链路保持不变：

```text
选择 Customer
  -> 加载对账数据
  -> preview_customer_reconciliation_statement(company, customer=party, from_date, to_date)
  -> 查询并返回客户送货单明细
  -> 保存时校验 Delivery Note.company/customer/date/currency
  -> 已保存单据可调用原有 PDF 导出接口
```

列表页“生成对账单”原链路也保持不变：弹窗仍分别选择 Customer/Supplier，并以旧参数 `party` 调用 `china_finance.services.reconciliation.generate_statement`。

## 兼容性与受影响模块

| 模块 | 影响 | 兼容说明 |
| --- | --- | --- |
| 对账单新建表单 | 往来单位变为明确的主数据搜索选择 | 保留 `party` 和 Dynamic Link，不迁移数据库字段 |
| 客户对账 | 默认即可选择客户；加载明细逻辑不变 | `preview_customer_reconciliation_statement` 接口和参数不变 |
| 供应商对账 | 切换类型后选择范围自动改为 Supplier | 采购齐套校验、豁免和提交逻辑不变 |
| 银行对账 | 不再残留客户或供应商值 | 银行账户、科目和快照逻辑不变 |
| 对账单列表生成 | 无代码改动 | 继续向旧接口传递 `party` |
| PDF 导出 | 无代码改动 | 已保存客户对账单导出接口不变 |
| 已有对账单数据 | 无数据迁移 | 服务端原有 `validate` 仍会按对账类型校正 `party_type` |

明确不受影响：销售订单、送货单、采购发票、付款、总账、报表的数据结构及其旧接口。

## 预期效果

1. 新建对账单默认显示“客户”，往来单位输入框可直接搜索和选择已有客户。
2. 对账类型切换到“供应商”后，往来单位只搜索 Supplier；原客户值自动清空，避免跨类型误用。
3. 切换到“银行”后清除往来类型和往来单位，继续使用银行账户及银行科目流程。
4. Customer/Supplier 未选择往来单位时，表单显示必填约束；绕过前端时服务端仍拒绝保存。
5. 客户“加载对账数据”、供应商采购齐套校验、银行快照、差异登记和 PDF 导出行为保持原样。

## 验收建议

1. 新建客户对账单，确认往来单位下拉只出现客户并可按名称搜索。
2. 选择客户后切换供应商，确认原值清空且选择结果只包含供应商。
3. 再切换银行，确认往来单位不再必填，并可完成原银行对账流程。
4. 分别保存客户和供应商对账单，确认 `party_type` 为 Customer/Supplier，`party` 为所选主数据编号。
5. 回归客户加载明细及 PDF 导出、供应商齐套校验、列表页生成对账单。
