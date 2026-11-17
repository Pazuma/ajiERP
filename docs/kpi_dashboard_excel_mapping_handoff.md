# 《ERP表格模板(2)(1)_各项指标汇总或看板数据.xlsx》看板字段沉淀方案

## 1. 文档目的

本文档针对：

`/home/cst/frappe_docker/ERP表格模板(2)(1)_各项指标汇总或看板数据.xlsx`

目标是把该 Excel 工作表中的指标拆分为 Deeplinkerp“运营指标看板”中的指标卡、目标配置、规则配置、趋势图、TOP10 下钻表和异常核对入口。当前阶段先完成表单结构和指标口径配置，Excel 中的数值只作为假数据/验收样本，不写入业务单据、看板快照或目标值。

看板中的数值属于业务单据计算结果，不应把 Excel 中的示例值直接导入成可编辑数据。系统应从已提交的销售订单、送货单、发票、收付款、采购订单、收货、工单、库存账、项目和费用单据重新计算；Excel 数值只用于历史核对、验收样本和口径确认。任何演示数据都必须标记为“样例”，不得创建客户 A、供应商 A、项目 A、订单或金额等正式业务记录。

## 2. Excel 内容盘点

### 2.1 文件结构

| 项目 | 结果 |
| --- | --- |
| 工作簿 | `ERP表格模板(2)(1)_各项指标汇总或看板数据.xlsx` |
| 工作表 | `各项指标汇总或看板数据` |
| 有效区域 | A1:I101 |
| 内容类型 | 指标卡、指标值、目标值、达成率、预警/合规状态、趋势数据、TOP10 明细、指标说明 |
| 数据性质 | 汇总快照/看板样例，不是客户、订单、库存等基础业务明细 |
| 建议导入方式 | 不作为普通 Data Import 表；通过系统业务单据和 KPI 目标/规则表单生成 |

### 2.2 工作表分区

| Excel 行区间 | 分区 | 主要内容 | 系统去向 |
| --- | --- | --- | --- |
| 1-3 | 销售整体指标 | 总订单数、总销售额、高新收入总额、高新收入占比 | 看板指标卡 + 销售订单/高新收入下钻 |
| 5-7 | 订单完成状态 | 整单已完成、整单未完成、已交货、交货中、未交货 | 看板指标卡 + 销售订单列表 |
| 10-15 | 回款&应收款指标 | 已收、应收、结清/未结清、平均应收天数、超 90 天、周转天数 | 应收指标卡 + 应收账龄报表 + 收款报表 |
| 18-20 | 业务员业绩 | 送货条数、送货金额、个人已回款、个人应收、交付率、回款率 | 业务员明细表 + 送货/收款/应收下钻 |
| 24-26 | 同比指标 | 上年同期销售额、销售同比、应收同比 | 同比指标卡 + 年度/期间趋势 |
| 29-31 | 对账预警 | 未完成订单、状态不一致条数 | 核对指标卡 + 异常订单列表 |
| 36-55 | 应收款核心管控 | 账龄金额、占比、预警状态、逾期客户 TOP10 | 应收核心指标表 + 账龄分布 + 客户 TOP10 |
| 59-79 | 生产采购运营 | 生产完工率、采购及时率、库存金额、安全库存预警、在途、超耗率、生产趋势、延迟供应商 TOP10 | 运营核心指标表 + 趋势图 + 采购延迟报表 |
| 81-101 | 高新收入合规 | 高新收入、总营收、占比、研发项目数、研发费用、合规状态、3 年趋势、项目 TOP10 | 高新合规指标表 + 趋势图 + 项目 TOP10 |

## 3. 系统表单与页面拆分

### 3.1 不把整张 Excel 复制成一个表单

Excel 是横向展示格式，不能直接对应一个“看板数据”可编辑 DocType。建议拆成以下对象：

| 对象 | 类型 | 是否新增 | 用途 | 是否允许录入汇总数值 |
| --- | --- | --- | --- | --- |
| 运营指标看板 | Page `operations-kpi-dashboard` | 已存在 | 展示筛选后的实时指标、目标、达成率、状态、趋势和 TOP10 | 否，只读 |
| KPI Target | DocType | 已存在 | 维护公司、指标编码、周期、目标值、评价方向、预警/危险阈值 | 只允许维护目标和阈值 |
| Aging Period Rule | DocType | 已存在 | 维护应收账龄区间和风险等级 | 允许维护规则，不录入应收余额 |
| Purchase Delay Risk Rule | DocType | 已存在 | 维护采购延迟区间和风险等级 | 允许维护规则，不录入延迟汇总 |
| KPI Metric Definition | DocType | 本轮已新增 | 维护指标名称、公式、单位、来源、负责人、是否合规指标、下钻入口 | 不存当前计算结果 |
| KPI Snapshot | 建议按需新增 DocType/报表 | 后续可选 | 留存历史结账快照、口径版本和导入核对值 | 仅允许受控的历史快照，不参与实时计算 |
| 下钻报表 | Report | 多数已存在 | 查看产生指标的订单、发票、收款、库存、工单、供应商、项目明细 | 只读 |

### 3.2 现有看板入口

当前应用已存在：

