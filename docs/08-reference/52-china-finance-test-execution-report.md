# 中国财务模块测试执行报告

## 1. 执行结论

本次按照《[中国财务模块完整测试计划](./51-china-finance-complete-test-plan.md)》执行了自动化单元测试、Playwright 登录和全量页面审计，并完成了测试数据库的配置与元数据核对。

当前结论：**模块基础页面可访问，自动化规则测试基本通过；完整业务写入链路尚未通过验收，存在 1 个自动化失败、现金流配置阻塞、发票识别入口阻塞和多个 404 资源问题。**

本报告不把“页面打开”当作“业务表功能通过”。未实际创建、提交、下游核对的业务表均明确标为“待业务写入测试”。

## 2. 测试环境和证据

| 项目 | 结果 |
| --- | --- |
| 站点 | `aki_test.localhost` |
| 地址 | `http://aki_test.localhost:8300` |
| 用户 | `Administrator / admin` |
| 浏览器 | Playwright Chromium |
| 自动化脚本 | `docs/playwright_china_finance_full_audit.mjs` |
| 页面审计结果 | `docs/china-finance-test-evidence/page-audit.json` |
| 页面审计截图 | `docs/china-finance-test-evidence/last-page.png` |
| 应用测试 | `bench --site aki_test.localhost run-tests --app china_finance` |

测试过程中临时将站点 `allow_tests` 改为 `true` 运行应用测试，完成后已恢复为 `false`。未修改业务代码，未删除原有业务数据。

## 3. 自动化测试结果

China Finance 应用测试共运行 **53 项**：

- **52 项通过**；
- **1 项失败**；
- 集成测试 `test_new_company_initialization_uses_numbered_profile` 通过，但测试日志暴露初始化数据问题。

### 3.1 失败项：累计折旧现金流分类

失败测试：

```text
china_finance.tests.test_china_coa_profile.TestChinaCoaProfile
test_all_non_cash_leaf_accounts_have_cash_flow_suggestion
```

失败数据：

```text
account_number: 160201
account_name: 机器设备累计折旧
account_type: Accumulated Depreciation
result: ('CASH_PAID_LONG_TERM_ASSETS', 'CASH_RECEIVED_ASSET_DISPOSAL', 'CASH_PAID_LONG_TERM_ASSETS')
expected: None
```

判断：累计折旧科目同时得到长期资产支付、资产处置收款和长期资产支付建议，属于现金流自动映射歧义。该问题会影响现金流量表映射和人工指定建议。

最小解决方法：在现金流分类函数中对累计折旧等非现金科目返回空建议，或明确只允许一个人工指定上下文。

优化方案：将现金流映射拆分为“自动映射”“人工指定”“报表展示”三层，并增加每个会计科目只能有一个默认现金流建议的校验。

### 3.2 集成测试日志问题

新公司初始化测试最终通过，但日志多次出现：

```text
LinkValidationError: Could not find Parent Department: All Departments
```

判断：初始化测试环境缺少标准父部门数据，当前测试通过是因为该错误被初始化流程记录后继续执行，不代表初始化数据完整。

解决方法：测试 fixture 或初始化流程先创建目标公司的 `All Departments` 根部门，再创建子部门。

优化方案：将初始化日志中的 LinkValidationError 视为失败而非可忽略日志，并在集成测试中断言公司基础主数据完整。

## 4. Playwright 全量页面审计

脚本检查了 **41 个 DocType 元数据/列表入口**和 **11 个中国财务报表入口**。41 个 DocType 均能从站点元数据读取，子表被识别并跳过独立列表访问；所有可独立访问的主表和报表均尝试打开。

页面审计共记录 **158 个 HTTP/浏览器错误事件**。错误主要集中为页面加载时的 404 资源或接口请求，必须查看 `page-audit.json` 中的具体 URL 后逐项归类。

### 4.1 已验证可访问的主表/入口

以下入口能够进入 Frappe Desk 路由并完成页面加载尝试：

