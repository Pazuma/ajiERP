# 中国财务测试问题修复实施记录

## 1. 实施范围

本记录对应 [53-china-finance-test-findings-fix-plan.md](53-china-finance-test-findings-fix-plan.md)，覆盖五项验收问题：累计折旧现金流建议、公司初始化根部门、页面审计错误分类、发票识别入口兼容、现金流量指定配置诊断。

实施约束：小增量、保持旧接口和 DocType 不变；配置诊断只读，不替财务负责人写入启用日期；未验证通过的流程明确标记为阻塞或待人工复测。

## 2. 已修改文件

| 文件 | 修改 | 影响 |
| --- | --- | --- |
| `apps/china_finance/china_finance/setup/templates.py` | Cash Flow 分类入口排除现金以外的手工指定科目 | 科目映射、现金流建议 |
| `apps/china_finance/china_finance/tests/test_china_coa_profile.py` | 增加非现金回归用例；集成测试前置补齐精确的 `All Departments` 根节点 | 仅测试环境和自动化回归 |
| `apps/china_finance/china_finance/services/cash_flow_assignment.py` | 新增 `get_cash_flow_configuration_status` 只读白名单方法 | 设置页诊断、现金流配置检查 |
| `apps/china_finance/china_finance/public/js/china_finance_settings.js` | 设置页增加现金流量指定配置状态区块 | 中国财务设置页面 |
| `docs/playwright_china_finance_full_audit.mjs` | 保留原始事件，增加 URL/方法/资源类型、分类、严重级别和去重汇总 | 测试工具，不影响业务 |
| `docs/playwright_invoice_ocr_ui.mjs` | 适配 Desk 路由、识别菜单、弹窗和异步文件输入 | 测试工具，不改识别接口 |

## 3. 调用链路与实现效果

### 3.1 累计折旧现金流建议

```text
科目模板 -> classify_account_number
         -> requires_manual_cash_flow_assignment
         -> 报表映射/现金流指定建议
```

`classify_account_number(number, "Cash Flow", account)` 的签名和返回结构未变。现金、银行科目继续按原逻辑处理；`160201`、`170201`、`1231`、`1471`、`510102`、`510105` 等非现金调整科目现在返回 `None`，由现金流量指定单人工指定现金腿。

### 3.2 新公司初始化

ERPNext 标准公司钩子使用精确名称 `All Departments` 查找全局根部门。测试在创建公司前只在缺失时插入该测试前置节点，未修改 ERPNext `Company.create_default_departments()`。本次集成测试通过，未再出现原先的 `Could not find Parent Department` 错误。

### 3.3 页面审计

```text
登录 -> DocType/Report 页面 -> response/console/pageerror 采集
     -> 按类型、方法、状态、URL、消息去重
     -> page-audit.json + page-audit-summary.json
```

原始事件文件继续保留；新增汇总文件不改变旧证据格式。本次运行结果：151 个事件、103 个唯一问题。分类汇总如下：

| 类别 | 唯一数 | 事件数 |
| --- | ---: | ---: |
| route-or-other | 2 | 43 |
| browser-console | 46 | 47 |
| frontend-runtime | 53 | 59 |
| api | 1 | 1 |
| server | 1 | 1 |

严重级别唯一问题：P0 1 个、P1 54 个、P2 48 个。具体 URL、首次页面和出现次数见 `docs/china-finance-test-evidence/page-audit-summary.json`。P0/P1 仍需按 URL 逐项处理，分类本身不等于缺陷已修复。

### 3.4 发票识别入口

```text
Desk 发票列表 -> 新建 China Tax Invoice
               -> 发票操作/识别发票
               -> 上传并识别发票 Dialog
               -> recognize_invoice_for_form（原接口不变）
```

脚本已不再依赖旧 `/app/...` 路由，也不再只查 Dialog 内的普通文件输入；它会兼容全页面异步渲染的 `input[type=file]`。实际复测已成功进入识别弹窗，但当前无头环境下 Frappe Vue `FileUploader` 未生成可注入的文件输入，自动上传步骤未完成。因此本项状态为“入口修复完成，附件上传待真实浏览器人工复测”，没有声称识别回填通过，也没有提交测试发票业务数据。

### 3.5 现金流量指定配置诊断

新增只读链路：

```text
China Finance Settings 页面
    -> get_cash_flow_configuration_status(company)
    -> get_company_settings
    -> get_template(Cash Flow)
    -> get_cash_scope_accounts
    -> 返回 configured / missing / counts
```

