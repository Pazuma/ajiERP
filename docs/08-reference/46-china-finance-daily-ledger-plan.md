# 中国财务“日账簿”新增方案

## 1. 文档状态

- 阶段：方案沉淀，尚未修改业务代码、数据库或导航数据。
- 目标版本：后续按本文实施。
- 设计基线：当前 `china_finance` 自定义应用与 ERPNext 标准 `General Ledger` Script Report。
- 需求来源：在“中国财务 -> 账簿”增加“日账簿”，视觉和操作方式参考众马会计日记账页面，同时贴合现有 Frappe Desk 风格。

## 2. 目标与范围

新增一个只读的 `China Daily Ledger` Script Report，中文显示名为“日账簿”。用户可按公司、财务账簿和会计期间查看逐日总账流水，并按摘要、科目、凭证号和往来单位缩小范围。页面提供本月小计、期初余额、收入、支出、余额，以及下载和打印能力。

本次采用独立报表分支，不直接修改 ERPNext 标准 `General Ledger`，也不修改现有“会计总账”入口。新报表复用标准总账的权限、筛选和取数函数，再转换为日账簿专用列。这样既能实现参考图的页面结构，又能把影响限制在新入口内。

### 2.1 本期范围

- 在“账簿”分组增加“日账簿”入口。
- 新增独立 Script Report 及局部 CSS。
- 支持公司、财务账簿、月份/日期、科目、凭证号和关键词筛选。
- 展示期初余额、当期收入/支出小计和期末余额。
- 复用 Frappe 报表的刷新、导出、打印、权限和金额格式化能力。
- 点击凭证号进入原始单据，点击科目进入科目详情。

### 2.2 非目标

- 不在列表中直接新增、编辑、删除或批量删除凭证。
- 不复制参考系统的蓝色品牌色、右侧悬浮月份轴或顶部多标签框架。
- 不新增“收支大类/收支类型”主数据；这些字段在现有 GL Entry 中没有稳定来源，本期不伪造。
- 不修改 `GL Entry`、`Journal Entry`、`Finance Book` 等标准 DocType。
- 不改变凭证生成、冲销、结账、对账和会计总账的既有接口及返回结构。

> 说明：参考图中的“导入日记账、生成凭证、批量操作”属于记账录入能力，不应与只读账簿混在同一小增量中。后续如确认需要，应另立导入/制证方案并复用现有手工凭证服务。

## 3. 方案选择

### 3.1 推荐：新增 Script Report，复用标准总账服务函数

`China Daily Ledger.execute(filters)` 在新模块内完成参数归一化和权限校验，然后调用 ERPNext 标准总账的公开 Python 模块能力获取结果。新报表只做字段映射、摘要提取和收支/余额展示，不重写 GL SQL。

推荐原因：

- 标准总账已处理公司权限、财务账簿、取消凭证、期初项、多币种及会计维度等复杂规则。
- 新报表有独立名称、列定义、前端筛选和样式，不会污染所有 `General Ledger` 使用者。
- ERPNext 升级时，只需对新报表中的适配层做兼容检查。
- 新入口可独立删除，回滚成本低。

### 3.2 不采用的方案

| 方案 | 不采用原因 |
| --- | --- |
| 全局 JS 改造 `General Ledger` | 当前已有 `general_ledger_total_row.js` 全局增强；继续叠加日账簿专属布局会影响标准会计总账和其他入口。 |
| 新写 SQL 直接查询 `tabGL Entry` | 容易遗漏标准总账的期初、财务账簿、会计维度、多币种和权限口径。 |
| 新建独立 Page 和白名单 API | 可以高度还原参考图，但重复实现报表导出、打印、列设置和权限，增量明显更大。 |

## 4. 数据与展示口径

### 4.1 筛选字段