- China Accounting Policy
- China Accounting Voucher
- China Cash Equivalent Scope
- China Cash Flow Assignment
- China Closing Run
- China Electronic Document
- China Finance Settings
- China Financial Statement Mapping
- China Financial Statement Notes
- China Financial Statement Reclassification Rule
- China Financial Statement Template
- China Input Tax Deduction Batch
- China Invoice Control Rule
- China Prior Period Error Adjustment
- China Purchase Reconciliation Rule
- China Reconciliation Difference
- China Reconciliation Scope
- China Reconciliation Statement
- China Report Snapshot
- China Sales Invoice Control
- China Sales Settlement
- China Sales Settlement Rule
- China Tax Account Mapping
- China Tax Integration Call
- China Tax Invoice
- China Tax Invoice Recognition
- China Tax Invoice Request
- China Voucher Recycle Bin Item
- China Voucher Sequence
- China Voucher Sync Issue

子表 `China Accounting Voucher Entry`、`China Cash Flow Assignment Item`、`China Financial Statement Row`、`China Input Tax Deduction Item`、`China Prior Period Error Adjustment Line`、`China Reconciliation Line`、`China Sales Settlement Item`、`China Tax Invoice Allocation`、`China Tax Invoice Item`、`China Tax Invoice Request Item` 不作为独立用户入口，必须在父表保存/提交时验证。

### 4.2 已验证的报表入口

- China AR AP Ledger Reconciliation
- China Business Document Chain
- China Daily Ledger
- China Financial Statements
- China Output Invoice Reconciliation
- China Purchase Document Chain
- China Purchase Reconciliation
- China VAT Ledger
- China VAT Return Worksheet
- China Voucher Integrity
- China Voucher Ledger

报表页面打开不等于报表口径正确。报表金额必须等业务凭证提交后，按来源 GL Entry 和中国财务快照逐项核对。

## 5. 配置和数据基线

### 5.1 公司和期间

已读取到 CNY 公司：

- `西安分公司`
- `阿基视觉（东莞）`
- `阿基视觉（东莞）有限公司`

已读取到 2026 会计年度：

```text
2026-01-01 至 2026-12-31
```

### 5.2 可用测试科目

目标公司 `阿基视觉（东莞）` 存在以下明细科目：

```text
1001 - 库存现金 - T       Cash
100201 - 基本存款账户 - T  Bank
1122 - 应收账款 - T        Receivable
```

正式业务写入测试应先在表单中选择公司，再从 Link 字段选择这些真实科目，不能把其他公司的同名科目带入。

### 5.3 现金流配置阻塞

`China Finance Settings` 中目标公司 `阿基视觉（东莞）` 的 `cash_flow_assignment_activation_date` 当前为空；另有名为 `test` 的配置记录，其启用日期为 `2026-07-22`。

因此现金流量指定的正式写入测试目前不能直接判定通过。应先明确目标公司的启用日期和有效现金流模板，否则“未生成指定单”可能是配置预期，而不是程序错误。

## 6. 全量表测试状态

状态定义：

- **通过-规则**：自动化规则/元数据已通过，但不代表真实业务写入已通过；
- **通过-页面**：页面可访问，但不代表数据正确；
- **待写入**：尚未创建、提交和下游核对真实单据；
- **阻塞**：存在配置或程序问题，不能继续判定；
- **子表待父表**：必须随父表保存/提交测试。

### 6.1 凭证和现金流

| 对象 | 状态 | 来源和待核对内容 |
| --- | --- | --- |
| China Accounting Voucher | 待写入 | Journal Entry/手工凭证 -> 凭证快照 |
| China Accounting Voucher Entry | 子表待父表 | 借贷、科目、金额逐行一致 |
| China Cash Flow Assignment | 阻塞 | 目标公司启用日期为空，需先补有效配置 |
| China Cash Flow Assignment Item | 子表待父表 | 方向、现金流项目、指定金额 |
| China Cash Equivalent Scope | 通过-页面/待业务 | 需用实际现金流报表核对科目范围 |
| China Voucher Sequence | 待写入 | 提交凭证后验证字号连续、不重复 |
| China Voucher Sync Issue | 待异常 | 需模拟快照同步失败并验证重试 |
| China Voucher Recycle Bin Item | 待异常 | 需执行回收/恢复流程 |

