# 中国财务表单数据流审计与增量优化方案

> 审计日期：2026-09-11  
> 本阶段仅检查与沉淀方案，不修改业务代码。结论来自 DocType、表单脚本、服务层、hooks 和关联 ERPNext 单据的静态调用链审查；涉及生产数据质量的项目需在实施前用脱敏数据验证。

## 1. 审计范围

覆盖中国财务主要表单链路：

- 法定凭证、手工凭证草稿、现金流量指定和凭证同步异常；
- 客户/供应商/银行对账、对账差异和销售结算；
- 税务发票、发票识别、开票申请、进项抵扣批次；
- 财务报表模板、科目映射、附注、前期差错、结账运行和报表快照；
- Sales Order、Delivery Note、Sales Invoice、Purchase Invoice、Payment Entry、GL Entry、Period Closing Voucher 等 ERPNext 来源单据。

## 2. 总体结论

核心服务能力大多已经存在，主要缺口是“数据已经在后端产生，但没有完整流转到表单、来源单据或下一处理入口”。建议采用小增量方式补齐展示、导航、状态同步和汇总，不重写服务，不更改已有白名单接口参数。

优先级定义：P0 为金额或状态可能误导；P1 为流程无法从表单完整操作；P2 为可追溯性和操作效率问题。

## 3. 已确认缺口与优化方案

### P0-1 客户对账的发票结算信息未形成完整双向链路

现状：Ledger 明细以 `GL Entry` 为主，销售发票、收款分摊、订单和送货关系依赖后续 enrich。历史实现未为结算字段赋值；当前增量实现已开始补齐，但仍需覆盖退款、贷项、跨币种、付款日期截止、超额收款和取消后重算，且 PDF 导出链路尚未同步确认。

拟修改：

- `china_finance/china_finance/services/customer_reconciliation_statement.py`：新增独立结算映射分支，按截止日期过滤已提交 Payment Entry，处理退票/退款符号与币种；保留现有预览接口。
- `china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js`：补充汇总、差额解释和来源单据跳转。
- `client_akivision.utils.customer_reconciliation_pdf` 所在应用：同步 PDF 字段和汇总（跨应用修改前单独确认）。
- `china_finance/tests/test_customer_reconciliation_statement.py`：补齐边界测试。

预期效果：页面、保存快照和 PDF 使用同一截止日口径；原始金额、已结、未结及状态可复核，退款和取消不会留下错误状态。

### P0-2 销售结算表单状态名称与实际动作不一致

现状：`China Sales Settlement.validate()` 在草稿阶段直接把状态改为“待客户确认/待内部复核”，但表单只有“查看正式销售发票”按钮；实际在标准 Submit 时一次性校验确认材料、创建并提交 Sales Invoice、回写“已生成应收”。用户看不到独立的“确认/审批”动作，状态看似有流程，实际没有对应表单动作和阶段审计。

调用链：

```text
Sales Order（结算模式）
 -> Delivery Note
 -> create_settlement_from_sales_order / create_settlement_from_delivery_notes
 -> China Sales Settlement（草稿即显示待确认）
 -> 标准 Submit
 -> before_submit -> create_receivable_for_settlement()
 -> ERPNext Sales Invoice 提交
 -> 回写 settlement.sales_invoice / 状态 / 审批人
```

拟修改：

- `china_finance/china_finance/doctype/china_sales_settlement/china_sales_settlement.js`：新增“确认材料”“内部复核”“生成正式应收”的状态化入口和清晰提示。
- `china_finance/services/sales_settlement.py`：优先新增状态动作分支；保留标准 Submit 的兼容路径，避免旧流程失效。
- `china_finance/china_finance/doctype/china_sales_settlement/china_sales_settlement.json`：仅在确需分阶段审计时追加确认状态字段，不重定义旧字段。
- `public/js/sales_order_settlement.js`、`public/js/delivery_note_settlement.js`：增加已存在结算单提示及快捷跳转，避免重复创建。

预期效果：每个状态都有可执行的下一步，确认人与财务审批人不再默认由同一次提交代填；旧用户仍可按既有提交路径完成结算。

### P0-3 进项抵扣批次缺少表单内“装载/调整发票”入口