| 字段 | 类型 | 默认值/规则 |
| --- | --- | --- |
| 公司 `company` | Link / Company | 用户默认公司，必填。 |
| 财务账簿 `finance_book` | Link / Finance Book | 可空；复用标准总账含默认账簿逻辑。界面显示“账簿”。 |
| 月份 `month` | Data（`YYYY-MM`） | 当前月；改变后同步本期起止日期。 |
| 开始日期 `from_date` | Date | 月初，必填；高级筛选可调整。 |
| 结束日期 `to_date` | Date | 月末或今天，必填。 |
| 科目 `account` | MultiSelectList / Account | 仅返回当前公司科目。 |
| 凭证号 `voucher_no` | Data | 精确匹配，沿用标准总账。 |
| 关键词 `keyword` | Data | 在新适配层对摘要、凭证号、往来名称做包含匹配。 |
| 显示本日小计 `show_daily_subtotal` | Check | 默认关闭；开启后按过账日期插入小计行。 |

公司、财务账簿、日期、科目和凭证号直接映射到标准 `General Ledger` filters。`keyword` 和 `show_daily_subtotal` 是新报表私有参数，不传入老接口。

### 4.2 列定义

| 列 | 来源/规则 |
| --- | --- |
| 日期 | `posting_date`。 |
| 凭证 | `voucher_no`，按 `voucher_type` 链接到原始单据。 |
| 摘要 | 优先 `remarks`；为空时使用凭证类型和凭证号形成简短说明。 |
| 科目 | `account`，保留标准科目 Link。 |
| 往来单位 | `party_name`，为空时使用 `party`；无往来方则留空。 |
| 收入 | 当前 GL 行 `debit`。这是会计借方展示，不等同现金流入分类。 |
| 支出 | 当前 GL 行 `credit`。这是会计贷方展示，不等同现金流出分类。 |
| 余额 | 使用标准总账返回的逐行余额，不在前端重新累计。 |
| 备注 | `remarks` 已作为摘要时，可展示 `against` 或留空，避免重复。 |

“收入/支出”是为了贴近参考图的显示文案；为了避免会计歧义，列头 tooltip 必须说明其实际口径分别为借方发生额和贷方发生额。若业务最终要求真正的现金收支分类，需另行定义现金/银行科目范围和对方科目分类规则。

### 4.3 汇总行

- 月初第一行显示“期初余额”，取标准总账 opening row。
- “本期小计”的收入为明细 `debit` 之和，支出为明细 `credit` 之和。
- 期末余额取最后一条标准总账余额；空结果时沿用期初余额。
- 小计不计入明细数量，不可点击，不参与关键字过滤。
- 导出和打印使用服务端返回的同一组结果，避免页面与文件口径不一致。

## 5. 预期修改文件

| 文件 | 类型 | 修改内容 |
| --- | --- | --- |
| `china_finance/china_finance/report/china_daily_ledger/__init__.py` | 新增 | 报表 Python 包。 |
| `china_finance/china_finance/report/china_daily_ledger/china_daily_ledger.json` | 新增 | Script Report 元数据、模块和角色。 |
| `china_finance/china_finance/report/china_daily_ledger/china_daily_ledger.py` | 新增 | 参数适配、标准总账调用、字段映射、关键词过滤及汇总行。 |
| `china_finance/china_finance/report/china_daily_ledger/china_daily_ledger.js` | 新增 | 紧凑筛选器、月份切换、formatter、凭证链接和局部样式类。 |
| `china_finance/public/css/china_daily_ledger.css` | 新增 | 仅作用于 `.cf-daily-ledger` 的表头、汇总行、工具栏和响应式样式。 |
| `china_finance/hooks.py` | 小改 | 在 `app_include_css` 末尾追加日账簿 CSS，不改变现有资源顺序。 |
| `china_finance/setup/install.py` | 小改 | 在 `BUSINESS_NAVIGATION_GROUPS` 的“账簿”分支追加 `China Daily Ledger`。 |
| `china_finance/china_finance/workspace/china_finance/china_finance.json` | 小改 | 在工作区账簿分组增加报表链接并更新数量。 |
| `china_finance/workspace_sidebar/china_finance.json` | 小改 | 在“会计总账”附近增加“日账簿”侧边栏链接。 |
| `china_finance/china_finance/tests/test_china_daily_ledger.py` | 新增 | 参数映射、权限、期初/明细/汇总、空结果、关键词和财务账簿测试。 |