- 页面：`operations-kpi-dashboard`（运营指标看板）。
- 设置入口：`KPI Target`、`Aging Period Rule`、`Purchase Delay Risk Rule`。
- 销售报表：`Sales Order List`、`Delivery List`、`High-tech Revenue Analysis`、`Receivable Aging Analysis`。
- 采购/库存报表：`Purchase Delay Analysis`、`Purchase List`、`Realtime Inventory`、`Safety Stock Status`、`Summary Calculation`。
- 收付款报表：`Receipt Record`、`Purchase Payment Record`。

因此本方案优先扩展现有看板和指标定义，不新建重复的“看板数据清单”表。

## 4. Excel 字段到看板表单映射

### 4.1 销售整体指标（Excel 1-3 行）

| Excel 指标 | 看板展示 | 数据来源 | 计算口径 | 目标/状态 |
| --- | --- | --- | --- | --- |
| 总订单数 | 销售整体指标卡 | 已提交 Sales Order | 按公司、订单日期范围统计订单数 | 可选 KPI Target；无目标显示未设置 |
| 总销售额 | 销售整体指标卡，重点卡 | Sales Order | 已提交订单 `grand_total` 汇总；需确认是否含税 | 可配置年度/月度目标 |
| 高新收入总额 | 销售整体指标卡、高新合规卡 | Sales Order | `custom_is_high_tech_revenue=1` 的订单金额汇总 | 年度目标；合规/未达标 |
| 高新收入占比 | 销售整体指标卡、高新合规卡 | Sales Order | 高新收入总额 / 总销售额；分母为 0 时显示 0 或无数据 | 年度目标；合规/不合规 |
| 说明文本 | 指标定义/帮助提示 | KPI Metric Definition | 保存公式、过滤条件和统计口径 | 不作为数值字段导入 |

源表样例值为：总订单数 260、总销售额 100000、高新收入 0、高新占比 0。它们只能作为验收样本，不能直接写入看板。

### 4.2 订单完成状态（Excel 5-7 行）

| Excel 指标 | 看板展示 | 数据来源 | 建议计算口径 | 下钻 |
| --- | --- | --- | --- | --- |
| 整单已完成订单数 | 指标卡 | Sales Order + Sales Order Item | 同一订单下所有明细 `delivered_qty >= qty` | Sales Order List，状态=已交货 |
| 整单未完成订单数 | 指标卡 | Sales Order | 订单明细中至少一行未完成 | Sales Order List，未完成 |
| 已交货订单数 | 指标卡 | Sales Order + Delivery Note | 至少一行已交货；与“整单已完成”严格区分 | Sales Order List，存在送货 |
| 交货中订单数 | 指标卡 | Sales Order Item | 至少一行已交货且仍有未交数量 | Sales Order List，状态=交货中 |
| 未交货订单数 | 指标卡 | Sales Order Item | 所有明细 `delivered_qty=0` | Sales Order List，状态=未交货 |
| 订单状态说明 | 指标定义 | Sales Order + Delivery Note | 客户订单号、内部型号/产品型号用于关联；最终以明细交货量判定 | 只读说明 |

注意：当前看板 API 中 `delivered_orders` 与 `completed_orders` 的计算存在同义风险，实施时必须拆成“至少有交货”和“全部完成”两个独立指标，避免出现 Excel 中 237 与 126 两个数字却在系统显示相同的情况。

### 4.3 回款与应收指标（Excel 10-15 行）

| Excel 指标 | 看板/报表位置 | 数据来源 | 计算口径 |
| --- | --- | --- | --- |
| 已收款总额 | 回款指标卡 | Payment Entry + Payment Entry Reference | 已提交 Receive 类型收款、按核销金额汇总 |
| 应收款总额 | 应收指标卡 | Sales Invoice | 已提交销售发票未核销余额；需明确是当前余额还是期间发生额 |
| 已结清单据数 | 应收核心指标 | Sales Invoice | `outstanding_amount=0` 的发票数量 |
| 未结清单据数 | 应收核心指标 | Sales Invoice | `outstanding_amount>0` 的发票数量 |
| 未结清单据平均应收天数 | 应收核心指标 | Sales Invoice | 未结清发票余额加权账龄，不能简单平均发票天数 |
| 超 90 天逾期应收金额 | 应收核心指标 | Sales Invoice | 账龄大于 90 天的未结清余额汇总 |
| 应收款周转天数 | 应收核心指标 | Sales Invoice + Payment Entry | 需确认采用平均应收余额/销售额还是现有加权账龄近似口径 |
| 回款来源说明 | 指标定义 | Delivery/Invoice/Payment | Excel 说明“回款清单来源为已送货订单”需在系统中明确是送货、发票还是收款核销作为事实来源 |

源表样例值包括已收款 100000、应收款 100000、已结清 334、未结清 136、周转天数 22。样例数与订单数不必相等，导入时不能做强制回填。

### 4.4 业务员业绩（Excel 18-20 行）

