# 中国财务测试问题小增量修复方案

## 1. 目标与约束

本方案处理中国财务验收发现的五类问题：

1. 累计折旧科目产生错误的现金流建议。
2. 新公司初始化测试缺少 `All Departments` 根部门。
3. Playwright 页面审计产生大量未分类的 HTTP/浏览器错误。
4. 发票识别入口与旧 Playwright 脚本不兼容。
5. 目标公司现金流量指定配置不完整。

实施原则：

- 小增量修改，不重构现有凭证、总账、报表和税务服务。
- 保留现有白名单方法、DocType 名称、返回结构和页面路由。
- 优先在已有入口前增加校验分支，或新增测试/诊断分支。
- 配置问题通过设置和配置完整性检查解决，不在代码中硬编码公司和日期。
- 每个修复都必须有自动化测试和 Playwright 复测证据。

## 2. 总体调用链路

```text
Company / Account / China Finance Settings
    -> 中国财务初始化和模板同步
    -> Journal Entry / GL Entry
    -> China Accounting Voucher
    -> China Cash Flow Assignment
    -> China Financial Statements

China Tax Invoice 表单
    -> hooks.py doctype_js
    -> china_tax_invoice_form_recognition.js
    -> frappe.ui.Dialog / Attach
    -> recognize_invoice_for_form（老接口保持不变）
    -> China Tax Invoice / Item / Recognition

Playwright 页面审计
    -> 登录
    -> DocType/Report 页面
    -> response/console/pageerror 采集
    -> 去重与严重级别分类
    -> 测试执行报告
```

## 3. 修复一：累计折旧现金流建议

### 3.1 根因

`requires_manual_cash_flow_assignment()` 已将 `1602`、`1702` 等前缀定义为不能从科目编号自动推导现金流的非现金科目，但 `classify_account_number(number, "Cash Flow", account)` 没有在 Cash Flow 分支入口复用该判断。

因此 `160201` 后续命中固定资产范围规则，返回：

```text
('CASH_PAID_LONG_TERM_ASSETS',
 'CASH_RECEIVED_ASSET_DISPOSAL',
 'CASH_PAID_LONG_TERM_ASSETS')
```

### 3.2 建议代码修改

修改文件：

- `china_finance/setup/templates.py`
- `china_finance/tests/test_china_coa_profile.py`

在 Cash Flow 分支增加早返回，不改变函数签名或现有返回结构：

```python
if statement_type == "Cash Flow":
    if account and account.account_type in {"Cash", "Bank"}:
        return None
    if requires_manual_cash_flow_assignment(number):
        return None
    # 保留现有编号映射分支
```

新增或细化测试：

```python
def test_non_cash_adjustment_accounts_have_no_cash_flow_suggestion(self):
    for number in ("1231", "1471", "160201", "170201", "510102", "510105"):
        self.assertIsNone(classify_account_number(number, "Cash Flow", account))
```

### 3.3 调用链路

```text
科目模板/公司初始化
    -> classify_account_number
    -> China Financial Statement Mapping
    -> cash_flow_assignment._suggestion_by_account
    -> get_cash_legs_for_voucher
    -> 现金流量指定单建议
```

### 3.4 预期效果

- 累计折旧、减值准备、折旧摊销等非现金科目不再自动给出现金流建议。
- 有现金腿的复杂业务仍可在 `China Cash Flow Assignment` 中人工指定。
- 现有现金、银行、销售、采购和投融资映射不变。
- 原白名单接口和报表接口不变。

### 3.5 受影响模块

- 中国会计科目模板初始化
- 财务报表映射
- 现金流量指定建议
- 现金流量表

不影响：Journal Entry、GL Entry、凭证提交、税务发票和对账接口。

## 4. 修复二：新公司初始化缺少根部门

### 4.1 根因

日志来自 ERPNext `Company.create_default_departments()`。它先尝试创建全局根部门 `All Departments`，随后创建公司子部门。测试数据库可能存在翻译、残留树结构或根节点被删除，导致条件判断和实际 Link 名称不一致。