以上路径均相对于 `development/frappe-bench/apps/china_finance/china_finance/`；其中报表目录实际位于第二层 Python 包 `china_finance/china_finance/report/`。

## 6. 拟修改代码

以下代码用于明确实现边界，实施时需以当前 ERPNext `General Ledger` 返回字段为准补齐适配和测试。

### 6.1 报表元数据

`china_daily_ledger.json`：

```json
{
  "doctype": "Report",
  "name": "China Daily Ledger",
  "report_name": "China Daily Ledger",
  "ref_doctype": "GL Entry",
  "report_type": "Script Report",
  "module": "China Finance",
  "is_standard": "Yes",
  "disabled": 0,
  "roles": [
    {"role": "Accounts User"},
    {"role": "Accounts Manager"},
    {"role": "China Finance Manager"},
    {"role": "China Finance Auditor"}
  ]
}
```

报表标题通过翻译显示“日账簿”；内部标识使用英文，避免路由和模块导入依赖中文名称。

### 6.2 服务端适配骨架

`china_daily_ledger.py`：

```python
import frappe
from frappe import _
from erpnext.accounts.report.general_ledger import general_ledger


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	standard_filters = build_general_ledger_filters(filters)
	_standard_columns, rows = general_ledger.execute(standard_filters)
	data = build_daily_ledger_rows(rows, filters)
	return get_columns(), data


def build_general_ledger_filters(filters):
	return frappe._dict({
		"company": filters.company,
		"finance_book": filters.get("finance_book"),
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"account": filters.get("account") or [],
		"voucher_no": filters.get("voucher_no"),
		"categorize_by": "",
		"include_default_book_entries": 1,
		"show_remarks": 1,
	})
```

实现约束：

- `validate_filters` 校验公司读取权限、日期先后关系和最长查询跨度；建议默认最长 366 天。
- 禁止接收任意 SQL、字段名、排序表达式或未声明过滤条件。
- 不调用 `frappe.db.sql` 重写标准 GL 查询。
- 不改变 `general_ledger.execute()`；新报表只作为调用方。
- ERPNext 标准函数若在升级中发生签名变化，只调整 `build_general_ledger_filters` 适配层。

### 6.3 前端筛选骨架

`china_daily_ledger.js`：

```javascript
frappe.query_reports["China Daily Ledger"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{fieldname: "from_date", label: __("From Date"), fieldtype: "Date", reqd: 1},
		{fieldname: "to_date", label: __("To Date"), fieldtype: "Date", reqd: 1},
		{fieldname: "account", label: __("Account"), fieldtype: "MultiSelectList", options: "Account"},
		{fieldname: "voucher_no", label: __("Voucher No"), fieldtype: "Data"},
		{fieldname: "keyword", label: __("Keyword"), fieldtype: "Data"},
	],
	onload(report) {
		report.page.wrapper.addClass("cf-daily-ledger");
	},
};
```

实施时月份快捷选择应转换为 `from_date/to_date`，而不是新增另一套服务端期间语义。Frappe 自带下载、打印、刷新按钮继续保留；不重复绘制参考图中的同名工具栏。

### 6.4 导航增量

`setup/install.py` 的“账簿”分支追加：

```python
("China Daily Ledger", "日账簿", "Report"),
```

对应 Workspace / Sidebar 链接：

```json
{
  "label": "日账簿",
  "link_to": "China Daily Ledger",
  "link_type": "Report",
  "is_query_report": 1,
  "type": "Link"
}
```

必须复用现有 `sync_navigation_metadata` / `sync_simplified_navigation` 的幂等同步方式，不另写插入数据库的临时脚本。