| Excel 指标 | 展示形式 | 数据来源 | 计算口径 |
| --- | --- | --- | --- |
| 送货条数 | 业务员明细表/汇总卡 | Delivery Note + Sales Team | 按送货单去重、按销售团队分摊；明确一单多人时是否按比例计数 |
| 送货业绩金额 | 业务员明细表 | Delivery Note Item + Sales Team | 送货明细金额按销售团队分摊 |
| 个人已回款 | 业务员明细表 | Sales Invoice + Payment Entry + Sales Team | 收款核销金额按发票销售团队比例分摊 |
| 个人应收款 | 业务员明细表 | Sales Invoice + Sales Team | 发票未收余额按团队比例分摊 |
| 交付率 | 业务员明细表 | 送货金额 / 订单金额 | 分母为个人订单金额；无订单金额时显示无数据 |
| 回款率 | 业务员明细表 | 个人已回款 /（个人已回款 + 个人应收款） | 必须防止分母、期间和销售团队分配导致超过 100% |

源表样例为送货 323 条、送货金额 3931524、个人已回款 8434843.1、个人应收 1837569、交付率 72.7477%、回款率 214.5438%。回款率超过 100% 是明显的口径/数据质量风险，不能照搬到看板；上线前需核对收款重复计入、期间不一致或销售团队分摊逻辑。

### 4.5 同比指标（Excel 24-26 行）

| Excel 指标 | 展示 | 数据来源 | 口径 |
| --- | --- | --- | --- |
| 上年同期销售额 | 同比卡 | Sales Order | 当前筛选期间向前平移一年，同公司、同单据状态、同金额口径 |
| 销售同比增长率 | 同比卡 | 当前/上年销售额 | `(本期-上期)/上期`；上期为 0 时显示无基期 |
| 应收款同比增长率 | 同比卡 | Sales Invoice | 当前与上年同期的应收余额比较；明确使用期末余额还是期间平均余额 |

当前 API 使用 `-365` 天平移，遇到闰年可能与自然年同期不一致；建议改为按年/月/日历期间计算，并在指标定义中记录比较期间。

### 4.6 对账预警（Excel 29-31 行）

| Excel 指标 | 展示 | 数据来源 | 规则 |
| --- | --- | --- | --- |
| 未完成订单总数 | 核对预警卡 | Sales Order + Delivery Note | 订单明细尚未全部交货 |
| 状态不一致条数 | 核对预警卡 | Sales Order 状态 + 明细交货量 | 单据状态与明细交货事实不一致 |
| 异常明细 | 点击下钻 | Sales Order List | 显示订单号、客户、明细数量、已交量、状态和异常原因 |

“状态不一致”不能只统计 Completed 状态的订单，还应覆盖状态为交货中/未交货但明细事实相反的情况，并输出异常原因。

### 4.7 应收款核心管控（Excel 36-55 行）

#### 核心指标表

| Excel 列 | 系统字段 | 说明 |
| --- | --- | --- |
| 应收核心指标 | `metric_name` | 账龄区间、余额或目标指标名称 |
| 金额 | `value` | 从发票未结清余额或收款事实计算 |
| 占比 | `ratio` | 当前行金额 / 应收总余额 |
| 预警状态 | `status` | 由 Aging Period Rule、KPI Target 和余额规则生成，只读 |

指标行包括：应收总余额、30 天内到期应收、31-90 天逾期应收、90 天以上逾期应收、本月回款目标完成率。

#### 账龄区间

| Excel 区间 | 建议规则 |
| --- | --- |
| 30 天内到期 | `from_days=0, to_days=30` |
| 31-60 天逾期 | `from_days=31, to_days=60` |
| 61-90 天逾期 | `from_days=61, to_days=90` |
| 91-180 天逾期 | `from_days=91, to_days=180` |
| 180 天以上逾期 | `from_days=181, to_days` 为空 |

区间由 `Aging Period Rule` 维护，金额和占比不允许在规则表中填写。

#### 逾期客户 TOP10

| Excel 字段 | 下钻报表字段 | 数据来源 |
| --- | --- | --- |
| 客户名称 | `customer_name` | Sales Invoice.Customer |
| 逾期金额 | `overdue_amount` | 未结清发票余额 |
| 逾期天数 | `overdue_days` | 截止日 - 到期日 |
| 风险等级 | `risk_level` | Aging Period Rule |

当前 API 已生成逾期客户 TOP10，并允许点击进入 `Receivable Aging Analysis`。

### 4.8 生产采购运营核心指标（Excel 59-79 行）

| Excel 指标 | 目标配置编码 | 数据来源/口径 | 评价方向 |
| --- | --- | --- | --- |
| 本月生产计划完工率 | `production_completion_rate` | Work Order 已生产数量 / 计划数量 | 越高越好 |
| 采购到货及时率 | `purchase_on_time_rate` | 在评价截止日已到期/已完成交付的采购订单中，按时订单数 / 评价订单数 | 越高越好 |
| 实时库存总金额 | `realtime_inventory_amount` | `tabBin.actual_qty * valuation_rate`，排除客户借出仓 | 越低越好或按库存策略配置 |
| 安全库存预警物料数量 | `safety_stock_warning_count` | 预计库存低于物料/仓库补货警戒线的物料-仓库组合数 | 越低越好 |
| 采购在途金额 | `purchase_in_transit_amount` | 未收数量 × 采购价，排除关闭/取消订单 | 越低越好或按经营目标配置 |
| 生产领料超耗率 | `material_over_consumption_rate` | `max(已消耗-需求,0)` / 需求数量 | 越低越好 |

