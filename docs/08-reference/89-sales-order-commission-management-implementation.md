# 销售订单提成管理实施记录

日期：2026-10-23。

状态：第一期代码已实现并在 `aki_test.localhost` 定向同步验证。此记录覆盖管理台账，不表示真实银行付款、工资或总账已经集成。

## 实现范围

- 新增 `Sales Commission Sheet` 与人员明细，支持订单未税额、已开票未税额、已核实回款、财务批准毛利、手工基数五种依据；总监逐人设比例、确认及创建修订版本。
- 新增回款分配台账。首期可用人工核实凭据，也能校验 Payment Entry 的客户、公司、方向、引用及金额；按有效发票进行未税折算。退货通过 `is_return` 识别并按退款方向登记。
- 新增发放/追回台账。发放前重新校验来源及可发额度，追回、冲销需凭据和附件；确认操作由服务端 POST 方法执行，拒绝重复业务凭据。
- 新增汇总与“我的提成”报表。普通业务人员无原始台账读取权限，个人报表按当前用户对应的 Sales Person 投影白名单字段。
- “Selling”侧边栏新增“提成管理”入口。统一报表按服务端当前角色分流：销售人员只看到本人结果，销售总监/提成财务看到授权范围内的管理数据；总监有“维护提成单”入口。
- 新增中文角色“销售总监”，与兼容角色 `Sales Commission Manager` 共享同一管理权限。管理员在“角色权限管理”中给相应用户分配“销售总监”；系统不自动授予。
- 销售订单只追加入口，不更改既有订单、发票、结算、收款、毛利核算接口或会计分录。
- 订单取消后可由总监显式作废当前提成版本，保留历史计提和支付记录；作废时清除有效版本键。

## 代码及文件

功能主体位于 `development/frappe-bench/apps/china_finance/china_finance/`：

- `services/sales_commission.py`：草稿、五种依据协调、确认、修订、毛利批准、来源有效性与取消订单作废。
- `services/sales_commission_sources.py`：订单/发票/回款/毛利/手工来源适配及快照。
- `services/sales_commission_payments.py`：回款额度校验、台账幂等、发放资格、追回与冲销。
- `services/sales_commission_permissions.py`、`services/sales_commission_reports.py`：角色授权、订单范围、个人白名单和汇总口径。
- `doctype/sales_commission_sheet/`、`sales_commission_sheet_item/`、`sales_commission_receipt_allocation/`、`sales_commission_disbursement/`：新增 DocType、表单控制和审计字段。
- `report/sales_commission_summary/`、`report/my_sales_commission/`：管理汇总和个人查询。
- `report/sales_commission_management/`：Selling 侧边栏的统一入口，服务端按角色投影管理结果或个人结果。
- `public/js/sales_order_commission.js`、`setup/sales_commission.py`、`tests/test_sales_commission.py`。
- `hooks.py`、`setup/install.py`：只追加新表单入口、权限/query hook 和幂等初始化。

## 调用链路

```text
Sales Order 按钮
  -> get_commission_context / create_commission_draft
  -> Sales Commission Sheet 服务端校验和来源快照
  -> preview_commission
  -> confirm_commission（锁订单、校验时间戳与当前版本、固化）
  -> create_commission_revision（保留旧版并按版本差额计提）

财务回款分配
  -> confirm_receipt_allocation（锁公司及订单/来源，校验累计凭据和发票额度）

财务发放登记
  -> get_release_context
  -> confirm_disbursement（校验有效版本、累计已发、可发额度及重复凭据）

报表
  -> 新权限服务限定角色/订单范围
  -> 管理报表读取有效版本和支付台账；个人报表只返回本人行
```

## 预期效果及边界

销售总监可以按订单维护不同业务人员的比例并看到版本差额；财务可登记并审计实际回款分配、发放和追回；业务人员仅能看到自身结果。来源变化会冻结新发放并要求复核，不会自动覆盖已确认比例。管理台账不会自动创建银行付款、工资、会计分录，也不改变原生销售团队佣金。第一期回款通过独立分配记录确认，预收款不会被自动猜测订单归属。

当前业务角色创建不自动赋给用户，须由管理员按岗位分配 `销售总监`（兼容 `Sales Commission Manager`）或 `Sales Commission Finance`。毛利依据沿用现有财务单据权限，并须显式财务批准；普通业务人员不返回毛利基数和提成比例。

## 验证

- `bench --site aki_test.localhost run-tests --app china_finance --module china_finance.tests.test_sales_commission --test-category all --skip-before-tests`：17 项通过（包括继承的财务核算回归测试）。
- 定向 `reload-doc` 四个 DocType 和两个报表、执行 `ensure_schema`、`clear-cache`：完成。
- 新增统一报表及销售总监角色已同步；`Selling` 侧边栏添加“提成管理”链接。
- `docs/playwright_sales_commission.mjs`：三个单据列表/新建表单以及报表筛选 smoke 通过。
- 新增/修改 Python 编译检查和主表/回款/发放 JSON 语法检查通过。
- 未运行全站 `bench migrate`：该站已有与本功能无关的公司映射配置问题（“西安分公司”缺失），故采用定向 schema reload，避免把无关配置修复并入本次。

## 后续独立增量

Payment Entry 自动分配需适配真实收款与多发票分配数据；来源变化事件通知、历史期末快照，以及正式付款/工资集成仍需单独设计、测试和上线。投入正式使用前，应先在目标站点备份、定向同步 DocType、分配岗位角色，并由财务核对 Payment Entry 与退款的真实数据口径。