### 6.5 局部样式

```css
.cf-daily-ledger .dt-header .dt-cell {
	background: var(--subtle-fg);
	font-weight: 600;
}

.cf-daily-ledger .dt-row[data-row-kind="summary"] .dt-cell {
	background: var(--control-bg);
	font-weight: 600;
}

.cf-daily-ledger .report-wrapper {
	min-height: 520px;
}
```

最终选择器需以运行时 DOM 为准。所有规则必须以 `.cf-daily-ledger` 开头；颜色使用 Frappe 主题变量，兼容明暗主题，不覆盖 `.datatable`、`.page-form` 等全局类。

## 7. 调用链路

### 7.1 页面查询链路

```text
用户点击“中国财务 -> 账簿 -> 日账簿”
  -> Frappe Desk 进入 query-report/China Daily Ledger
  -> china_daily_ledger.js 初始化默认公司、本月日期和筛选控件
  -> Frappe 标准 Query Report RPC 调用 China Daily Ledger.execute(filters)
  -> 新报表 validate_filters / build_general_ledger_filters
  -> ERPNext General Ledger.execute(standard_filters)
  -> 标准 GL 权限、财务账簿、期初和总账取数逻辑
  -> 新报表 build_daily_ledger_rows 映射列并生成小计
  -> Frappe DataTable 渲染、格式化、下载或打印
```

### 7.2 数据来源链路

```text
Journal Entry / Sales Invoice / Purchase Invoice / Payment Entry 等提交
  -> ERPNext 原有过账控制器
  -> GL Entry
  -> General Ledger 标准查询逻辑
  -> China Daily Ledger 只读展示
```

日账簿不参与上游单据过账，也不回写任何 GL Entry。

### 7.3 部署链路

```text
bench --site <site> migrate
  -> 同步 Report 元数据
  -> china_finance after_migrate
  -> 同步 Workspace / Workspace Sidebar
  -> bench build --app china_finance
  -> clear-cache
```

## 8. 预期界面效果

页面采用现有 Frappe/ERP 列表视图风格：左侧为中国财务模块导航，顶部保留页签和面包屑，内容区使用紧凑筛选栏、列表视图工具栏和可滚动数据表。整体以白底、浅灰分隔线、标准圆角控件和系统主题色为主，不复刻截图中的品牌 Logo 或第三方顶部导航。

```text
中国财务  日账簿  凭证附件中心  中国结账运行单  中国财务报表  对账单
┌──────────────┬────────────────────────────────────────────────────────────┐
│ 中国财务导航 │ 主页 / 账簿 / 日账簿              [列表视图] [刷新] [...] │
│  账簿         ├────────────────────────────────────────────────────────────┤
│  · 日账簿     │ 公司 [众马公司]  账簿 [默认账簿]  月份 [2026-09]          │
│  · 会计总账   │ 日期 [2026-09-01] 至 [2026-09-30]  [过滤条件] [清除]     │
│  · 对账单     ├────────────────────────────────────────────────────────────┤
│               │ □ 日期  凭证  摘要  科目  往来单位  收入  支出  余额  备注 │
│               │ □ 2026-09-03  JV-00021  收到货款  银行存款  客户甲  8,000 │
│               │ □ 2026-09-03  JV-00021  收到货款  应收账款  客户甲  8,000 │
│               │                 本期小计              8,000  8,000  0 │
│               ├────────────────────────────────────────────────────────────┤
│               │ 每页 20   共 2 条                         [加载更多]     │
└──────────────┴────────────────────────────────────────────────────────────┘
```

### 8.1 视觉规则