该问题发生在 ERPNext 标准公司初始化链路，不应直接修改 ERPNext 老接口。

### 4.2 推荐小增量方案

优先只改测试 fixture，不修改 ERPNext：

修改文件：

- `china_finance/tests/test_china_coa_profile.py`
- 可新增 `china_finance/tests/utils.py` 中的测试辅助函数

新增测试前置分支：

```python
def ensure_department_root():
    root = frappe.db.exists("Department", {"is_group": 1, "parent_department": ["is", "not set"]})
    if not root:
        frappe.get_doc({
            "doctype": "Department",
            "department_name": _("All Departments"),
            "is_group": 1,
        }).insert(ignore_permissions=True)
```

然后在新公司初始化测试开始前调用，测试结束时只清理由该测试创建且无引用的 fixture。

若真实用户创建公司也能复现，再新增 China Finance 安装前置校验，不覆盖 ERPNext 方法：

```text
initialize_company
    -> ensure_required_erpnext_roots（新增私有辅助函数）
    -> 原 initialize_company 逻辑
```

### 4.3 预期效果

- 自动化测试不再出现被忽略的 LinkValidationError。
- 新公司测试结果能真实代表初始化完整性。
- 不覆盖 `Company.create_default_departments()`，降低 ERPNext 升级风险。

### 4.4 受影响模块

- China Finance 集成测试
- 可选的新公司中国财务初始化前置检查

不影响：已有公司、部门业务、员工、凭证和报表。

## 5. 修复三：页面审计错误分类

### 5.1 根因

当前脚本把每次页面加载中的所有 `response.status >= 400`、console error 和 pageerror 直接追加。相同静态资源在 41 个 DocType 和 11 个报表中重复请求，所以“158”是事件数量，不是 158 个独立缺陷。

### 5.2 建议代码修改

修改文件：

- `docs/playwright_china_finance_full_audit.mjs`

新增结构化采集函数，不改变业务代码：

```javascript
function classifyFailure(event) {
    if (event.type === "pageerror") return "frontend-runtime";
    if (event.status >= 500) return "server";
    if (event.url.includes("/api/method/")) return "api";
    if (event.url.includes("/assets/")) return "asset";
    return "route-or-other";
}
```

记录字段：

```text
method, url, status, resourceType, pageUrl,
responseBody, category, occurrenceCount, firstSeenPage
```

按 `method + url + status` 去重，并新增严重级别：

- P0：关键业务接口 5xx、页面不可用。
- P1：业务接口 404/403、列表或报表无法加载。
- P2：非关键静态资源 404。
- P3：浏览器扩展、开发提示或可忽略预加载错误。

输出两个文件：

- `page-audit.json`：原始事件，保留兼容。
- `page-audit-summary.json`：新增去重分类结果。

### 5.3 预期效果

- 158 个事件被归并为可处理的唯一问题清单。
- 能快速区分代码错误、权限问题、资源构建问题和非阻断噪声。
- 原始证据格式继续保留，不影响已有报告引用。

### 5.4 受影响模块

- Playwright 测试工具
- 测试执行报告
- CI/验收门禁

不影响任何业务 DocType、接口或数据库。

## 6. 修复四：发票识别入口和测试兼容

### 6.1 现有调用链路

```text
hooks.py
    -> doctype_js["China Tax Invoice"]
    -> public/js/china_tax_invoice_form_recognition.js
    -> refresh 注册“发票操作/识别发票”
    -> open_recognition_dialog
    -> frappe.ui.Dialog + Attach 字段
    -> recognize_invoice_for_form
    -> apply_recognition_result
```

后端接口无需修改：

```text
china_finance.services.invoice_recognition.recognize_invoice_for_form
```

### 6.2 根因方向

前端源码明确会创建 `frappe.ui.Dialog`，当前 Playwright 点击后却没有弹窗。优先排查：