#### 月度生产完工率趋势

| Excel 字段 | 系统字段 | 来源 |
| --- | --- | --- |
| 月份 | `period` | Work Order planned_start_date |
| 计划产量 | `planned_qty` | Work Order.qty |
| 实际产量 | `actual_qty` | Work Order.produced_qty |
| 完工率 | `completion_rate` | 实际产量 / 计划产量 |

#### 采购到货延迟 TOP10 供应商

| Excel 字段 | 系统字段 | 来源 |
| --- | --- | --- |
| 供应商名称 | `supplier_name` | Purchase Order.Supplier |
| 延迟订单数 | `delayed_order_count` | 采购订单到货状态 |
| 平均延迟天数 | `average_delay_days` | 订单/收货日期差 |
| 风险等级 | `risk_level` | Purchase Delay Risk Rule |

当前看板已有 `Purchase Delay Analysis` 和采购延迟风险规则，可作为下钻和风险配置入口。

### 4.9 高新收入合规核心指标（Excel 81-101 行）

| Excel 指标 | 目标配置编码 | 数据来源/口径 | 状态 |
| --- | --- | --- | --- |
| 本年高新收入总额 | `high_tech_revenue` | 本年高新标记销售订单金额 | 达标/未达标 |
| 本年总营收总额 | `total_revenue` | 本年销售订单金额；需确认是否改为销售发票收入 | 达标/未达标 |
| 高新收入占比 | `high_tech_ratio` | 高新收入 / 总营收 | 合规/不合规 |
| 研发项目数量 | `rd_project_count` | 当前未完成/未取消 Project 数量；需确认是否改为本年有效项目数 | 达标/未达标 |
| 本年研发费用总额 | `rd_expense_amount` | 当前实现从带项目的 Purchase Invoice 汇总；需补充费用科目范围 | 达标/未达标 |
| 研发费用占比 | `rd_expense_ratio` | 研发费用 / 总营收 | 合规/不合规 |

#### 近 3 年趋势

| Excel 字段 | 系统字段 | 来源 |
| --- | --- | --- |
| 年度 | `year` | Sales Order.transaction_date |
| 高新收入总额 | `high_tech_revenue` | 高新标记订单金额 |
| 总营收总额 | `total_revenue` | 总销售订单金额 |
| 高新收入占比 | `high_tech_ratio` | 高新收入 / 总营收 |

#### 研发项目高新收入 TOP10

| Excel 字段 | 系统字段 | 来源 |
| --- | --- | --- |
| 研发项目名称 | `project_name` | Project / Sales Order.project |
| 高新收入总额 | `high_tech_revenue` | 项目关联高新订单金额 |
| 占比 | `ratio` | 项目高新收入 / 高新收入总额；当前看板需补充该列 |

注意：源表中的“研发项目数量 11、年度目标 10、达成率 110%、合规状态未达标”与通常“数量越高越好”的逻辑矛盾。实施时应统一目标方向和状态算法，不能直接照搬样例状态。

## 5. KPI Target 表单设计

### 5.1 现有字段复用

现有 `KPI Target` 已具备：

| 字段 | 用途 | 约束 |
| --- | --- | --- |
| company | 公司 | 必填，作为指标唯一作用域 |
| kpi_code | 指标编码 | 必须来自看板支持的指标定义 |
| kpi_name | 指标名称 | 系统根据编码自动带出，只读 |
| period_type | Monthly/Quarterly/Yearly | 与指标类型匹配 |
| period_value | 例如 2026-08、2026-Q3、2026 | 格式校验 |
| target_value | 目标值 | 金额、数量或比例，不能混用单位 |
| evaluation_direction | Higher/Lower Is Better | 决定达成率和状态方向 |
| warning_threshold | 预警阈值 | 方向与指标一致 |
| danger_threshold | 危险阈值 | 方向与指标一致 |
| remarks | 备注 | 可填写目标来源、预算版本、审批说明 |

### 5.2 建议增加的指标编码

现有编码已覆盖生产、采购、库存、高新和研发指标。为完整承接 Excel，建议补充以下编码：

```text
total_orders
total_sales_amount
high_tech_ratio
completed_orders
pending_orders
delivered_orders
delivering_orders
undelivered_orders
received_amount
receivable_amount
settled_documents
unsettled_documents
average_receivable_days
overdue_over_90
receivable_turnover_days
salesperson_delivery_count
salesperson_delivery_amount
salesperson_received_amount
salesperson_receivable_amount
salesperson_delivery_rate
salesperson_collection_rate
prior_sales_amount
sales_growth_rate
receivable_growth_rate
unfinished_orders
status_mismatch_count
monthly_collection_completion
total_revenue
rd_project_count
rd_expense_amount
rd_expense_ratio
```

实际新增前应先核对现有代码、报表和权限，避免与已存在编码重复。

### 5.3 目标值与结果值分离

- `KPI Target` 只保存目标、阈值、方向和周期。
- 看板 API 返回 `value`、`target`、`achievement`、`status`、`target_progress`。
- 用户可以修改目标配置，但不能在看板卡片中直接修改当前值。
- Excel 中 B/C/D/E 列的当前值、目标、达成率、状态不能作为同一张业务表的可写字段。