- 使用 Frappe 标准列表视图布局：页签、面包屑、筛选器、视图切换、刷新、更多操作和分页位置与现有系统一致。
- 筛选栏采用截图所示的紧凑横向输入框；宽度不足时自动换行，不把筛选条件塞进弹窗。
- 列表首列提供复选框，支持标准列表选择行为；只读日账簿不显示“添加”或批量删除按钮。
- 状态类信息使用系统浅色标签/徽标，金额与日期使用标准列表单元格对齐规则。
- 桌面端金额列右对齐，日期和凭证列固定合理宽度，摘要和科目可弹性扩展。
- 表头吸顶仅在报表内容滚动容器内生效。
- 期初和本期小计使用浅色背景与加粗文字；不使用高饱和整行蓝色。
- 空数据时显示标准空状态，同时保留期初/本期小计为 0。
- 1280px 以下隐藏低优先级“备注”；768px 以下允许横向滚动，列宽不挤压到文字重叠。
- 加载中、请求失败、无权限、日期非法均使用 Frappe 标准提示反馈。

### 8.2 交互规则

- 切换月份自动设置当月起止日期并刷新；手动改日期后月份控件显示对应月份或“自定义”。
- 上一月/下一月只调整筛选，不改变全局系统账期。
- 凭证号可点击并按 `voucher_type` 打开原始单据；无读取权限时不绕过标准权限。
- 关键词输入采用显式查询或 300ms 防抖，避免每次按键立即发请求。
- 下载和打印结果与当前全部筛选结果一致，不只导出屏幕可见行。

### 8.3 状态化预期效果

| 场景 | 预期效果 |
| --- | --- |
| 首次进入 | 自动带出用户默认公司、当前月份和对应日期范围；表格显示加载状态，加载完成后展示期初、明细和本期小计。 |
| 有数据 | 按日期升序显示流水；同一凭证的多条分录保持连续；收入、支出、余额金额右对齐并使用系统币种格式。 |
| 开启本日小计 | 每个过账日明细结束后插入一行“本日小计”，浅色背景加粗显示，不计入明细条数。 |
| 筛选后 | 修改公司、账簿、日期、科目、凭证号或关键词后，表格、期初、本期小计和期末余额同步更新，旧结果不会残留。 |
| 无数据 | 保留表头和筛选条件，显示 Frappe 标准空状态；期初、本期小计和期末余额显示 `0.00`，不显示错误提示。 |
| 查询失败 | 保留当前筛选条件，显示标准错误提示和“重试”操作，不清空已显示的上一份成功结果，避免误认为账务为空。 |
| 无权限 | 不展示越权数据；按 Frappe 标准返回无权限提示，导航入口也应遵循角色可见性。 |
| 导出/打印 | 文件标题为“日账簿”，包含公司、账簿、日期范围和筛选条件；明细、期初和汇总口径与屏幕一致。 |
| 小屏设备 | 筛选器按两列或单列折行，表格保持最小列宽并支持横向滚动；日期、金额和凭证号不重叠。 |

验收时应至少准备一组包含多日期、多凭证、期初余额和空结果的样例数据，逐项核对上述状态，而不能只验证页面是否能打开。

## 9. 受影响模块

| 模块 | 影响 |
| --- | --- |
| China Finance 导航 | “账簿”新增一个 Report 链接，现有“会计总账”等入口不变。 |
| China Finance 报表 | 新增 `China Daily Ledger` 独立报表和测试。 |
| ERPNext Accounts | 仅运行时调用标准 General Ledger Python 模块，不修改其源码。 |
| Frappe Query Report / DataTable | 使用标准渲染、导出、打印和链接格式化。 |
| 静态资源 | 新增一份作用域严格限定的 CSS；构建产物体积小幅增加。 |
| 权限 | 沿用 GL Entry/Accounts 角色与公司权限，不增加匿名或越权入口。 |

明确不受影响：凭证创建与提交、自动过账、冲销、结账、税务发票、对账单、现金流量指定、现有凭证账簿、会计总账接口、数据库表结构。

## 10. 兼容性与风险控制

