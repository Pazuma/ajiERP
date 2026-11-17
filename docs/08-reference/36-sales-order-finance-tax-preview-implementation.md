# 销售订单税费与预计记账预览实施沉淀

## 1. 实施结果

已在 `china_finance` 自定义应用中新增销售订单“财务审核”只读预览。该功能在订单表单刷新时汇总税费、金额、结算模式、关联销售发票和中国会计凭证，帮助财务人员判断订单金额口径及后续记账状态。

本次没有修改销售订单、销售发票、送货单、税费模板、总账分录或凭证生成行为；预览接口不写入任何业务数据。

## 2. 已修改文件

| 文件 | 实际改动 |
|---|---|
| `development/frappe-bench/apps/china_finance/china_finance/services/sales_order_finance_preview.py` | 新增只读预览服务与 `get_sales_order_finance_preview` 白名单接口。读取订单、税费行、关联已提交销售发票及其中国会计凭证，返回财务摘要、税费明细、预计记账行和状态。 |
| `development/frappe-bench/apps/china_finance/china_finance/public/js/sales_order_finance_preview.js` | 新增 Sales Order 表单脚本；将“财务审核”紧跟原生税费与合计区块之后、销售团队之前渲染。未保存订单仅提示保存后查看，已保存订单调用预览接口。 |
| `development/frappe-bench/apps/china_finance/china_finance/public/css/sales_order_finance_preview.css` | 新增局部样式，覆盖财务摘要、提示、两张预览表和窄屏单列布局。 |
| `development/frappe-bench/apps/china_finance/china_finance/hooks.py` | 将 Sales Order 的 `doctype_js` 改为数组，在保留 `sales_order_settlement.js` 的同时追加预览脚本；增加局部 CSS 资源。 |
| `development/frappe-bench/apps/china_finance/china_finance/tests/test_sales_order_finance_preview.py` | 新增三项纯逻辑测试：直接确认应收的借贷平衡、对账结算不预览应收分录、正式凭证状态优先于发票状态。 |

## 3. 功能口径

### 财务摘要

- 未税销售额读取 `Sales Order.net_total`；
- 销项税额读取 `Sales Order.total_taxes_and_charges`；
- 含税订单额读取 `Sales Order.grand_total`；
- 结算模式读取 `custom_china_settlement_mode`；
- 对账结算订单额外读取 `custom_china_settled_amount`；
- 校验 `未税销售额 + 总税费 = 含税订单额`，仅提示差额，不改变既有保存和提交校验。

### 税费与预计记账

- 税费行从原生 `Sales Taxes and Charges` 子表派生：描述、税率、计税基数、税额、`account_head`、借贷方向；
- 直接确认应收模式预览“借应收账款、贷收入、贷税费”；
- 对账结算后确认应收模式不展示应收分录，并说明须完成客户确认和销售结算；
- 缺少应收、收入或税费科目时显示“待财务配置”，不猜测、不创建科目。

### 正式状态

- 通过 `Sales Invoice Item.sales_order` 查询已提交销售发票；
- 通过 `China Accounting Voucher.source_doctype/source_name` 查询发票对应的已提交凭证；
- 状态优先级为：已生成中国会计凭证 > 已生成销售发票 > 待客户确认/销售结算 > 预计记账；
- 页面提供已关联发票与凭证的跳转链接，订单本身不被标记为正式凭证。

## 4. 调用链路

```text
Sales Order 表单刷新
  -> sales_order_finance_preview.js
  -> 定位原生 taxes 字段所属税费区块，在其后插入只读预览容器
  -> 已保存订单调用 get_sales_order_finance_preview
  -> 校验 Sales Order read 权限
  -> 只读查询订单、税费行、Sales Invoice、China Accounting Voucher
  -> 构建摘要、税费明细、预计记账行和状态 JSON
  -> 浏览器渲染“财务审核”区块

Sales Order -> Delivery Note -> Sales Invoice / China Sales Settlement
  -> 既有 china_finance 自动开票、结算与凭证链路保持不变
  -> 用户下次打开订单时，预览只读更新关联状态
```

服务中未使用 `insert`、`save`、`db_set`、`make_gl_entries`、自动开票或 `create_voucher_from_source`。

## 5. 兼容与影响

- `sales_order_settlement.js` 保持原有草稿/提交状态下的结算模式可编辑性逻辑；
- `sales_settlement.py`、`auto_invoice.py`、`voucher.py` 未修改；
- ERPNext 原生税费计算和 `Sales Taxes and Charges` 子表未修改；
- Excel、CRM、API 创建销售订单不需要新增参数；
- 对现有已提交订单不做回填或写入；
- 新接口遵循 Sales Order 读取权限，不能越权读取订单金额、发票或凭证关联。

## 6. 验证记录

- 已通过 `python3 -m compileall` 对新增 Python 服务和测试文件进行语法编译；
- 已通过 `git diff --check` 检查 `china_finance` 子应用的补丁格式；
- 当前工作区未提供可执行的 `development/frappe-bench/env/bin/python`、`bench` 或 `node`，因此未能运行 Frappe 单测和前端 `node --check`；
- 部署前应在完整 Bench 环境执行：

```bash
bench --site <site> run-tests --app china_finance --module china_finance.tests.test_sales_order_finance_preview
bench --site <site> migrate
bench --site <site> clear-cache
bench build --app china_finance
```

## 7. 部署后验收

1. 含 13% 税率的直接确认应收订单显示未税、税额、含税金额，预计分录借贷平衡。
2. 对账结算订单显示待确认提示且不显示提前确认应收的分录。
3. 销售发票提交后，订单显示发票链接；凭证生成后，状态升级并显示凭证链接。
4. 无税费、免税、多收入科目、缺失科目配置时页面可正常加载，且不产生伪造分录。
5. 保存、提交、取消销售订单以及创建送货单、发票、结算单的既有行为无回归。