## 6. KPI Metric Definition 表单（本轮已配置）

为了保存 Excel 中各段的说明文本和公式，本轮已新增 `KPI Metric Definition`，字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| metric_code | Data/Unique | 与 API 返回 key 和 KPI Target.kpi_code 一致 |
| metric_name | Data | 中文展示名称 |
| section | Select | 销售、订单、回款、业务员、同比、对账、应收、运营、高新 |
| datatype | Select | Int、Float、Currency、Percent、Date |
| is_compliance | Check | 是否属于高新收入、研发费用等合规类指标；勾选后不能使用 Informational 评价方向 |
| enabled | Check | 是否允许看板读取该指标定义；停用只影响配置，不删除历史口径 |
| source_doctypes | Small Text | 例如 Sales Order、Delivery Note、Sales Invoice |
| formula | Long Text | 可读的计算公式 |
| filter_scope | Long Text | 公司、期间、状态、项目、业务员、仓库等过滤条件 |
| default_period_type | Select | Monthly/Quarterly/Yearly/Custom |
| evaluation_direction | Select | Higher Is Better/Lower Is Better/Informational |
| drilldown_report | Link/Select | 点击卡片或行进入的报表 |
| owner_role | Link/Select | 指标维护责任角色 |
| definition_version | Data | 口径变更时递增 |
| remarks | Long Text | Excel 说明、例外规则、数据质量注意事项 |

该表单用于“定义和解释指标”，不存实时数值，也不替代 KPI Target。

## 7. 看板页面布局承接关系

建议维持现有 `operations-kpi-dashboard` 页面并按 Excel 顺序展示：

1. 销售整体指标：4 张指标卡 + 销售收入构成图。
2. 订单完成状态：5 张指标卡 + 交付状态分布图。
3. 回款&应收款：6 张指标卡 + 回款/应收构成图。
4. 业务员业绩：业务员表格，默认 TOP10，可切换全部。
5. 同比指标：3 张指标卡。
6. 对账预警：未完成订单和状态不一致卡片，点击进入异常列表。
7. 应收核心管控：核心指标表、账龄分布、逾期客户 TOP10。
8. 生产采购运营：6 项核心指标、月度生产趋势、延迟供应商 TOP10。
9. 高新收入合规：6 项核心指标、3 年趋势、研发项目 TOP10。

页面统一提供：公司、起始日期、截止日期、刷新、导出 Excel。指标卡、表格行和 TOP10 项目只有在用户具备对应 Report/DocType 权限时才可点击下钻。

## 8. 数据流设计

```text
客户/供应商/物料/项目主数据
        |
销售订单、送货、发票、收款、采购订单、收货、工单、库存、项目费用
        |
已提交单据 + 公司/期间/业务员/仓库等筛选
        |
operations_kpi.get_kpi_dashboard_data
        |-- sales / delivery / receivable / salesperson
        |-- year_over_year / reconciliation
        |-- aging / operations / production_trend
        `-- high_tech / high_tech_trend / high_tech_projects
        |
看板指标卡、目标进度、状态、趋势、TOP10
        |
