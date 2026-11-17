# 中国财务模块 Playwright 验收记录

## 1. 测试范围

本记录针对测试站点 `aki_test.localhost`，目标是按正常用户流程验证中国财务模块的页面、单据和数据流向。测试允许在测试数据库创建、提交和取消测试数据；正式提交凭证前必须确认公司、期间和科目来自当前站点配置。

测试入口：`http://aki_test.localhost:8300`

测试账号：`Administrator / admin`

浏览器：Playwright Chromium，运行在 `devcontainer-frappe-1` 容器内。

## 2. 已执行步骤

| 步骤 | 页面/对象 | 结果 |
| --- | --- | --- |
| 1 | 登录页 | 通过，Administrator 登录成功 |
| 2 | 中国财务工作台 | 通过，导航正常加载 |
| 3 | 中国税务发票新建 | 通过，实际路由为 `/desk/china-tax-invoice/new-...` |
| 4 | 发票操作菜单 | 菜单可见，显示“识别发票” |
| 5 | 识别发票上传弹窗 | 未通过，点击后未找到可见弹窗或文件控件 |
| 6 | 页面控制台 | 发现 3 个静态资源/接口 404，具体 URL 尚待记录 |
| 7 | 公司和科目配置读取 | 通过，已读取真实公司、币种和明细科目 |
| 8 | 现金流量指定单模型确认 | 通过，真实 DocType 为 `China Cash Flow Assignment` |

本轮尚未提交会计凭证或税务发票，避免在业务模型尚未完全确认时产生脏测试数据。

## 3. 系统实际数据

当前系统存在以下 CNY 公司：

- `西安分公司`
- `阿基视觉（东莞）`
- `阿基视觉（东莞）有限公司`

已确认属于 `阿基视觉（东莞）` 且可直接记账的明细科目示例：

- `1001 - 库存现金 - T`，科目类型 Cash
- `100201 - 基本存款账户 - T`，科目类型 Bank
- `1122 - 应收账款 - T`，科目类型 Receivable

正式测试必须在表单中选择当前公司的真实科目，不能手工输入仅显示名称的假科目。若默认公司不是 `阿基视觉（东莞）`，应改用该公司的对应科目。

## 4. 真实数据模型

### 4.1 记账链路

```text
手工凭证页面
  -> Journal Entry
  -> GL Entry
  -> China Accounting Voucher
  -> China Accounting Voucher Entry
  -> 凭证汇总、查凭证、日账簿、会计总账
```

### 4.2 现金流链路

```text
过账凭证中的现金/银行 GL Entry
  -> China Cash Flow Assignment
  -> China Cash Flow Assignment Item
  -> 中国财务报表中的现金流量表
```

`Cash Flow Mapping` 是模板/映射概念，不是本系统中可直接查询的业务 DocType。直接查询该名称得到 `DocType Cash Flow Mapping not found`，这是错误的测试假设，不是数据库连接故障。

### 4.3 已发现的相关对象

- `China Finance Settings`
- `China Accounting Voucher`
- `China Accounting Voucher Entry`
- `China Cash Flow Assignment`
- `China Cash Flow Assignment Item`
- `China Tax Invoice`
- `China Tax Invoice Item`
- `China Tax Invoice Allocation`
- `China Reconciliation Statement`
- `China Closing Run`
- `China Voucher Ledger` 报表
- `China Daily Ledger` 报表
- `China Financial Statements` 报表

## 5. 待执行的正常业务测试

### 5.1 手工凭证

推荐使用当前公司配置中实际存在的以下业务数据：

```text
摘要：中国财务模块连通性测试-20260907
借方：100201 - 基本存款账户 - T
借方金额：100.00
贷方：1122 - 应收账款 - T
贷方金额：100.00
日期：当前未结账会计期间
```

执行步骤：

1. 进入“中国财务 -> 凭证 -> 新增凭证”。
2. 选择实际公司和当前期间日期。
3. 录入上述借贷分录，确认借贷平衡。
4. 保存并记录 Journal Entry 编号。
5. 提交凭证。
6. 检查是否生成 GL Entry。
7. 检查是否生成 China Accounting Voucher 及其分录快照。
8. 在查凭证、凭证汇总、会计总账和日账簿中按编号查询。

