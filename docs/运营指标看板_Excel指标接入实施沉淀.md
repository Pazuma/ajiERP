# 运营指标看板 Excel 指标接入实施沉淀

## 1. 实施结论

已根据 `ERP表格模板(2)(1)_各项指标汇总或看板数据.xlsx` 对运营指标看板进行接入补齐。看板仍然只保留 Excel 中的 9 个分区和原有指标，不导入 Excel 示例值，也没有新增 Excel 之外的业务指标。

页面和导出均复用 `get_kpi_dashboard_data` 的系统实时计算结果：用户选择公司、起止日期和业务员行数后，服务端查询已提交业务单据，页面显示当前指标；红框位置的“看板”下拉框仅切换当前显示的指标分区，不作为业务数据筛选条件；导出 Excel 使用相同的业务筛选条件和计算接口。

本次补齐内容：

- 回款与应收区域增加 Excel 行 14 的“应收款周转天数”，并保留平均应收天数、超 90 天逾期应收等字段。
- 应收核心管控区域保留 Excel 要求的余额、账龄金额/占比和本月回款目标完成率；移除回款总览区的重复目标完成率。
- 账龄分布增加金额和占比明细表。
- 月度生产趋势增加计划产量、实际产量、完工率明细表，图表仍展示完工率趋势。
- 近 3 年高新趋势增加高新收入占比明细字段。
- 导出总览、应收核心管控、高新趋势同步补齐对应字段。
- 筛选栏红框位置为“看板”选择框，默认“全部看板”；可切换销售整体指标、订单完成状态、回款及应收、业务员业绩等九个指标分区，只显示所选看板内容。

## 2. 数据流

```text
公司/日期/业务员行数筛选
        ↓
get_kpi_dashboard_data(filters)
        ↓
已提交 Sales Order、Delivery Note、Sales Invoice、Payment Entry、Work Order、Purchase Order、Purchase Receipt、Bin、Project 等事实单据
        ↓
operations_kpi.py 按指标公式聚合
        ↓
KPI Target、Aging Period Rule、Purchase Delay Risk Rule 提供目标和规则
        ↓
页面分区/指标卡/明细表/趋势图/TOP10
        ↓
相同结果进入 operations_kpi_export.py 生成导出文件
```

关键关联：

- 订单交付：Sales Order Item 的数量与已交数量判定整单完成、交货中和未交货。
- 回款：Payment Entry Reference 关联 Sales Invoice，按已提交 Receive 类型收款统计。
- 应收：Sales Invoice 的 outstanding_amount 和 due_date 计算余额、账龄、逾期和周转天数。
- 采购及时率：Purchase Order Item 与 Purchase Receipt Item 通过明细关联，按承诺日期和收货日期判断。
- 生产趋势：Work Order 的 planned_start_date、qty、produced_qty 按月份聚合。
- 高新趋势：Sales Order 的高新标记、金额和交易年度聚合；项目 TOP10 通过 Sales Order.project 关联 Project。

## 3. 变更文件

| 文件 | 变更 |
| --- | --- |
| `client_akivision/page/operations_kpi_dashboard/operations_kpi_dashboard.js` | 补齐 Excel 字段展示、账龄占比表、生产趋势明细、高新趋势占比；完善字段格式化 |
| `client_akivision/api/operations_kpi_export.py` | 补齐应收周转天数、月度回款目标完成率、高新趋势占比等导出字段 |
| `client_akivision/api/operations_kpi.py` | 按公司和期间计算各看板指标；页面不再通过红框位置传递业务员筛选条件 |
| `docs/playwright_kpi_dashboard_ui.mjs` | 增加字段完整性断言和趋势字段检查 |
| `docs/playwright_kpi_dashboard_result.json` | 保存 Playwright 检查结果 |
| `docs/playwright_kpi_dashboard_desktop.png` | 保存桌面端截图 |
| `docs/playwright_kpi_dashboard_mobile.png` | 保存移动端截图 |

## 4. 依赖清单

- Frappe 页面 API：`frappe.ui.make_app_page`、`frappe.call`、`frappe.set_route`、权限判断。
- 服务端模块：`operations_kpi.py`、`operations_kpi_export.py`。
- 业务 DocType：Sales Order、Sales Order Item、Delivery Note、Delivery Note Item、Sales Invoice、Payment Entry、Payment Entry Reference、Work Order、Purchase Order、Purchase Order Item、Purchase Receipt、Purchase Receipt Item、Bin、Project。
- 配置 DocType：KPI Target、Aging Period Rule、Purchase Delay Risk Rule。
- 导出依赖：Python `xlsxwriter`。
- UI 检查依赖：项目 Node `/home/cst/frappe_docker/development/erpnext.official/.tools/node/bin/node`、项目 Playwright、Chromium。

## 5. 风险点清单