点击下钻到原始订单、收款、库存、工单、供应商和项目报表
```

KPI Target 和规则表单只参与目标/阈值/分段判定，不作为事实数据来源。所有计算结果都应能够反查到来源单据或明细行。

## 9. 现有实现与 Excel 的差异清单

| 差异 | 当前情况 | 实施要求 |
| --- | --- | --- |
| 已交货订单数与整单已完成订单数 | 当前 API 容易将两者都取为完全交货订单数 | 拆分“至少交货”和“全部完成” |
| 业务员回款率 | Excel 示例超过 100% | 核对重复收款、期间和销售团队分摊；超过 100% 应标记异常 |
| 同比日期 | 当前采用前移 365 天 | 改为自然年/同期间比较，处理闰年 |
| 总营收 | 当前高新模块使用 Sales Order 金额 | 明确财务口径；如要求实际收入，应改用 Sales Invoice |
| 研发项目数量 | 当前统计未完成/未取消项目 | 确认是存量项目数、本年立项数还是有高新收入项目数 |
| 研发费用 | 当前按带项目 Purchase Invoice 汇总 | 明确费用科目、Purchase Invoice/Purchase Expense 来源和是否含税 |
| 研发项目 TOP10 占比 | Excel 有占比列，当前看板表格未完整展示 | 增加项目高新收入占比 |
| 应收周转天数 | 当前与加权账龄计算接近 | 与财务确认标准公式，记录公式版本 |
| 采购及时率 | 当前排除尚未到期订单 | 在定义中明确评价分母和截止日 |
| 库存金额 | 当前读取 Bin.actual_qty × valuation_rate | 与库存报表、样品仓和客户借出仓排除规则对账 |
| 目标状态 | Excel 部分目标方向和状态不一致 | 统一由 evaluation_direction、threshold 和指标类型计算 |

## 10. 历史 Excel 数值处理策略

### 10.1 默认策略：作为验收样本

适用于当前文件中的示例值和占位客户/供应商/项目名称。处理方式：

1. 不导入看板当前值。
2. 先准备对应业务单据和目标配置。
3. 按相同公司、期间和权限打开看板。
4. 对比 Excel 样例值与系统计算值，差异记录到验收表。

### 10.2 需要保留历史结账结果时

如果企业要求保留某月已发布的看板结果，新增受控 `KPI Snapshot`：

- 快照期间、公司、指标编码、数值、单位、目标、达成率、状态。
- 来源文件名、来源行号、导入批次、口径版本、审核人、审核时间。
- 快照只读，不回写 Sales Order、Invoice、Stock Ledger 等事实表。
- 实时看板默认显示计算值；历史看板单独选择快照期间查看。

不建议把快照直接写进 KPI Target，也不建议把快照字段加入普通 Excel 导入向导。

## 11. 权限与表单规则

| 角色 | 看板 | KPI Target | Aging Rule | Purchase Delay Rule | 下钻 |
| --- | --- | --- | --- | --- | --- |
| System Manager | 查看/导出 | 增删改 | 增删改 | 增删改 | 全部 |
| Accounts Manager | 查看/导出 | 增删改 | 增删改 | 查看 | 应收/销售财务报表 |
| Sales Manager | 查看/导出 | 查看/报表 | 查看 | 无/查看 | 销售、送货、应收 |
| Purchase Manager | 查看/导出 | 查看/报表 | 无/查看 | 增删改 | 采购、供应商 |
| Stock Manager | 查看/导出 | 查看/报表 | 无/查看 | 查看/报表 | 库存、采购、生产 |
| Manufacturing Manager | 查看 | 查看/报表 | 无 | 查看/报表 | 工单、生产趋势 |

看板页面可见不等于拥有底层数据权限。API 必须继续执行角色检查和 Report/DocType 权限检查。

## 12. 实施分期

### 阶段一：指标定义和口径确认

1. 由销售、财务、采购、生产、库存和研发负责人确认每个指标的分子、分母、期间、公司范围和状态方向。
2. 确认“销售额/营收”的订单口径还是发票口径。
3. 确认回款率、周转天数、研发项目和研发费用口径。
4. 修正 Excel 中回款率超过 100%、目标状态反向等样例问题。

### 阶段二：配置表单

1. 补齐 KPI Target 指标编码和中文名称。
2. 配置月度、季度、年度目标及阈值。
3. 配置账龄区间和采购延迟风险区间。
4. 新增 KPI Metric Definition，录入公式、来源和下钻入口。

### 阶段三：看板与报表

1. 修正订单“已交货/整单完成”的两个指标。
2. 补齐业务员全部/前十切换及分摊明细。
3. 补齐项目高新收入占比和异常订单明细。
4. 将看板中文标题、单位、空值、未设置目标状态统一化。

### 阶段四：历史核对和上线

1. 以盘点日和财务结账日为切点，准备可追溯的业务明细。
2. 按公司、期间逐项对比 Excel 与系统结果。
3. 差异必须记录原因：数据缺失、口径不同、期间不同、重复核销或 Excel 计算错误。
4. 通过角色权限和下钻链路验收后，才开放正式使用。

## 13. 验收场景

### 销售与交付

- 一个订单包含三条明细，全部送货后进入“整单已完成”。
- 一个订单只送货一条明细，进入“交货中”，同时不计入整单完成。
- 一个订单没有任何送货，进入“未交货”。
- 送货单、订单和销售团队多人分摊时，业务员金额和条数符合约定。

### 回款与应收

- 一张发票分两次收款，已收、未收和结清状态正确。
- 发票跨期间收款时，期间回款和期末应收不重复计算。
- 账龄边界分别测试 30、31、60、61、90、91、180、181 天。
- 客户 TOP10 可点击进入对应客户/发票明细。

### 采购、生产和库存

- 未到期采购订单不进入延迟分母。
- 已延期未收货订单的延迟天数随截止日增长。
- 工单计划/实际产量计算完工率，趋势按月份分组。
- 采购在途金额、库存金额和安全库存预警可下钻至对应报表。

### 高新合规

- 高新收入标记为真/假时收入和占比变化正确。
- 年度目标、达成率和合规状态方向一致。
- 研发项目、费用来源和项目 TOP10 与财务/项目负责人确认。
- 近三年趋势只显示有来源数据的年份，空年份不伪造金额。

### 权限与异常

- 无 KPI 角色的用户不能调用看板 API。
- 无底层报表权限时，卡片仍可显示但不可下钻，或按产品决定隐藏。
- 公司为空、日期逆序、目标未设置、分母为 0 时显示明确提示。
- 同一筛选条件刷新多次不会出现旧请求覆盖新结果。

## 14. 风险清单

| 风险 | 影响 | 控制措施 |
| --- | --- | --- |
| 将汇总值直接导入 | 看板与业务单据脱节 | 当前值只读计算，Excel 不作为普通导入表 |
| Excel 样例值不是当前站点真实数据 | 验收误判 | 标记为样例，按公司/期间重算后对比 |
| 指标名称相同但口径不同 | 跨部门争议 | KPI Metric Definition 保存公式和版本 |
| 订单状态统计重复 | 完成数/已交数失真 | 分离 all-delivered 与 any-delivered |
| 财务金额期间混用 | 回款率、应收同比异常 | 明确发生日、过账日、到期日和期末口径 |
| 销售团队分摊比例不完整 | 业务员汇总超过总额 | 校验分摊比例合计，异常单据进入核对报表 |
| 研发费用来源不全 | 高新合规指标失真 | 确认费用科目和来源单据 |
| 目标方向设置错误 | 达成率和预警反向 | KPI Target 校验方向、阈值和单位 |
| 账龄区间重叠或断档 | TOP10 和金额占比错误 | Aging Period Rule 保存并校验连续区间 |
| 权限过宽暴露财务数据 | 数据安全风险 | API、报表、下钻三层权限校验 |

## 15. 当前实现状态（本轮交付）

本轮已按“先表单、后数据”的要求完成配置层代码，交付范围如下：

| 交付项 | 状态 | 说明 |
| --- | --- | --- |
| `KPI Metric Definition` DocType | 已完成 | 保存指标编码、名称、看板分区、数据类型、来源单据、计算公式、统计范围、周期、评价方向、下钻报表、维护角色和口径版本；不保存当前值 |
| 指标定义前端提示/校验 | 已完成 | Desk 表单显示“只维护口径，不录入当前金额/数量/达成率”的提示，并校验 snake_case 编码 |
| 运营指标看板设置入口 | 已完成 | 在看板侧栏增加“指标定义”，与 `KPI Target`、账龄规则和采购延迟规则并列 |
| Excel 样例数据导入 | 明确不做 | 未创建客户、供应商、项目、订单、库存、金额或 KPI 快照等示例记录 |
| 实时看板数值计算 | 保持现状 | 仍由已提交业务单据和现有看板 API 计算，本轮不以 Excel 快照覆盖 |

表单填写顺序建议为：先建立一条指标定义并确认口径，再在 `KPI Target` 中维护目标和阈值，最后由看板从业务单据计算当前值。若暂时没有真实业务单据，可在测试环境使用现有测试夹具或只读的 Playwright mock 响应验证页面展示；不要把 mock 数值保存到生产站点。

本轮未扩充 `KPI Target` 的全部指标编码，也未修改 `operations_kpi.py` 的计算逻辑。这是有意的边界：在指标口径和真实来源尚未确认前，避免出现“表单可以配置目标，但看板尚未计算该指标”的误导。

## 16. 后续实施代码范围

完成业务口径确认后，建议按以下顺序推进：

1. `client_akivision/client_akivision/api/operations_kpi.py`：补齐指标、修正订单完成状态、同比和高新口径。
2. `client_akivision/client_akivision/page/operations_kpi_dashboard/operations_kpi_dashboard.js`：补齐中文标签、业务员全量/Top10、项目占比和异常入口。
3. `client_akivision/client_akivision/doctype/kpi_target/kpi_target.py`：扩充指标编码、单位和方向校验。
4. 执行迁移并验收已新增的 `KPI Metric Definition` DocType、权限和侧边栏入口。
5. 现有 `Sales Order List`、`Receivable Aging Analysis`、`Purchase Delay Analysis`、`Realtime Inventory`、`High-tech Revenue Analysis` 等报表：作为看板下钻源，保持单一事实来源。
6. 根据差异确认结果补充单元测试、API 测试和 Playwright 看板验收。

部署本轮 DocType 后，应执行站点迁移并检查：DocType 能打开、侧栏入口可见、指标编码非法时不能保存、合规指标不能选择 Informational、下钻报表不存在时不能保存。迁移检查只验证结构和校验，不要求也不应产生业务数据。

在完成阶段一的业务口径确认前，不建议把 Excel 中的示例值写入数据库，也不建议直接开放“各项指标汇总或看板数据”作为导入表单。

## 17. 本轮实施交付与沉淀（2026-08-22）

人工测试执行稿：[`kpi_dashboard_manual_test_sequence.md`](./kpi_dashboard_manual_test_sequence.md)。

### 17.1 已落地代码

本轮已将第 16 节中的代码范围实际落地，主要文件如下：

| 文件 | 实施内容 |
| --- | --- |
| `client_akivision/api/operations_kpi.py` | 增加 Top10/全部业务员行数参数；区分“至少有交货”与“整单全部交货”；同比按自然年平移 12 个月；扩展 KPI Target 应用；补充状态不一致规则和研发项目收入占比；下钻权限由 API 返回 |
| `client_akivision/api/operations_kpi_export.py` | Excel 导出复用同一筛选和指标数据，增加业务员行数筛选、研发项目占比列；标题合并覆盖 A:J 筛选区域 |
| `client_akivision/page/operations_kpi_dashboard/operations_kpi_dashboard.js` | 增加业务员 Top10/全部选择器、日期逆序校验、失败重试、权限安全下钻、平均应收天数/周转天数、研发项目占比、移动端表格容器约束和统一模块标题 |
| `client_akivision/doctype/kpi_target/kpi_target.py/js` | 补齐销售、交付、应收、业务员、同比、对账等指标编码及评价方向 |

旧文档第 15-16 节描述的是实施前边界；以上表格是本轮实际交付状态，应以本节为准。

### 17.2 数据流

```text
页面筛选（公司/起止日期/业务员行数）
        ↓
