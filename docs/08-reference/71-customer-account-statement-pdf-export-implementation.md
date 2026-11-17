---
title: 客户往来对账单 PDF 导出实施记录
---

# 客户往来对账单 PDF 导出实施记录

## 已完成

- 已保存客户 Ledger 对账单继续使用原有“导出客户对账单 PDF”入口；
- PDF 从已保存快照读取公司、客户、期间、币种、版本、财务流水、订单账单和期初未结账单；
- 增加期初余额、本期借方、本期贷方、所选期间余额、截止日期余额；
- 增加订单总金额、已开票金额、已结金额、未结金额和未开票金额；
- 增加订单/账单、期初未结账单和财务流水三类明细；
- 指定 PNG 图标以内嵌 Base64 方式放在 PDF 顶部右侧；
- 列表页生成客户 Ledger 对账单时同步保存订单账单及期初账单子表，并补齐动态链接的往来类型；
- 历史 Delivery 类型客户对账单仍走原商品/送货模板。

## 修改文件

- `client_akivision/utils/customer_reconciliation_pdf.py`
- `client_akivision/templates/customer_account_statement_pdf.html`
- `client_akivision/public/images/customer_account_statement_logo.png`
- `china_finance/services/reconciliation.py`
- `docs/playwright_customer_account_statement_pdf.mjs`

## 验证记录

- Python 模块编译通过；
- 使用 ASC、阿基视觉（东莞）、2026-08-01 至 2026-09-09 样例数据生成草稿 `CNR-2026-00001`；
- Playwright 登录站点、打开表单、确认“导出客户对账单 PDF”按钮并成功下载 PDF；
- 下载文件为 PDF，两页，大小约 64 KB；
- 页面中可见“订单账单明细”；
- 浏览器记录的 `custom_filters` 404 和 `Cannot read properties of null (reading 'join')` 属于站点已有页面资源/脚本问题，未阻断表单打开和 PDF 下载。

## 结果文件

- [Playwright 验证结果](../china-finance-test-evidence/customer-account-statement-playwright.json)
- [导出的 PDF](../china-finance-test-evidence/customer-account-statement.pdf)
- [对账单页面截图](../china-finance-test-evidence/customer-account-statement-form.png)