现状：服务端已有创建批次、勾选、抵扣、取消能力，批次表单仅有状态按钮。新建批次时无法从表单按公司、期间装载“已查验且待勾选”发票，也没有在操作结果中展示失败明细；用户必须依赖税票列表批量入口或接口调用。

调用链：

```text
China Tax Invoice（进项蓝票）
 -> verify_input_invoices()
 -> deduction_status=待勾选
 -> create_input_tax_deduction_batch()
 -> China Input Tax Deduction Batch
 -> select_input_tax_deduction_batch()
 -> deduct_input_tax_batch()
 -> 回写 Tax Invoice 的勾选/抵扣状态和期间
```

拟修改：

- `china_finance/services/input_tax_deduction.py`：新增只读候选查询接口，复用 `_ensure_eligible_for_selection()`，不改变现有创建/勾选接口。
- `china_finance/china_finance/doctype/china_input_tax_deduction_batch/china_input_tax_deduction_batch.js`：新增“装载待勾选发票”、选择对话框、操作结果汇总和税票跳转。
- 对应 batch/item JSON：必要时新增只读来源状态或异常说明字段。
- `china_finance/tests/test_input_tax_deduction.py`：验证重复占用、取消回滚、权限和期间条件。

预期效果：用户可在批次表单闭环完成选票、勾选、抵扣和取消，并看到逐票失败原因。

### P0-4 结账检查预览未自动保存，生成对账单后检查结果也不会刷新

现状：“运行结账检查”只更新前端 `checks` 子表，没有保存；离开页面可能丢失预览。点击“生成必需对账单”后仅弹数量结果，不重新运行检查或刷新对账覆盖状态。正式 Submit 会重新检查，因此页面预览与最终提交结果可能不同。

拟修改：

- `china_finance/china_finance/doctype/china_closing_run/china_closing_run.js`：预览完成后标记时间/快照标识并明确“预览未保存”；可新增“运行并保存检查”分支；生成对账单后刷新检查。
- `china_finance/services/closing.py`：新增返回 `checked_on`、输入快照键和汇总；保留 `preview_closing_checks()` 返回列表的旧行为，可通过新方法或可选参数返回增强结构。
- `china_finance/china_finance/doctype/china_closing_run/china_closing_run.json`：追加只读检查时间、检查摘要字段。

预期效果：用户能够判断当前检查是否对应最新条件；生成缺失对账单后能立即看到阻断项变化；提交仍以服务端实时复检为准。

### P1-1 税务发票、开票申请和 ERPNext 销售发票缺少统一反向导航

现状：开票申请可以生成 China Tax Invoice，并由服务回填申请状态；但 Sales Invoice、Tax Invoice Request、China Tax Invoice 三者在各自表单上的反向入口不完整。多对多分摊存在于 `China Tax Invoice Allocation`，用户难以从任一端快速查看完整链路和剩余可开票金额。

拟修改：

- `public/js/sales_invoice_invoice_control.js`：增加查看开票申请、税务发票及剩余可申请金额入口。
- `china_finance/china_finance/doctype/china_tax_invoice_request/china_tax_invoice_request.js`：增加来源 Sales Invoice 列表和已生成税票跳转。
- `china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.js`：增加开票申请、业务分摊、原蓝票/红票关联导航。
- `china_finance/services/tax_invoice_request.py`、`tax_invoice.py`：新增只读链路摘要接口，复用现有校验和分摊数据。

预期效果：从销售发票、申请或税票任一端均可查看完整链路，不改变现有开票、红冲和提交接口。

### P1-2 发票识别任务缺少异步状态刷新与失败重试反馈

现状：识别表单可发起识别和生成税票草稿，但没有轮询 `Queued/Processing` 状态；用户需手动刷新。失败时虽保存 `error_message`，表单没有结构化重试提示，也没有从识别任务直接返回源税票表单的上下文。

拟修改：

- `china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.js`：仅在 Queued/Processing 时短周期轮询，完成或离页即停止；失败显示原因并提供重试。
- `china_finance/services/invoice_recognition.py`：保持现有识别接口，新增轻量状态查询接口；返回统一状态、错误和生成结果。
- `public/js/china_tax_invoice_form_recognition.js`：识别后保留任务链接和警告摘要。

预期效果：无需反复手动刷新即可看到完成、待核对或失败状态，重试不会重复创建有效任务或税票。