get_kpi_dashboard_data()
        ↓
Sales Order、Sales Order Item、Delivery Note、Sales Invoice、Payment Entry
Work Order、Purchase Order、Bin/Warehouse、Project/费用来源
        ↓
指标计算 + KPI Target/Aging Period Rule/Purchase Delay Risk Rule
        ↓
指标卡、核心指标表、趋势图、TOP10、权限标记
        ↓
允许的 Query Report/List 下钻，或按相同数据生成 Excel
```

看板不写入汇总快照，也不把 Excel 示例值回填业务单据。页面和导出共用同一 API 计算层，避免“页面一个口径、Excel 另一个口径”。下钻权限由服务端计算后返回，浏览器不自行猜测用户权限。

### 17.3 依赖清单

| 依赖 | 用途 | 缺失/异常时的表现 |
| --- | --- | --- |
| Frappe Desk/Page、角色权限 | 页面、API 白名单、Report/DocType 权限 | 无 KPI 角色拒绝访问；无报表权限时卡片不可点击 |
| MariaDB 业务表 | 销售、交付、应收、采购、生产、库存计算 | SQL/字段迁移不完整时需在真实站点复测 |
| `KPI Target` | 目标、评价方向、阈值和达成率 | 未配置目标显示“未设置”，不阻断看板 |
| `Aging Period Rule` | 账龄区间及风险等级 | 使用默认区间；上线前应检查区间连续性 |
| `Purchase Delay Risk Rule` | 采购延迟风险等级 | 使用默认风险区间 |
| xlsxwriter | 服务端 Excel 导出 | 未安装时导出失败，但页面计算不受影响 |
| Frappe Chart/浏览器 CSS | 趋势图、环图和响应式布局 | 图表无数据时显示空态 |

### 17.4 风险点与控制措施

| 风险点 | 当前控制 | 仍需业务确认 |
| --- | --- | --- |
| 已交货与整单完成混淆 | SQL 分别统计 `any_delivered` 和 `fully_delivered` | 订单明细数量异常、退货冲销规则 |
| 同比跨闰年偏移 | 改为自然期间前移 12 个月 | 财务是否按订单日、发票日或过账日 |
| 回款率超过 100% | 按“已收/(已收+应收)”计算并保留分摊结果 | 多销售员分摊、跨期收款和重复核销 |
| 应收周转天数口径 | 当前与未结清余额加权账龄同值，已标注为近似口径 | 财务确认严格周转公式和平均应收余额来源 |
| 高新总营收来源 | 当前沿用 Sales Order，页面与导出一致 | 是否改用 Sales Invoice/收入科目 |
| 研发费用、项目数量 | 保留现有来源并展示目标状态 | 费用科目范围、本年有效项目定义 |
| 下钻越权 | 服务端返回权限，前端仅对允许入口加可点击行为 | 各角色真实 Report 权限矩阵 |
| 移动端表格撑破页面 | 表格容器 `overflow-x:auto`，网格子项 `min-width:0` | 真实 Frappe 主题变量和字体下复测 |

### 17.5 Playwright 验证与问题记录

已运行：

```text
/home/cst/frappe_docker/development/erpnext.official/.tools/node/bin/node \
  docs/playwright_kpi_dashboard_ui.mjs