### 6.2 设置和报表配置

| 对象 | 状态 | 来源和待核对内容 |
| --- | --- | --- |
| China Finance Settings | 通过-页面/配置待确认 | 公司、启用日期、现金流配置 |
| China Accounting Policy | 通过-规则 | 应补充配置变更后的凭证/报表回归 |
| China Financial Statement Template | 通过-页面 | 模板版本和公司适配 |
| China Financial Statement Row | 子表待模板 | 行号、层级、公式 |
| China Financial Statement Mapping | 通过-规则 | 已有规则测试，但累计折旧映射失败 |
| China Financial Statement Notes | 待写入 | 财报附注来源和期间 |
| China Financial Statement Reclassification Rule | 通过-页面/待写入 | 需用实际科目验证报表影响 |
| China Tax Account Mapping | 通过-页面/待写入 | 税率/税种到科目 |
| China Invoice Control Rule | 通过-页面/待写入 | 重复发票和状态控制 |

### 6.3 税务发票

| 对象 | 状态 | 来源和待核对内容 |
| --- | --- | --- |
| China Tax Invoice | 通过-页面/待写入 | 发票主表保存、提交、状态 |
| China Tax Invoice Item | 子表待父表 | 未税额、税率、税额和价税合计 |
| China Tax Invoice Allocation | 子表待父表 | 业务单据分摊合计 |
| China Tax Invoice Recognition | 阻塞 | 旧 Playwright 脚本找不到当前上传控件 |
| China Tax Integration Call | 待接口 | 识别/查验请求和错误日志 |
| China Tax Invoice Request | 待写入 | 开票申请来源和金额 |
| China Tax Invoice Request Item | 子表待父表 | 申请明细 |
| China Input Tax Deduction Batch | 待写入 | 抵扣批次和发票集合 |
| China Input Tax Deduction Item | 子表待父表 | 税额、抵扣状态 |
| China Sales Invoice Control | 待业务链 | 销项发票和销售业务关联 |

### 6.4 对账、结算和结账

| 对象 | 状态 | 来源和待核对内容 |
| --- | --- | --- |
| China Reconciliation Scope | 通过-页面/待写入 | 公司、客户/供应商范围 |
| China Reconciliation Statement | 待业务链 | GL、业务单据、已结算和未结算 |
| China Reconciliation Line | 子表待父表 | 单据和金额 |
| China Reconciliation Difference | 待业务链 | 差异来源、金额、处理状态 |
| China Purchase Reconciliation Rule | 通过-页面/待写入 | 匹配字段和阈值 |
| China Sales Settlement Rule | 通过-页面/待写入 | 结算模式和规则 |
| China Sales Settlement | 待写入 | 订单/发票/收款结算 |
| China Sales Settlement Item | 子表待父表 | 结算明细和分摊 |
| China Closing Check | 待写入 | 未提交、未指定、未核销检查 |
| China Closing Run | 通过-页面/待写入 | 期间结账、重复执行和锁定 |

### 6.5 档案和快照

| 对象 | 状态 | 来源和待核对内容 |
| --- | --- | --- |
| China Electronic Document | 待附件链 | 文件、来源和哈希 |
| China Report Snapshot | 待报表链 | 快照期间、筛选和不可漂移 |

## 7. 尚未完成的正式业务写入

以下 P0 流程必须在明确现金流配置后继续执行，当前不能标记为通过：

1. 新建并提交 `Journal Entry`，金额 `100.00 CNY`。
2. 核对生成的 `GL Entry`。
3. 核对 `China Accounting Voucher` 和 `China Accounting Voucher Entry`。
4. 在查凭证、凭证汇总、会计总账和日账簿中核对金额。
5. 创建、确认和作废 `China Cash Flow Assignment`。
6. 新建中国税务发票、发票明细和附件。
7. 创建发票业务分摊、进项税抵扣和销售结算链路。
8. 执行对账差异和结账检查。
9. 取消测试凭证并确认所有报表回滚。

## 8. 人工测试流程

### 8.1 凭证人工测试

