---
title: 客户往来对账单完整账款流水实施记录
---

# 客户往来对账单完整账款流水实施记录

## 实现功能

客户对账单新增 Ledger 口径。用户选择公司、客户、起始日期和截止日期后，点击“加载往来账”，系统读取该客户已记账且未取消的 GL Entry，显示期初余额、本期借方、本期贷方、期末余额，以及发票、收款/退款、调整凭证等期间流水和逐行滚动余额。

保存时服务端重新取数并校验快照标识、来源 GL Entry、凭证、科目、借贷和余额。预览后账务发生变化，系统要求重新加载，浏览器不能自行修改账款金额。

已保存 Ledger 客户对账单继续使用原导出按钮和接口 URL，但接口内部新增分支，输出独立的“客户往来对账单”PDF；历史 Delivery 快照仍使用原商品/送货模板。

## 修改文件

| 文件 | 实现内容 |
| --- | --- |
| `china_finance/services/customer_reconciliation_statement.py` | 新增 `get_customer_ledger_snapshot` 和 `preview_customer_account_statement`；计算期初、期间借贷、期末及快照哈希。旧 Delivery 接口保留。 |
| `china_finance/services/reconciliation.py` | Customer 分支内部复用统一 Ledger 快照，保持 `generate_statement` 的参数和返回结构不变；Supplier/Bank 分支不变。 |
| `china_reconciliation_statement.json` | 新增 `statement_basis`、`snapshot_key`；按类型控制银行、采购字段显隐；客户默认 Ledger。 |
| `china_reconciliation_statement.js` | 新增“加载/重新加载往来账”、汇总回填和查询条件变化提示；保留原差异、供应商及银行按钮。 |
| `china_reconciliation_statement.py` | 新增 Ledger 保存校验分支；历史 Delivery 校验分支保留。 |
| `china_reconciliation_line.json` | 新增 `transaction_category` 和隐藏的 `gl_entry` 来源字段，复用现有凭证、科目、借贷和余额字段。 |
| `client_akivision/utils/customer_reconciliation_pdf.py` | 原保存导出接口新增 Ledger 分支，旧接口签名不变。 |
| `client_akivision/templates/customer_account_statement_pdf.html` | 新增财务往来 PDF，展示期初、期间流水、借贷、滚动余额及期末。 |

部署修正：实际实现文件位于模块目录时，另在应用顶层 `china_finance/services/customer_reconciliation_statement.py` 增加公共兼容入口，并为模块服务目录补充 `__init__.py`。Frappe 白名单路径 `china_finance.services.customer_reconciliation_statement.*` 因此可正常解析，现有前端及内部调用路径保持不变。

## 调用链路

```text
新建客户对账单
  -> 选择公司、Customer、日期
  -> china_reconciliation_statement.js
  -> preview_customer_account_statement
  -> get_customer_ledger_snapshot
  -> GL Entry（company + Customer + party + date + is_cancelled=0）
  -> 计算期初/借方/贷方/滚动余额/期末
  -> 前端填充汇总和 China Reconciliation Line
  -> 保存时 _validate_customer_ledger_snapshot 重新取数校验
  -> 保存不可静默变化的快照
  -> 原 PDF 按钮/接口按 statement_basis 分流
  -> customer_account_statement_pdf.html
```

## 兼容与影响

- `generate_statement` 参数和返回值未修改；
- Delivery Note 预览、加载和旧 PDF 接口未删除；
- 历史客户 Delivery 快照继续走旧校验及模板；
- 供应商采购齐套/豁免、银行快照和差异登记逻辑未修改；
- 销售发票、付款、手工凭证、总账、订单和送货单均只读，不创建或修改来源业务数据；
- 期间无流水但有期初余额时允许保存和导出，期末余额等于期初余额。

## 预期效果

选择客户和日期并加载后，页面展示真实财务往来，而不是仅展示送货商品。销售发票、收款、退款/贷项和手工调整均按实际总账借贷方向进入流水，顶部金额满足：

```text
期末余额 = 期初余额 + 本期借方 - 本期贷方
```

客户对账页面不再显示技术字段“往来类型”，客户场景不再显示银行账户和银行科目。保存后的 PDF 与快照一致，来源账务变化需要重新加载并生成新快照。