```

证据文件：

- `docs/playwright_kpi_dashboard_result.json`
- `docs/playwright_kpi_dashboard_desktop.png`
- `docs/playwright_kpi_dashboard_mobile.png`

8 项断言全部通过：九个看板分区、交付语义区分、字段完整性、权限下钻、Top10/全部切换、Excel 导出、390px 移动端无横向溢出、日期错误与重试。

本轮发现并解决的问题：

1. 业务员表格缺少统一的模块 `h4` 标题，导致无法按 Excel 九大分区扫描；已在 `table_section()` 增加标题。
2. 移动端表格和双栏网格最小内容宽度导致页面宽度达到 1024px；已增加表格内部横向滚动和网格子项最小宽度约束。
3. 测试脚本初始正则和 Playwright Locator API 使用错误，均已修正后重跑通过。

限制：本次使用模拟 `frappe.call` 数据和临时 HTTP 服务，不能替代真实登录站点、MariaDB SQL、角色权限和业务数据核对；结果文件已明确标记这些限制。

### 17.6 上线前必须复测的场景

1. 订单含多明细时，0%、部分、100% 交货分别落入未交货/交货中/整单完成，且“已交货”按至少一条明细交货统计。
2. 30/31/60/61/90/91/180/181 天账龄边界、跨期收款、部分核销和退货冲销。
3. 同一销售订单多销售员分摊比例合计 100%，异常分摊不得使个人回款率虚高。
4. 闰年 2 月 29 日及跨年度筛选的同比期间；基期为 0 时显示无基期而非无限增长。
5. Sales Order 与 Sales Invoice 两种营收口径对高新收入、总营收、占比的差异。
6. 研发费用科目、项目状态、年度范围及项目 TOP10 占比合计关系。
7. 采购未到期订单不进入及时率分母，库存借出仓排除规则与在途金额下钻。
8. System Manager、销售、财务、采购、库存、生产角色分别验证看板访问、卡片点击和报表下钻权限。
9. 真实 Frappe 主题下 1440px、1024px、768px、390px 视口截图，检查字体、表格滚动、图表非空和无遮挡。