1. 页面是否加载到最新构建的 `doctype_js` 资源。
2. 自定义按钮是否来自重复注册或旧缓存。
3. 点击定位是否点中了菜单组而不是菜单项。
4. Attach 控件是否在 Dialog 显示后异步渲染。

### 6.3 推荐修改

第一阶段只改测试，不改业务接口：

修改文件：

- `docs/playwright_invoice_ocr_ui.mjs`

调整为：

```javascript
await page.goto(`${baseUrl}/desk/china-tax-invoice/view/list`);
await page.getByRole("button", { name: /添加|新建/ }).click();
await page.waitForURL(/\/desk\/china-tax-invoice\/new-/);
await page.getByRole("button", { name: "发票操作" }).click();
await page.locator(".dropdown-menu:visible").getByText("识别发票", { exact: true }).click();
const dialog = page.locator(".modal:visible");
await dialog.getByText("上传并识别发票", { exact: true }).waitFor();
```

Attach 字段不要依赖普通可见 input。优先使用 Frappe Attach 控件按钮和 `filechooser`：

```javascript
const chooserPromise = page.waitForEvent("filechooser");
await dialog.getByText(/添加文件|上传/).click();
const chooser = await chooserPromise;
await chooser.setFiles(invoiceFile);
```

若确认业务 JS 未加载，再做最小业务修复：

- 保留 `hooks.py` 的 `doctype_js` 注册；
- 检查 build 产物和缓存；
- 只在 `china_tax_invoice_form_recognition.js` 增加可测试的 `data-action` 或稳定类名；
- 不修改 `recognize_invoice_for_form` 参数和返回值。

### 6.4 预期效果

- 用户仍按原入口操作，不新增重复按钮。
- 测试适配 Frappe 当前 Desk 路由和 Attach 控件。
- OCR、人工回填、税务查验三种状态继续相互独立。
- 老后端接口和已有业务数据不受影响。

### 6.5 受影响模块

- 中国税务发票表单
- 发票识别 Playwright 测试
- 前端资源构建/缓存

不影响：税务发票数据模型、识别服务合同、抵扣、对账和凭证接口。

## 7. 修复五：现金流量指定配置完整性

### 7.1 根因

`is_direct_assignment_required(company, posting_date)` 只有在以下条件同时满足时返回真：

```text
China Finance Settings 存在
cash_flow_assignment_activation_date 非空
posting_date >= activation_date
```

目标公司 `阿基视觉（东莞）` 的启用日期为空，因此不自动要求或创建现金流指定单。这是配置状态，不应通过代码硬编码修复。

### 7.2 配置修复

用户操作：

```text
中国财务 -> 设置 -> 中国财务设置
    -> 公司：阿基视觉（东莞）
    -> 现金流量指定启用日期：由财务负责人确认
    -> 确认现金流模板和现金等价物范围
    -> 保存
```

建议测试环境使用已知未结账日期，例如 `2026-09-01`，但正式启用日期必须由财务负责人确认。

### 7.3 建议新增代码分支

不改变 `is_direct_assignment_required()` 老接口，新增只读配置检查方法：

修改文件建议：

- `china_finance/services/cash_flow_assignment.py`
- `china_finance/public/js/china_finance_settings.js`
- 新增相应测试文件或现有现金流测试

新增方法示例：

```python
@frappe.whitelist()
def get_cash_flow_configuration_status(company):
    return {
        "configured": bool(activation_date and template and cash_scope),
        "activation_date": activation_date,
        "has_template": bool(template),
        "cash_scope_count": len(cash_scope),
        "missing": missing,
    }
```

设置页面只读展示：

```text
现金流配置：完整 / 不完整
缺少：启用日期、模板、现金等价物范围
```

该方法只提供诊断，不改变现有自动创建和确认接口。

### 7.4 调用链路

```text
China Finance Settings
    -> is_direct_assignment_required
    -> create_assignment_if_required
    -> China Cash Flow Assignment
    -> confirm_cash_flow_assignment
    -> get_confirmed_cash_flow_values
    -> China Financial Statements
```