| 风险 | 处理与上线要求 |
| --- | --- |
| Excel 示例数值被误当成生产事实 | 代码不读取 Excel 当前值；只读取系统已提交单据 |
| 财务收入口径与销售订单口径不一致 | 上线前确认高新收入、总营收是否改用 Sales Invoice；记录口径版本 |
| 应收周转天数与平均账龄被混用 | 当前接口字段分开返回，但两者公式仍需财务确认 |
| 多次收款或多业务员分摊重复计算 | 复测 Payment Entry 核销和 Sales Team allocated_percentage 合计 |
| 账龄规则重叠或断档 | 保存 Aging Period Rule 前校验区间连续性和唯一性 |
| 业务员未配置 Sales Team | 该单据无法归属到选择的业务员；需在销售订单/发票的 Sales Team 中维护人员和分摊比例 |
| 采购未到期订单稀释及时率 | 仅将已到评价日或已逾期订单纳入评价分母 |
| 无权限用户看到下钻入口 | 页面依据服务端权限返回值显示可点击状态；真实角色矩阵仍需复测 |
| 分母为 0 的比例显示异常 | 验收高新收入占比、研发费用占比、账龄占比和回款目标为 0 的场景 |

## 6. 本次问题记录与解决方案

| 问题 | 原因 | 解决方案 | 结果 |
| --- | --- | --- | --- |
| 页面未在回款区域显示应收周转天数 | 页面只在应收核心表展示 | 增加到回款与应收指标卡，并避免核心表重复 | 已通过字段断言 |
| 生产趋势图只展示完工率 | API 已返回计划量、实际量，但页面不可读 | 增加趋势明细表，保留完工率图表 | 已通过 Playwright |
| 高新三年趋势未展示占比 | API 已计算 high_tech_ratio，页面和导出遗漏 | 增加趋势占比列和格式化 | 已通过 Playwright |
| 账龄图表缺少占比可读值 | 图表只使用金额数据集 | 增加账龄金额/占比明细表 | 已通过 Playwright |
| 红框位置被误设为业务员 | 该位置应切换指标看板分区 | 改为“看板”下拉框，切换时仅渲染所选指标分区 | 已通过 Playwright |
| 系统无 `node` 命令 | 环境 PATH 未提供 Node | 改用项目内 Node 路径 | 检查成功 |
| 沙箱禁止临时 HTTP 监听 | Playwright 脚本需要本地服务 | 申请受限权限运行一次临时服务 | 检查成功 |
| Frappe 虚拟环境软链接断裂 | `development/frappe-bench/env/bin/python` 不可执行 | 完成本地语法检查；真实站点 SQL/权限测试列入上线复测 | 当前无法替代真实环境验证 |

## 7. Playwright 检查结果

执行命令：

```bash
/home/cst/frappe_docker/development/erpnext.official/.tools/node/bin/node \
  development/frappe-bench/apps/client_akivision/docs/playwright_kpi_dashboard_ui.mjs
```

结果：9 项全部通过。

- 九个看板分区渲染：通过
- 整单完成与至少有交货语义区分：通过
- 应收周转天数、账龄占比、生产计划/实际产量、高新趋势占比：通过
- 下钻权限保护：通过
- Top10/全部切换：通过
- 切换“看板”后仅显示对应指标分区，API 不携带 `sales_person`：通过
- Excel 导出入口及当前筛选条件：通过
- 390px 移动端无横向溢出，图表和分区完整：通过
- 日期逆序错误提示和 Retry：通过

检查使用模拟 `frappe.call` 数据，不能替代真实登录站点、MariaDB SQL、用户权限矩阵和真实业务数据核对。结果详情保存在 `playwright_kpi_dashboard_result.json`。

## 8. 需要复测的场景

1. 一个订单全部交货、部分交货、完全未交货时，五类订单状态是否与 Excel 定义一致。
2. 一张发票分多次收款、跨期间收款、重复核销时，已收和应收是否不重复。
3. 账龄 30/31/60/61/90/91/180/181 天边界是否落入正确区间。
4. 无目标、目标为 0、分母为 0、日期逆序时，页面和导出是否显示明确状态。
5. 多业务员单据按分摊比例统计，个人汇总是否等于事实金额。
6. 采购订单未到承诺日期、已逾期未收齐、部分收货、全部收货时，及时率和延迟天数是否正确。
7. 高新收入、总营收、研发费用按财务确认的收入来源复核年度趋势。
8. 无看板角色、无报表权限、无 DocType 读取权限时，API 拒绝访问且页面不显示下钻入口。
9. 真实公司、空数据公司、大数据量公司分别检查查询耗时、页面加载和导出耗时。
10. 页面指标与导出 Excel 逐项比对，确认字段、单位、目标、达成率和状态一致。
11. 分别选择“销售整体指标”“订单完成状态”“全部看板”，确认页面仅显示对应分区或恢复全部九个分区，且接口不携带 `sales_person`。

## 9. 验收结论

前端字段、导出字段、模拟数据交互和响应式布局已完成验证；后端 Python/前端 JavaScript 语法检查通过。真实站点数据库、财务口径和权限矩阵尚未在当前环境执行，必须完成第 8 节复测后再正式上线。