1. **标准模块内部 API 风险**：`general_ledger.execute` 是报表模块函数，不是稳定的外部 REST 合同。通过单一适配函数隔离，并用回归测试覆盖升级。
2. **重复摘要风险**：必须排除标准总账生成的 Opening/Closing/Total 等展示行后再构建本期小计，避免重复累计。
3. **余额口径风险**：余额必须取标准总账行结果，禁止简单累加余额列。
4. **多科目余额语义**：选择多个科目或不选科目时，“余额”是标准总账当前分组口径，不应表述为单一现金余额。
5. **性能风险**：默认查询一个月，限制最长 366 天；关键词过滤尽量在已授权结果集上完成，数据量验证后再决定是否增加兼容的服务端条件。
6. **样式污染风险**：CSS 全部限定 `.cf-daily-ledger`，不复用或覆盖现有 `general_ledger_total_row.js` 的选择器。
7. **全局增强叠加风险**：现有 `general_ledger_total_row.js` 必须以路由名严格判断只增强 `General Ledger`，不得误命中 `China Daily Ledger`。

## 11. 测试与验收

### 11.1 自动化测试

- 必填公司、日期顺序、最长跨度和无权限公司校验。
- 财务账簿过滤及 `include_default_book_entries` 行为。
- 单科目、多科目、凭证号和关键词过滤。
- 期初行识别、收入/支出合计、期末余额及空结果。
- 已取消凭证、期初凭证和多币种场景与标准 General Ledger 对照。
- 原始凭证链接类型和名称正确。
- 标准 `General Ledger` 测试继续通过，证明老报表未被改变。

### 11.2 页面验收

- 中国财务工作区主体和左侧导航的“账簿”均显示“日账簿”，重复迁移不产生重复入口。
- 默认打开本月数据，公司和账簿切换后数据正确刷新。
- 列顺序、汇总行、金额格式、空状态与本文线框图一致。
- 下载、打印与当前筛选口径一致。
- 1440x900、1280x720、768x1024 和 390x844 下无文字重叠或控件遮挡。
- 明暗主题下表头、边框、汇总行对比度正常。
- Administrator、Accounts User 和仅有无关角色的用户分别验证可见性与权限拒绝。

### 11.3 实施验证命令

```bash
bench --site aki_test.localhost run-tests --app china_finance \
  --module china_finance.china_finance.report.china_daily_ledger
bench build --app china_finance
bench --site aki_test.localhost migrate
bench --site aki_test.localhost clear-cache
```

实施后使用 Playwright 对上述桌面/移动视口截图，并核对浏览器控制台无报错、报表请求只触发一次、下载文件包含完整筛选结果。

## 12. 实施顺序

1. 新增报表 JSON/Python/JS 和后端单元测试，先验证与标准 General Ledger 的数据口径一致。
2. 新增局部 CSS，完成桌面和移动布局。
3. 在 `BUSINESS_NAVIGATION_GROUPS` 新增日账簿分支，同步 Workspace 与 Sidebar fixture。
4. 检查 `general_ledger_total_row.js` 路由判断，确认不会作用于新报表；只有判断不严格时才做最小修正。
5. 构建、迁移、清缓存，执行自动化和视觉验收。
6. 验收通过后另写实施沉淀，记录最终文件、接口差异和截图。

## 13. 回滚方案

回滚时移除“日账簿”导航项、Report 元数据目录、局部 CSS 引用和对应测试，然后重新执行 migrate/build/clear-cache。由于本方案不新增业务表、不写入账务数据、不修改老接口，回滚不会影响历史凭证和 GL Entry。

## 14. 待业务确认

- 页面列名是否确定使用“收入/支出”，还是采用会计语义更准确的“借方/贷方”。本文默认保留参考图文案，并增加口径提示。
- “日账簿”是否只允许查看现金/银行科目。本文默认查看全部总账流水；若限定现金类科目，需要明确科目识别规则。
- 本期是否需要真正的“收支大类/收支类型”。本文默认不增加，避免无可靠数据来源时产生误导。
- 导入日记账、生成凭证、批量删除是否进入后续独立需求。本文明确不包含写操作。