1. 登录 `http://aki_test.localhost:8300`。
2. 进入“中国财务 -> 凭证 -> 新增凭证”。
3. 公司选择 `阿基视觉（东莞）`；日期选择 2026 年未结账日期。
4. 摘要输入 `中国财务模块连通性测试-人工-日期`。
5. 借方选择 `100201 - 基本存款账户 - T`，金额 `100.00`。
6. 贷方选择 `1122 - 应收账款 - T`，金额 `100.00`。
7. 保存，记录草稿编号；确认借贷合计均为 `100.00`。
8. 提交，记录正式凭证编号。
9. 打开查凭证、凭证汇总、会计总账和日账簿，按编号查询。
10. 对比 Journal Entry、GL Entry 和中国凭证快照金额。

### 8.2 现金流人工测试

1. 先在中国财务设置确认目标公司的现金流启用日期和有效模板。
2. 从凭证或“现金流量指定单”进入指定单。
3. 确认来源凭证、现金科目和可指定金额。
4. 选择模板中的收款项目，录入 `100.00`。
5. 保存并确认，检查状态和指定明细。
6. 打开中国财务报表的现金流量表，核对只增加一次。
7. 作废指定单，确认报表恢复。

### 8.3 发票人工测试

1. 进入“中国财务 -> 发票管理 -> 中国税务发票 -> 新建”。
2. 选择公司、进销项和发票类型。
3. 输入唯一测试发票号码和日期。
4. 增加发票明细：未税金额、税率、税额。
5. 检查价税合计和明细合计。
6. 添加 PDF/图片附件并保存。
7. 按系统规则提交，记录发票编号。
8. 查看发票列表、附件中心、进项税抵扣或销项报表。
9. OCR 测试必须确认“识别成功”和“税务查验成功”是两个不同状态。

### 8.4 对账和结账人工测试

1. 在对账单中按测试客户、供应商或凭证查询。
2. 核对已结算、未结算和差异金额。
3. 打开中国结账检查，记录所有检查项。
4. 只有没有其他待处理业务时，才执行测试期间结账。
5. 再次执行结账，确认系统阻止重复结账。
6. 尝试在已结账期间新建凭证，确认系统阻止提交。

## 9. 已发现问题和优化方案

| 编号 | 问题 | 原因 | 最小解决方法 | 长期优化 |
| --- | --- | --- | --- | --- |
| CF-EXEC-001 | 累计折旧现金流分类测试失败 | 一个非现金科目得到多个现金流建议 | 修正分类函数返回空或单一建议 | 增加映射唯一性校验和人工指定分层 |
| CF-EXEC-002 | 新公司初始化日志缺少 All Departments | 测试基础主数据不完整 | 初始化前创建根部门 | 初始化错误升级为测试失败并补 fixture |
| CF-EXEC-003 | 页面审计记录 158 个 4xx/5xx 事件 | 资源或接口 URL 未逐项归类 | 从 page-audit.json 按 URL 定位 | CI 将关键 4xx/5xx 纳入页面验收门禁 |
| CF-EXEC-004 | 发票识别入口找不到上传控件 | 旧脚本依赖旧路由/旧弹窗 DOM | 使用列表入口和 filechooser 事件 | 前端提供稳定语义选择器和上传状态 |
| CF-EXEC-005 | 目标公司现金流启用日期为空 | 配置未完成 | 明确启用日期和模板后再测 | 设置页增加必填校验和配置状态提示 |
| CF-EXEC-006 | 报表可打开但缺少业务写入证据 | 页面可访问不等于口径正确 | 提交已知凭证后逐项核对 | 每个报表增加来源摘要和核对接口 |

## 10. 后续执行顺序

1. 由财务负责人确认目标公司和现金流启用日期/模板。
2. 按第 8.1 节创建并提交测试凭证。
3. 记录所有生成编号并补齐第 7 节数据核对。
4. 按第 8.2 节确认现金流指定。
5. 按第 8.3 节完成发票及子表链路。
6. 按第 8.4 节完成对账和结账检查。
7. 执行取消/作废回滚。
8. 将每张表的状态从“待写入”更新为“通过”“失败”或“阻塞”，不得跳过中间状态。