预期：借方和贷方均为 `100.00`；凭证、GL Entry、快照和报表金额一致。

### 5.2 现金流量指定

1. 打开由凭证自动生成或列表中关联的 `China Cash Flow Assignment`。
2. 检查来源凭证、公司、日期和现金/银行金额。
3. 选择当前公司现金流模板中的实际明细项目。
4. 指定 `100.00`，方向应为“收款”。
5. 保存并确认。
6. 在中国财务报表中查询现金流量表。

预期：指定金额等于现金类 GL Entry 金额，现金流量表只增加一次，不重复统计。

### 5.3 取消和回滚

1. 取消测试凭证。
2. 检查 GL Entry 是否不再计入有效余额。
3. 检查现金流量指定单是否变为作废或不再计入报表。
4. 检查凭证汇总和日账簿是否同步排除。

## 6. 已发现问题

### 问题 A：旧 Playwright 路由写死

现象：旧脚本访问 `/app/china-tax-invoice/new-china-tax-invoice-1`，当前系统实际使用 `/desk/china-tax-invoice/new-随机名`。

原因：脚本依赖旧版路由和固定单据名。

解决方法：从列表页点击“新建”，等待 `/desk/.../new-` 路由，不写死名称。

优化方案：所有验收脚本优先使用角色、按钮文本和 DocType 列表入口；只对最终业务断言使用单据编号。

### 问题 B：识别发票菜单没有打开上传控件

现象：菜单中能看到“识别发票”，但点击后没有可定位的 `.modal`、`[role=dialog]` 或 `input[type=file]`。

原因：当前页面实现与旧脚本假设不同，可能使用文件选择器事件、动态组件或事件注册缺失。

解决方法：用 `page.waitForEvent("filechooser")` 验证点击后的文件选择器；同时记录点击后的 DOM 和网络请求。

优化方案：前端入口应在点击后明确打开带标题、文件类型限制和错误提示的上传弹窗；测试选择器应使用语义化按钮和文件选择器事件。

### 问题 C：页面存在 3 个 404 请求

现象：进入中国税务发票页面时控制台出现 3 条 `Failed to load resource: 404`。

原因：目前尚未记录具体 URL，可能是静态资源、旧接口或不存在的报表方法。

解决方法：Playwright 记录所有 `response.status() >= 400` 的 URL、请求方法和响应正文，再分别修复资源路径或接口注册。

优化方案：验收脚本把 4xx/5xx 作为独立失败项，不只依赖页面是否能显示。

### 问题 D：现金流量 DocType 名称容易误解

现象：导航显示“现金流量指定单”，但按 `Cash Flow Mapping` 查询不存在。

原因：模板映射和实际业务指定单命名不同。

解决方法：以 `China Cash Flow Assignment` 和 `China Cash Flow Assignment Item` 为实际业务对象。

优化方案：在开发文档、接口命名和页面帮助中明确区分“现金流模板/映射”和“现金流量指定单”。

## 7. 验收判定标准

### 凭证链路

```text
Journal Entry 借贷合计
= GL Entry 借贷合计
= China Accounting Voucher 快照金额
= 会计总账/日账簿金额
```

### 现金流链路

```text
现金类 GL Entry 金额
= China Cash Flow Assignment Item.assigned_amount
= 现金流量表对应项目金额
```

### 权限和数据隔离

- 不同公司不能互相查询凭证和现金流指定单。
- 非财务角色不能提交或确认凭证。
- 已提交凭证不能直接修改金额和科目。
- 作废凭证和作废现金流指定不能继续进入有效报表。

## 8. 下一轮执行顺序

1. 修正 Playwright 的列表入口和 404 记录。
2. 读取中国财务设置的默认公司、启用日期、会计期间和现金流模板。
3. 使用实际公司和明细科目创建上面的 `100.00` 测试凭证。
4. 提交并记录所有生成的单据编号。
5. 逐个打开查凭证、凭证汇总、会计总账、日账簿和现金流量指定单。
6. 确认现金流并查询中国财务报表。
7. 取消测试凭证，检查回滚。
8. 将每一步的实际结果、截图、控制台错误和网络错误补充到本文档。

