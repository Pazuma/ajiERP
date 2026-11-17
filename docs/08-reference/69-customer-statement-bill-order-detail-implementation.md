---
title: 客户对账账单订单明细实施记录
---

# 客户对账账单订单明细实施记录

## 实现内容

按 67 号方案，在现有客户 Ledger 预览接口上新增返回字段，保留原有入参、`rows`、余额字段和 Delivery 预览分支：

- `opening_documents`：起始日前仍未结清的已提交销售发票，包含订单、送货、原始金额、已结和期初未结金额；
- `order_billing_rows`：期间销售订单明细，汇总订单数量、送货数量、开票数量、账单、收款和未结金额；
- 本期 GL 流水补充销售发票、收款单及多订单/送货关联；
- 快照标识覆盖 GL、期初账单和订单关联结果。

## 修改文件

- `china_finance/services/customer_reconciliation_statement.py`
- `china_reconciliation_statement.js`
- `china_reconciliation_statement.py`
- `china_reconciliation_statement.json`
- `china_reconciliation_opening_document.json`
- `china_reconciliation_order_billing_line.json`
- `china_finance/setup/install.py`

## 调用链路

```text
选择公司/客户/起止日期
  -> preview_customer_account_statement
  -> GL Entry 客户流水
  -> Sales Invoice + Payment Entry Reference
  -> Sales Order Item + Delivery Note Item
  -> 返回 opening_documents / order_billing_rows / rows
  -> 页面填充三张明细表
```

## 预期效果

期初有余额但本期无流水时，可以在“期初未结账单”中看到具体发票及其订单、送货和未结金额；期间有业务时，“订单账单明细”显示产品、数量、送货、发票、已收和未结金额；“对账明细”继续显示 GL 借贷和滚动余额。跨公司单据不会被查询，订单和送货金额不重复计入财务余额。

## 校验

- Python 模块编译通过；
- 新增及修改 DocType JSON 解析通过；
- `git diff --check` 通过。