### P1-3 对账差异解决后，父对账单缺少状态和汇总联动提示

现状：差异单可解决、批准时间性差异或豁免，但处理完成后仅刷新差异单；父对账单的差异字段和页面提示不会即时反映未闭环差异数量。时间性差异承接到下期主要由结账检查读取，表单缺少直观链路。

拟修改：

- `china_finance/services/reconciliation_control.py`：动作成功后返回父单差异摘要；新增只读汇总函数，不改变旧动作参数。
- `china_finance/china_finance/doctype/china_reconciliation_difference/china_reconciliation_difference.js`：显示父单和承接差异导航、动作结果。
- `china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js`：显示开放、时间性、已解决差异数量。

预期效果：差异处理后立即能看出对账是否闭环，并能追踪上期/下期承接关系。

### P1-4 凭证、现金流量指定和同步异常的状态入口分散

现状：China Accounting Voucher 可跳转现金流指定，China Voucher Sync Issue 可重试补齐，但在来源 Journal Entry/Payment Entry 等表单中主要显示凭证快照摘要，缺少统一呈现“凭证是否生成、现金流是否待确认、附件是否完整、取消同步是否异常”的处理入口。

拟修改：

- `public/js/gl_source_snapshot.js`：新增统一只读状态摘要和按状态出现的操作入口。
- `china_finance/services/voucher.py`：新增来源单据状态聚合接口，复用已有凭证、现金流和同步异常查询。
- `public/js/china_accounting_voucher.js`、`public/js/china_cash_flow_assignment.js`、`china_voucher_sync_issue.js`：统一完成后的返回与刷新行为。

预期效果：用户从来源单据即可判断财务链路是否完整，并进入唯一待处理节点；不改变来源单据过账逻辑。

### P2-1 财务报表映射、附注、报表快照缺少“就绪度到修复入口”的联动

现状：结账服务可以识别未复核映射、缺失附注、四表勾稽等阻断项，但检查行只展示文本，不能直接导航到对应模板、映射控制台或附注；修复后也不能在原表单一键复检单项。

拟修改：

- `china_finance/services/closing.py`：为检查结果追加可选 `target_doctype`、`target_name`、`route`，保留原字段。
- `china_finance/china_finance/doctype/china_closing_run/china_closing_run.js`：增加“处理”按钮和单项复检入口。
- `services/statement_mapping_console.py`、`services/disclosure.py`：提供按公司/期间定位缺口的只读参数。

预期效果：结账检查由静态清单变成可操作清单，修复后无需离开结账上下文。

### P2-2 多个表单动作缺少统一批量结果与幂等反馈

现状：README 约定批量接口返回处理数、成功数、跳过数、失败数和逐条错误，但部分表单只 `reload_doc()` 或只显示创建数量，错误细项未在表单呈现。涉及抵扣、生成对账单、识别和凭证补齐。

拟修改：

- 新增通用前端结果展示函数，例如 `public/js/china_finance_action_result.js`。
- 各服务保留旧字段并追加标准 `processed/succeeded/skipped/failed/errors`。
- hooks 中按需加载公共脚本，不替换已有方法。

预期效果：批量操作不再“点完只刷新”，用户能确认哪些数据成功、跳过或失败，并可按失败对象重试。

## 4. 需运行数据验证的风险项

以下静态检查无法直接判定为缺陷，实施前需用测试站点验证：

- Payment Entry 跨币种分摊是否应使用 `allocated_amount`、基础币金额还是交易币金额。
- 销售结算合并多个 Delivery Note 时，税费模板一致但舍入差异是否完全回写到结算明细。
- Sales Invoice 取消后，China Sales Settlement 被置为“已取消”，是否允许按原出库明细重新结算且汇总及时恢复。
- 税务发票取消后，进项抵扣批次、开票申请和分摊记录是否都能阻止或回滚不一致状态。
- 重新开账后，报表快照、档案包和已确认对账单的版本状态是否全部形成可追溯的新版本。
- 电子附件从来源单据删除或替换后，China Electronic Document 的哈希与附件中心状态是否同步。

## 5. 推荐实施顺序