旧的 `is_direct_assignment_required`、`create_assignment_if_required`、确认和报表接口均未修改。对 `阿基视觉（东莞）` 的实际调用结果：

```json
{
  "configured": false,
  "activation_date": null,
  "has_template": true,
  "cash_scope_count": 2,
  "missing": ["cash_flow_assignment_activation_date"]
}
```

该结果说明代码链路正常，剩余问题是会计配置。启用日期必须由财务负责人确认后在设置页保存，实施过程没有自动写库。

## 4. 自动化验证记录

### 4.1 语法与静态检查

- `python3 -m py_compile`：通过。
- `git diff --check`：通过。

### 4.2 中国财务应用测试

命令：

```bash
bench --site aki_test.localhost run-tests --app china_finance
```

结果：43 个单元测试通过；1 个集成测试通过；7 个未分类测试通过；3 个旧 Frappe 分类测试通过，合计 54 项通过。测试前临时启用 `allow_tests`，完成后已恢复为 `false`。

重点回归：`test_non_cash_adjustment_accounts_have_no_cash_flow_suggestion`、`test_new_company_initialization_uses_numbered_profile` 均通过。

### 4.3 配置诊断接口

通过 `bench execute` 对目标公司调用成功，准确返回缺失启用日期；未产生设置、凭证、现金流量指定单或业务数据写入。

### 4.4 Playwright 页面审计

已生成并同步：

- `docs/china-finance-test-evidence/page-audit.json`
- `docs/china-finance-test-evidence/page-audit-summary.json`

本次统计以汇总文件为准，原始 158 事件与本次 151 事件的差异来自页面加载时序和错误事件数量波动，不能直接视为缺陷数量变化。

## 5. 人工测试流程

1. 以管理员或中国财务管理员登录 `http://aki_test.localhost:8300`。
2. 打开“中国财务设置”，选择 `阿基视觉（东莞）`，确认“现金流量指定配置”显示“待处理”，缺少项为启用日期；确认模板和现金范围数量为已配置状态。
3. 由财务负责人确定正式启用日期后，在设置页保存；不要直接修改数据库。
4. 新建一张测试收款或付款凭证，日期设置为启用日期之后，提交后打开对应“中国会计凭证”，确认能创建“现金流量指定单”。
5. 在指定单中检查现金总账分录、方向、金额和对方科目；选择与方向匹配的现金流量项目后提交确认。
6. 打开现金流量表，核对已确认指定金额与现金 GL 分录一致；内部转账应选择内部资金划转，不进入现金流量表。
7. 打开“中国税务发票”列表，点击新建 -> “发票操作” -> “识别发票”；选择真实测试 PDF，确认附件上传、识别结果人工核对后再保存。测试 PDF 必须为测试数据库允许的发票样本，不能把生产票据上传到测试站点。
8. 运行页面审计并按 `page-audit-summary.json` 的 P0/P1 URL 分类处理；静态资源 404 不能与业务 API 500 混为一类。

## 6. 遗留问题与后续优化

| 问题 | 当前状态 | 解决方法 |
| --- | --- | --- |
| 页面审计仍有 1 个 P0、54 个 P1 | 已分类，未逐项修复 | 按汇总 URL 检查 API 权限、前端异常和服务端日志，先处理 P0，再处理阻断列表/报表的 P1 |
| 发票 Vue 上传器无头模式未完成 | 自动化未通过 | 使用带真实浏览器文件选择能力的 Playwright 运行器，或为测试脚本增加 Frappe FileUploader 的稳定测试钩子；不得改动识别接口合同 |
| 目标公司启用日期为空 | 代码已诊断，配置未完成 | 财务负责人确认日期后在设置页保存，再执行真实凭证和结账前覆盖率测试 |
| `All Departments` 测试前置依赖 ERPNext 标准实现 | 集成测试通过 | 保持测试 fixture；若生产创建公司仍复现，应单独提交 ERPNext 兼容补丁，不在中国财务应用中覆盖标准方法 |

## 7. 兼容性与回滚

旧白名单方法、参数、返回结构、DocType、路由和历史数据均未改变。新增诊断方法和设置页区块可独立移除；页面审计和发票脚本只属于测试工具；累计折旧修复可通过恢复 Cash Flow 分支的新增早返回独立回滚。现金流启用日期错误时，应通过设置页按会计政策调整，不删除历史凭证或现金流量指定单。