### 7.5 预期效果

- 配置不完整时，用户能在设置页提前看到原因。
- 启用日期之前的历史凭证不受影响。
- 启用日期之后的现金类凭证按现有逻辑创建指定单。
- 老接口、历史指定单和报表返回结构不变。

### 7.6 受影响模块

- 中国财务设置
- 现金流量指定单
- 现金流量表和覆盖率
- 结账前现金流检查

不影响：凭证过账本身、GL Entry、税务发票和对账。

## 8. 文件修改汇总

| 文件 | 修改类型 | 用途 |
| --- | --- | --- |
| `china_finance/setup/templates.py` | 小改 | Cash Flow 分支统一排除非现金科目 |
| `china_finance/tests/test_china_coa_profile.py` | 小改 | 增加非现金科目回归和根部门 fixture |
| `china_finance/tests/utils.py` | 可选新增 | 复用测试环境根部门准备逻辑 |
| `docs/playwright_china_finance_full_audit.mjs` | 小改 | 错误去重、分类和分级 |
| `docs/playwright_invoice_ocr_ui.mjs` | 小改 | 适配当前 Desk 路由和 Attach 控件 |
| `china_finance/services/cash_flow_assignment.py` | 可选新增分支 | 新增只读配置完整性接口 |
| `china_finance/public/js/china_finance_settings.js` | 可选小改 | 展示现金流配置状态，不改保存接口 |

上述路径中的 `china_finance/` 均相对于 `development/frappe-bench/apps/china_finance/china_finance/`。

## 9. 兼容性与风险控制

### 保持不变

- `classify_account_number()` 的函数签名。
- `recognize_invoice_for_form` 的方法路径、参数和响应结构。
- `is_direct_assignment_required()`、`create_assignment_if_required()` 和确认/作废接口。
- Journal Entry、GL Entry、中国凭证、发票、对账和报表 DocType。
- 历史凭证、历史现金流指定和历史发票数据。

### 风险

- 非现金科目早返回可能减少现有自动现金流建议；这是预期修正，但需用完整科目表回归。
- 测试 fixture 若清理不严谨可能影响共享测试数据；只清理由本测试创建且无引用的根节点。
- 前端构建缓存可能掩盖发票 JS 修改；复测前执行 `bench build --app china_finance` 和站点 `clear-cache`。
- 现金流启用日期属于会计政策，不能由开发人员替财务负责人决定。

## 10. 实施顺序

1. 修复累计折旧早返回并运行全部 53 项应用测试。
2. 增加测试根部门 fixture，确认初始化日志无 LinkValidationError。
3. 改进 Playwright 错误分类，得到唯一 URL 清单。
4. 只改 OCR Playwright 脚本，验证当前业务 JS 是否正常。
5. 若业务 JS 确认未加载，再做最小前端资源/选择器修复。
6. 财务负责人补齐目标公司现金流配置。
7. 运行真实凭证、现金流、发票、对账和结账验收。
8. 将结果写入 `52-china-finance-test-execution-report.md`。

## 11. 验收标准

- China Finance 自动化测试全部通过，无被忽略的 LinkValidationError。
- 非现金科目不产生自动现金流建议。
- 页面审计输出唯一错误 URL、类别、次数和严重级别。
- 发票识别弹窗能通过真实用户入口打开，附件上传和回填成功。
- 目标公司现金流配置状态明确，启用日期后凭证能生成指定单。
- Journal Entry、GL Entry、中国凭证、现金流指定和报表金额一致。
- 未新增重复业务接口，老接口调用方无需修改。

## 12. 回滚方案

- `templates.py` 的早返回为单点修改，可独立回滚。
- 测试 fixture 和 Playwright 脚本不影响生产运行，可独立移除。
- 配置状态接口为新增只读分支，可删除而不影响老接口。
- 现金流启用日期若配置错误，应通过设置页按会计政策调整，不直接改数据库。
- 不删除或重写历史中国凭证、现金流指定、税务发票和报表快照。