1. P0 金额与状态一致性：客户对账、销售结算、抵扣批次、结账检查。
2. P1 跨表单链路：税票链路、识别状态、差异闭环、凭证统一入口。
3. P2 操作效率：结账修复导航和统一批量结果。
4. 最后执行跨模块回归：来源单据提交/取消、对账、税务、结账、重新开账和导出。

## 6. 增量兼容原则

- 不修改已有白名单方法名称、必填参数、核心返回字段和 ERPNext 标准 DocType 行为。
- 新能力优先新增只读查询、可选参数或新状态动作分支。
- 新字段只追加，不删除、不改名；前端使用元数据存在性检查兼容未 migrate 环境。
- 来源单据仅回写明确的中国财务自定义字段，不修改 ERPNext 核心金额和总账逻辑。
- 状态变更集中在服务层，表单脚本只负责触发、展示和导航。
- 所有生成动作必须幂等；取消和重开必须有反向同步测试。
- 跨应用 PDF 修改单独提交，避免 China Finance 发布隐式依赖其他自定义应用版本。

## 7. 总体调用关系

```text
ERPNext 来源单据
  |-- GL Entry -> China Accounting Voucher -> Cash Flow Assignment
  |                                  |-> Electronic Document / Sync Issue
  |-- Sales Order -> Delivery Note -> China Sales Settlement -> Sales Invoice
  |                                                        |-> Customer Reconciliation
  |-- Sales Invoice -> China Tax Invoice Request -> China Tax Invoice
  |                                               |-> Allocation / Red Invoice
  |-- Purchase Invoice / Tax Invoice -> Input Tax Deduction Batch
  |-- Customer/Supplier/Bank -> Reconciliation Statement -> Difference
  `-- Period Closing Voucher + 上述模块状态 -> China Closing Run
                                                |-> Report Snapshot
                                                `-> Archive Package
```

## 8. 受影响模块与回归边界

直接影响：China Accounting Voucher、China Cash Flow Assignment、China Sales Settlement、China Reconciliation Statement/Difference、China Tax Invoice/Request/Recognition、China Input Tax Deduction Batch、China Closing Run。

关联影响：Sales Order、Delivery Note、Sales Invoice、Purchase Invoice、Payment Entry、Bank Transaction、GL Entry、Period Closing Voucher、财务报表模板/映射/附注、PDF 导出和电子档案。

回归重点：权限和职责分离、提交/取消钩子、幂等创建、跨期截止日、币种、退货/红冲、附件权限、旧单据打开和旧接口调用。

## 9. 总体验收效果

- 任一主要表单都能看见“当前状态、数据来源、下一步动作、处理结果”。
- 来源单据到中国财务快照、现金流、对账、税票和结账形成可双向追踪链路。
- 状态字段均有对应服务动作，不再出现“有状态但没有按钮”或“按钮完成但状态未回写”。
- 金额汇总可以从来源单据复核，取消、退款、红冲、跨期不会遗留旧结果。
- 老接口和非中国财务流程保持可用，新功能可按模块逐步上线和回滚。

## 10. 本次实施记录（2026-09-11）

已按小增量原则落地：

- 客户 Ledger 对账补齐发票结算金额、收款状态、部分开票、截止日付款过滤、汇总和差异提示；修正一个销售订单关联多张发票时客户订单号回填不完整的问题。
- 进项抵扣批次新增按公司及抵扣期间装载“已查验、待勾选、未被其他活动批次占用”发票的入口。
- 销售结算草稿新增“生成正式应收”明确动作和下一步提示，继续复用标准 Submit 及原有服务端校验。
- 结账检查新增保存式检查接口、检查时间、阻断项数量、条件变化失效提示；生成必需对账单后自动复检并显示逐项错误。
- 发票识别任务在 Queued/Processing 状态自动刷新，完成、失败或离开该状态后停止。
- 对账差异动作返回父对账单剩余开放差异数，父单显示待处理差异摘要。
- Sales Invoice、开票申请、China Tax Invoice 补充申请、税票和业务分摊来源的反向导航。
- ERPNext 总账来源单据状态聚合增加待处理凭证同步异常，并提供处理入口。

保留后续验证项：跨应用 PDF 模板实际展示、跨币种分摊口径、取消/红冲/重开全链路以及脱敏生产数据回归。本次未改变旧白名单接口参数，也未修改 ERPNext 核心过账逻辑。
