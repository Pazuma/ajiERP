# 中国财务“凭证汇总表”方案

> 状态：方案沉淀，暂不修改业务代码  
> 版本：v0.1  
> 目标站点：`aki_test.localhost`

## 1. 目标与原则

在中国财务模块新增“凭证汇总表”，呈现众马会计式的科目借贷汇总，并支持按月份区间或自定义日期区间查询。本阶段只沉淀设计，不执行迁移、接口或前端改动。

- 小增量：新增页面和查询分支，保持现有凭证快照、生成服务和“查凭证”报表不变。
- 数据一致：以已生成的 `China Accounting Voucher` 快照为报表事实来源，不重新从业务单据推导金额。
- 兼容优先：不修改 `create_voucher_from_source`、`on_gl_source_submit`、`China Voucher Ledger` 的既有参数和返回格式。
- 权限继承：沿用中国财务报表的角色和公司权限校验。

## 2. 参考样式拆解

页面位于“凭证”分类，标题为“凭证汇总表”。顶部提供模糊搜索、科目分类小计开关、下载和打印；主体为白色表格区，蓝色表头，列为“科目编码、科目名称、借方金额、贷方金额”，并显示凭证数、附单据数和合计。右侧为起止月份选择器（如 `2026-08` 至 `2026-08`），同时允许切换到自定义起止日期。无数据时显示空状态，不改变表格尺寸。

## 3. 一期功能需求

1. 公司、起止月份为必填；月份转换为该月第一天至最后一天，采用闭区间。
2. 自定义日期模式支持 `from_date`、`to_date`，校验开始日期不晚于结束日期。
3. 按科目聚合借方、贷方；可按科目编码或名称排序。
4. 顶部统计：去重后的凭证数、附件张数合计、借贷合计。
5. 模糊搜索覆盖凭证字号、来源单号、摘要、科目编码/名称、金额（金额搜索可作为后续优化）。
6. “显示科目分类小计”打开时按 Account 科目树的父级/分类增加小计行；若当前科目树接口不足，一期先保留开关和明细汇总，分类小计列为二期。
7. 下载导出 CSV/XLSX，打印使用独立打印格式；均新增接口，不改旧报表接口。
8. 点击科目或统计数字可跳转/钻取到现有“查凭证”或凭证快照列表（一期可先提供链接参数）。

## 4. 现有数据来源与表关系

现有链路为：

```text
Journal Entry / Payment Entry / 其他 GL 来源
  -> GL Entry
  -> china_finance.services.voucher.on_gl_source_submit
  -> create_voucher_from_source
  -> China Accounting Voucher（凭证头、日期、字号、附件数、合计）
  -> China Accounting Voucher Entry（科目、借贷、辅助核算）
```

汇总查询建议连接：

```text
China Accounting Voucher v
  INNER JOIN China Accounting Voucher Entry e ON e.parent = v.name
  LEFT JOIN Account a ON a.name = e.account
```

过滤 `v.company`、`v.posting_date`、`v.docstatus=1`。是否仅包含 `Journal Entry`/`Payment Entry` 应做成配置或筛选项，默认与现有“查凭证”一致；不能静默改变快照口径。凭证数按 `COUNT(DISTINCT v.name)`，附件数优先使用 `v.attachment_count`；若电子档案关联成为权威来源，需在实施前确认统计口径。

## 5. 计划新增/最小修改文件

| 文件 | 计划变更 | 说明 |
|---|---|---|
| `china_finance/page/china_voucher_summary/china_voucher_summary.json` | 新增 | 页面元数据与权限入口 |
| `china_finance/page/china_voucher_summary/china_voucher_summary.js` | 新增 | 月份/日期控件、筛选、表格、下载打印、空状态 |
| `china_finance/public/css/china_voucher_summary.css` | 新增 | 页面局部样式，复用 Frappe 变量，不污染旧页面 |
| `china_finance/services/voucher_summary.py` | 新增 | 白名单查询、聚合、统计、导出数据；独立参数对象 |
| `china_finance/china_finance/report/china_voucher_summary/` | 新增（可选） | 若采用 Query Report，则放置 JSON/Python/JS；与页面二选一，优先独立 Page 以匹配截图交互 |
| `china_finance/china_finance/workspace/china_finance/china_finance.json` | 最小修改 | 在“日常工作/凭证”下增加“凭证汇总表” Page 链接 |
| `china_finance/hooks.py` | 原则上不改 | 仅在静态资源需要全局声明时增加最小资源项，默认使用页面按需加载 |
| `china_finance/tests/test_voucher_summary.py` | 新增 | 日期边界、权限、聚合、去重、空结果和搜索测试 |

不修改：`services/voucher.py`、`services/manual_voucher.py`、两个凭证 DocType 结构、现有 `china_voucher_ledger` 接口及其调用方。

## 6. 建议接口与字段

新增 `@frappe.whitelist()` 方法（名称可最终按项目约定调整）：

- `get_voucher_summary(filters)`：返回 `columns`、`rows`、`totals`、`applied_filters`。
- `export_voucher_summary(filters, format)`：复用同一查询服务，输出 CSV/XLSX 文件。
- `get_voucher_summary_print(filters)`：生成独立打印上下文或 HTML。

请求字段：`company`、`period_mode`（month/custom）、`from_month`、`to_month`、`from_date`、`to_date`、`search_text`、`show_account_category_subtotal`、可选 `voucher_status`/`account`。响应行字段：`account`、`account_code`、`account_name`、`debit`、`credit`、`is_subtotal`、`parent_account`。

## 7. 调用链路

```text
用户打开 Page
  -> JS 设置公司和月份默认值
  -> frappe.call(get_voucher_summary, filters)
  -> voucher_summary.py 校验权限/日期并构造参数化 SQL
  -> v + e (+ a) 聚合
  -> 返回科目行与 totals
  -> JS 渲染表格、分类小计、统计栏
  -> 下载/打印调用同一服务的独立输出分支
```

## 8. 受影响模块

- 中国财务：新增查询页面、工作区导航、报表权限。
- 凭证快照：只读消费，不改变生成、冲销和同步异常处理。
- 会计科目：读取科目编码、名称、父级和分组标识。
- 电子会计档案：仅影响附件数统计口径确认，不在一期修改档案逻辑。
- 现有“查凭证”：提供钻取目标和筛选参数，不改变其结果格式。

## 9. 权限、性能与安全

服务端必须校验公司读取权限及报表角色（`Accounts User`、`Accounts Manager`、`China Finance Manager`、`China Finance Auditor`、`System Manager`，最终以现有报表权限为准），SQL 使用参数绑定，禁止前端拼接条件。对日期和公司建立/确认索引使用情况；大期间查询采用分页或限制最大跨度并提示用户。导出与页面查询必须复用同一权限和过滤逻辑。

## 10. 测试与验收

- 单月、跨月、自定义日期：边界日期包含且跨年正确。
- 借贷聚合与总计和明细一致；同一凭证多行只计一次凭证数。
- 空结果、撤销/草稿状态、公司隔离、无权限访问均符合预期。
- 科目搜索、摘要搜索、分类小计开关、导出和打印内容一致。
- 不影响新增凭证、凭证冲销快照、同步异常重试和现有“查凭证”回归测试。

## 11. 分阶段实施与回滚

阶段一：新增查询服务、Page、样式和工作区入口，完成月份/自定义日期、科目汇总和统计。  
阶段二：补充科目分类小计、钻取、导出和打印格式。  
阶段三：按使用反馈增加缓存、分页、金额搜索和电子档案附件口径。

回滚仅需移除新增 Page、服务、测试和工作区链接；不涉及数据表迁移，不回滚既有凭证快照或老接口。

## 12. 预期效果

用户可在中国财务的“凭证”分类中直接打开“凭证汇总表”，选择一个月、连续月份或任意日期范围，快速看到按科目的借贷发生额、凭证数和附件数，并可下载、打印或钻取明细。现有凭证生成、查询和审计链路保持兼容，新增能力可独立发布和回滚。
