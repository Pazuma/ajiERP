# 中国财务手工凭证全生命周期与内控合规修复方案

## 1. 文档目的

本文针对“新增凭证”页面与正式记账链路的规则缺口制定小增量修复方案。

目标是让手工凭证能够完整支持：

1. 凭证字（收、付、转、记）选择与正式凭证一致；
2. 附件张数随凭证保存并在汇总、打印中正确显示；
3. 可恢复的持久化草稿；
4. 配置启用时的制单、审核、记账职责分离；
5. 已关闭或已冻结期间的提前提示和最终强校验；
6. 凭证字号按公司、凭证字和配置的重置周期安全连续生成；
7. 已记账凭证的不可随意修改与冲销追溯。

本阶段仅沉淀方案，**不修改代码、不修改数据库、不创建业务凭证**。

## 2. 现状与差距

### 2.1 已具备的规则

| 规则 | 当前实现 | 结论 |
| --- | --- | --- |
| 每行借方、贷方二选一 | `create_manual_voucher()` 后端校验 | 已实现 |
| 至少两条有效分录 | `clean_entries` 少于两条时阻止提交 | 已实现 |
| 借贷合计相等 | 后端以 `Decimal` 强校验 | 已实现 |
| 只能选末级科目 | 后端要求当前公司 `Account.is_group = 0` | 已实现 |
| 日期不得早于中国财务启用日期 | `activation_date` 校验 | 已实现 |
| 已结账/冻结期间的最终拦截 | ERPNext Journal Entry / GL 原生结账、冻结校验 | 已实现，但页面缺少提前提示 |
| 已记账快照核心字段不可改 | `China Accounting Voucher.before_update_after_submit()` | 已实现 |
| 取消来源单据后的冲销审计快照 | `on_gl_source_cancel()` 与 `process_cancellation_snapshot()` | 已实现 |

### 2.2 需要补齐的规则

| 缺口 | 当前现象 | 风险 |
| --- | --- | --- |
| 凭证字选择未贯通 | 页面仅显示默认值；生成正式快照时 `classify_voucher_word()` 固定返回“记”。 | 页面显示、设置和正式凭证字号可能不一致；不能可靠使用收、付、转字。 |
| 附件张数未落库 | 页面有输入框，但保存 RPC 未传该值；`China Accounting Voucher.attachment_count` 保持 `0`。 | 凭证汇总和打印附件数不真实。 |
| 草稿不持久化 | “保存草稿”只显示提示，刷新或退出即丢失。 | 用户误以为已保存，存在录入丢失风险。 |
| 审核生命周期不完整 | 手工页点击保存即创建并提交 Journal Entry；页面“待审核”只是文字。 | 未启用配置时可绕过制单、审核、记账分离。 |
| 凭证字号重置策略未完全使用 | 设置有“会计期间/会计年度”，现有编号逻辑固定按会计期间（月）取序号。 | 设置项与实际行为不一致。 |
| 关闭期间只在最终保存拦截 | 用户录入完成后才在 Journal Entry/GL 校验阶段被拒绝。 | 用户体验差，但不构成绕过。 |

## 3. 总体原则与边界

### 3.1 实施原则

- 小增量：新增手工凭证专用草稿和服务分支，不重写 ERPNext Journal Entry、GL Entry、Workflow、会计期间或结账机制。
- 保留接口：保留既有 `create_manual_voucher(company, posting_date, entries, remarks)`，其签名、权限和返回结构不变。
- 新入口优先：新增受控手工凭证服务，由“新增凭证”页面切换调用；旧入口继续兼容既有调用方和历史脚本。
- 后端兜底：页面提示仅改善体验，正式 Journal Entry 提交仍使用 ERPNext 原生关闭期间、冻结、权限和借贷平衡校验作为最终事实来源。
- 配置决定内控强度：不强制改变所有公司的现有业务；只有公司启用“强制制单审核分离”后，才要求审批工作流和独立审核。
- 业务数据可追溯：草稿、来源 Journal Entry、China Accounting Voucher、冲销快照之间保留可查询的关联。

### 3.2 不在本方案范围

- 不修改 ERPNext 原生 Journal Entry、GL Entry、Accounting Period、Period Closing Voucher 源码。
- 不自动替历史凭证补填附件数或改写历史凭证字；历史数据修复必须另行审批。
- 不改变现有现金流量指定、总账、报表取数和税务单据接口。
- 不将“审核”简化为前端按钮或仅显示文字；审核必须有持久化状态、操作人和时间。

## 4. 目标数据流与调用链路

### 4.1 草稿、审核与记账主链路

```text
China Finance -> 新增凭证 Page
  -> 新增 China Manual Voucher Draft（草稿头 + 草稿分录）
       ├─ 公司、日期、凭证字、附件张数、摘要、借贷分录
       └─ 草稿状态：Draft

用户点击“提交审核”
  -> 新增 manual_voucher.submit_draft()
  -> 后端校验有效分录、末级科目、借贷平衡、启用日期
  -> 创建 Journal Entry（docstatus=0，保留草稿关联、凭证字、附件张数）
  -> 如启用制审分离：进入既有 ERPNext Workflow 审核
  -> 审核人完成独立审核
  -> Journal Entry 提交
       -> 原有 validate_source_approval()
       -> ERPNext 关闭期间 / 冻结日期校验
       -> GL Entry
       -> 原有 create_voucher_from_source()
       -> China Accounting Voucher（正式凭证快照）
          ├─ 使用来源 Journal Entry 的凭证字和附件张数
          ├─ assign_voucher_number()
          └─ 已记账 / 可追溯
  -> 更新 China Manual Voucher Draft 状态与来源链接
```

### 4.2 关闭与冲销链路

```text
China Closing Run / ERPNext Accounting Period
  -> Company.accounts_frozen_till_date / 已关闭会计期间
  -> 新增凭证页面预检提示（非权威）
  -> Journal Entry 提交时原生最终拦截（权威）

已提交 Journal Entry 取消
  -> 原有 on_gl_source_cancel()
  -> process_cancellation_snapshot()
  -> China Accounting Voucher 冲销快照
  -> 原正式凭证状态标记 Reversed，并关联 reversed_by
```

## 5. 拟修改与新增文件

以下为计划文件清单；实施时应以实际仓库结构为准，并在实施记录中逐项确认。

| 文件 | 动作 | 修改目的 | 是否修改旧接口 |
| --- | --- | --- | --- |
| `china_finance/services/manual_voucher.py` | 修改 | 保留旧即时记账接口；新增草稿保存、草稿提交、页面上下文预检等受控分支。 | 旧接口不改；新增方法 |
| `china_finance/china_finance/page/china_new_voucher/china_new_voucher.js` | 修改 | 新增凭证字选择、草稿加载/保存/提交审核、附件张数传递、关闭期间提示。 | 否 |
| `china_finance/services/voucher.py` | 小修改 | 正式快照生成时优先读取手工 Journal Entry 中已固化的凭证字、附件张数；原自动来源逻辑保留。 | 函数仅加可选分支 |
| `china_finance/setup/install.py` | 修改 | 为 Journal Entry 增加中国财务元数据 Custom Fields；注册新增 DocType 所需桌面入口/元数据同步。 | 否 |
| `china_finance/china_finance/doctype/china_manual_voucher_draft/*` | 新增 | 持久化草稿头、状态、来源 Journal Entry、审核信息。 | 新增 |
| `china_finance/china_finance/doctype/china_manual_voucher_draft_entry/*` | 新增 | 持久化草稿分录行。 | 新增 |
| `china_finance/china_finance/doctype/china_finance_settings/china_finance_settings.json` | 谨慎修改 | 仅在现有 `enforce_role_separation` 不足以表达手工凭证审批策略时，新增明确配置；默认保持兼容。 | 否 |
| `china_finance/tests/test_manual_voucher.py` | 新增 | 覆盖草稿、附件、凭证字、编号、审核与日期校验。 | 不涉及 |
| `docs/playwright_china_manual_voucher_lifecycle.mjs` | 新增 | 覆盖页面草稿、提交审核、禁用保存记账等行为；写入测试数据须可识别、可取消。 | 不涉及 |
| `docs/08-reference/62-china-manual-voucher-lifecycle-fix-record.md` | 后续新增 | 记录实际实现、迁移、测试、人工复测与回滚。 | 不涉及 |

### 5.1 新增 Journal Entry 元数据字段

在现有 `custom_china_voucher_number` 的同一中国财务字段区新增以下 Custom Fields：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `custom_china_voucher_word` | Data / Select，只读 | 在手工凭证草稿提交时固化“收/付/转/记”，供正式快照生成与审计追溯。 |
| `custom_china_attachment_count` | Int，只读 | 保存原始附件张数，供正式快照、打印和汇总使用。 |
| `custom_china_manual_voucher_draft` | Link → China Manual Voucher Draft，只读 | 建立草稿与来源 Journal Entry 的追溯关系。 |

这些字段只补充中国财务元数据，不改变 ERPNext Journal Entry `accounts` 分录结构、提交接口或原生总账生成逻辑。

### 5.2 新增草稿 DocType

建议新增：

```text
China Manual Voucher Draft
China Manual Voucher Draft Entry
```

草稿头建议字段：

```text
company
posting_date
voucher_word
attachment_count
remarks
status: Draft / Pending Review / Approved / Posted / Rejected / Cancelled
source_journal_entry
prepared_by
reviewed_by
reviewed_on
submitted_on
posted_on
```

草稿分录建议字段：

```text
remarks
account
debit
credit
idx
```

设计理由：

- 不把未平衡或未完整资料写入 Journal Entry，避免污染标准账务单据列表和审批流。
- 可安全保存“尚未满足正式凭证校验”的临时录入。
- 草稿提交后再创建标准 Journal Entry，后续 GL Entry、正式凭证快照、现金流和报表链路保持不变。

## 6. 分项修复设计

### 6.1 凭证字：收、付、转、记

#### 当前问题

页面读取 `default_voucher_word` 并显示，但用户不能选择；正式快照的 `classify_voucher_word(entries, settings)` 当前固定返回 `"记"`。

#### 小增量方案

1. 页面在“凭证字”位置新增 Select 控件，而不是改写现有凭证头结构。
2. 根据公司设置返回可选值：

   - `voucher_mode = 统一记字`：仅可选择 `记`。
   - `voucher_mode = 收付转记`：可选择 `收`、`付`、`转`、`记`；默认值仍使用 `default_voucher_word`。

3. 草稿提交时将选择值写入 `Journal Entry.custom_china_voucher_word`。
4. `create_voucher_from_source()` 增加优先分支：

```text
若来源为带 custom_china_voucher_word 的 Journal Entry
  -> 使用已固化的值
否则
  -> 保留现有 classify_voucher_word() 逻辑
```

5. `classify_voucher_word()` 仅增加可选来源参数或新增私有辅助方法；其他来源单据继续走旧规则。

#### 预期效果

- 页面显示的凭证字、Journal Entry 元数据、China Accounting Voucher 凭证字及字号一致。
- 收、付、转、记可按公司配置使用。
- 非手工来源单据不受影响。

### 6.2 附件张数

#### 当前问题

页面 `.cf-attachment-count` 的值未传入保存 RPC，正式凭证快照中的 `attachment_count` 默认仍为 0。

#### 小增量方案

1. 保存草稿时写入草稿头 `attachment_count`。
2. 草稿提交创建 Journal Entry 时写入 `custom_china_attachment_count`。
3. `create_voucher_from_source()` 对有该来源字段的 Journal Entry 写入：

```text
China Accounting Voucher.attachment_count
```

4. 保持 `China Accounting Voucher.attachment_count` 为只读审计结果；已记账快照不可在凭证页面直接篡改。

#### 预期效果

- 凭证打印、凭证汇总表附件合计和审计快照显示真实附件张数。
- 原有业务单据自动生成的凭证仍保持当前默认行为，不因缺少新字段而报错。

### 6.3 真实草稿与恢复编辑

#### 当前问题

当前“保存草稿”只显示提示，数据只停留在浏览器内存。

#### 小增量方案

新增白名单方法，不更改旧 `create_manual_voucher()`：

```text
save_manual_voucher_draft(draft=None, payload)
get_manual_voucher_draft(name)
list_my_manual_voucher_drafts(company=None)
submit_manual_voucher_draft(name)
cancel_manual_voucher_draft(name)
```

规则：

- `Draft` 可不平衡、可有未填行，但保存时必须能确定公司和制单人。
- `Pending Review` 及以后禁止制单人直接改动分录；如退回，回到 `Draft`。
- 草稿提交审核前才执行“至少两条有效分录、末级科目、每行借贷二选一、借贷平衡、启用日期”校验。
- 页面新增“保存草稿”“我的草稿/继续编辑”“提交审核”按钮；原“保存并记账”在启用审核分离时改为不可用或改名为“提交审核”。

#### 预期效果

- 用户可以关闭浏览器后继续编辑。
- 未完成凭证不会误入正式 Journal Entry、GL Entry、报表或现金流。
- 草稿与正式凭证可建立一对一或一对多版本追踪，避免重复提交。

### 6.4 制单、审核、记账分离

#### 当前问题

`enforce_role_separation` 已存在，但默认关闭；当前手工页直接提交 Journal Entry。页面上的“审核人：待审核”并不代表有真实审核状态。

#### 小增量方案

复用 ERPNext Workflow，不在中国财务内重写通用审批引擎：

1. 公司启用 `enforce_role_separation=1` 时：

   - 配置并检查 Journal Entry 的活动 Workflow；
   - 草稿“提交审核”创建标准 Journal Entry 草稿并路由至该单据；
   - 审核人通过 Workflow 完成审核；
   - Journal Entry 提交前沿用 `validate_source_approval()`，校验存在独立审核人，且审核人、制单人、记账人不同。

2. 公司未启用该设置时：

   - 保留当前“平衡后可直接记账”的快速路径；
   - 页面明确显示“当前公司未启用制单审核分离”，不得显示为“待审核”造成误导。

3. 提交后的 China Accounting Voucher 继续从 Workflow Action 读取审核人；没有审批的快速路径保持空审核人，不伪造审核记录。

4. 新增配置就绪度检查：

```text
启用了强制制单审核分离
  但 Journal Entry 未配置活动 Workflow
  -> 设置页面和新增凭证页均明确阻断并提示管理员配置
```

#### 预期效果

- 启用内控的公司不能由同一账号完成制单、审核、记账。
- 未启用内控的存量公司不因本次升级突然无法记账。
- 审核人、审核时间和工作流动作有原生可审计记录。

### 6.5 已关闭/冻结期间预检

#### 当前问题

最终保存能由 ERPNext 拦截，但新增凭证页面没有提前告诉用户日期是否落入关闭或冻结期间。

#### 小增量方案

新增或扩展手工凭证上下文方法，例如：

```text
get_manual_voucher_context_v2(company, posting_date=None)
```

返回只读预检信息：

```text
activation_date
accounts_frozen_till_date
closed_accounting_periods
can_post
blocking_reason
```

页面在公司或日期变化时显示状态：

```text
可记账 / 日期早于启用日 / 期间已关闭 / 期间已冻结
```

约束：

- 预检仅用于页面提示和禁用按钮。
- 任何情况下仍由 Journal Entry 提交与 GL 生成时的 ERPNext 原生校验最终决定是否允许记账。

#### 预期效果

- 用户在录入前或修改日期时即知道是否可记账。
- 不复制、不替代 ERPNext 原生结账和冻结规则。

### 6.6 凭证字号与重置周期

#### 当前问题

现有 `assign_voucher_number()` 已使用数据库锁避免重复，但忽略 `China Finance Settings.sequence_reset`，固定按会计期间生成序号。

#### 小增量方案

在不改表名和已有序列数据的前提下新增私有方法：

```text
get_voucher_sequence_scope(voucher, settings)
```

返回：

| 设置 | 序列范围 |
| --- | --- |
| `会计期间` | 公司 + 会计年度 + YYYY-MM + 凭证字 + formal |
| `会计年度` | 公司 + 会计年度 + 凭证字 + formal |

`assign_voucher_number()` 保留行锁、唯一 `voucher_key` 和显示格式；仅改为使用该范围生成 `sequence_key`。

迁移策略：

- 新设置生效前读取当前周期/年度内已有正式凭证最大流水号作为初始值。
- 不重排、不重编号任何历史凭证。
- 变更重置周期应限制为新会计年度或管理员确认后生效，避免同一期间混用两种编号范围。

#### 预期效果

- 同公司、同凭证字、同序列范围内不会重复。
- 设置中“会计期间/会计年度”的语义与实际编号一致。
- 并发提交仍由 `SELECT ... FOR UPDATE` 保护。

### 6.7 已记账修改、取消与红字冲销

当前来源单据取消会生成冲销快照，正式快照已保护核心字段。本次不重写该机制，只补充页面和草稿边界：

1. 已生成来源 Journal Entry 的草稿不可再编辑，只读显示正式凭证与来源单据链接。
2. 不在新增凭证页提供“删除正式凭证”能力。
3. 更正引导统一跳转至来源 Journal Entry 的原生取消/冲销流程；关闭或冻结期间仍遵守原生权限与期间规则。
4. 增加“关联冲销凭证”展示，明确原凭证和冲销快照关系。

## 7. 接口兼容策略

### 7.1 保持不变的接口

以下接口不修改签名、权限和返回结构：

```text
china_finance.services.manual_voucher.create_manual_voucher
china_finance.services.manual_voucher.get_manual_voucher_context
china_finance.services.voucher.create_voucher_from_source
china_finance.services.voucher.validate_source_approval
```

### 7.2 新增接口

新增手工凭证受控接口：

```text
save_manual_voucher_draft
get_manual_voucher_draft
list_my_manual_voucher_drafts
submit_manual_voucher_draft
cancel_manual_voucher_draft
get_manual_voucher_context_v2
```

### 7.3 对旧逻辑的最小增强

`create_voucher_from_source()` 仅增加以下优先读取分支：

```text
Journal Entry 有 custom_china_voucher_word
  -> 使用该凭证字

Journal Entry 有 custom_china_attachment_count
  -> 写入正式快照附件张数

否则
  -> 完整保留现有凭证字分类、附件默认值及其他来源单据逻辑
```

该设计不要求修改所有业务单据，也不改变现有白名单方法的合同。

## 8. 受影响模块

| 模块 | 影响级别 | 影响说明 |
| --- | --- | --- |
| 新增凭证 Page | 高 | 增加凭证字、草稿、审核、附件和期间状态交互。 |
| 手工凭证服务 | 高 | 新增草稿服务；旧直接记账接口保留。 |
| Journal Entry | 中 | 仅新增中国财务只读元数据 Custom Fields，继续使用原生分录、审批、提交和取消。 |
| China Accounting Voucher | 中 | 读取并展示已固化的凭证字/附件；不改变其已有审计快照定位。 |
| China Voucher Sequence | 中 | 根据既有配置切换序列范围；保持并发锁与历史兼容。 |
| 中国凭证汇总、打印、账簿 | 低 | 附件数和凭证字将更准确；现有查询字段不变。 |
| Closing / Accounting Period | 低 | 仅读取状态并提前提示；最终校验仍由原生模块处理。 |
| 现金流、税务、报表 | 无直接逻辑变更 | 仍通过 Journal Entry / GL Entry / China Accounting Voucher 下游取数。 |

## 9. 分阶段实施顺序

### 第一阶段：数据与后端基础

1. 新增草稿 DocType 与草稿分录子表。
2. 新增 Journal Entry 中国财务元数据字段。
3. 新增草稿 CRUD、提交预校验和日期上下文接口。
4. 给正式快照增加“优先读取来源元数据”的兼容分支。
5. 补齐单元测试。

### 第二阶段：页面接入

1. 新增凭证页接入凭证字选择、附件张数、草稿保存和草稿恢复。
2. 根据公司设置展示“保存并记账”或“提交审核”。
3. 显示关闭/冻结期间预检信息。
4. 在正式凭证生成后跳转至来源 Journal Entry 或正式凭证快照。

### 第三阶段：审核与编号策略

1. 配置并验证 Journal Entry Workflow。
2. 验证制单、审核、记账角色分离。
3. 接入 `sequence_reset`，完成新旧序号交界测试。
4. 补齐打印、汇总、冲销追溯和权限测试。

每一阶段均应独立可回滚；未完成下一阶段时，不应破坏当前直接记账路径。

## 10. 验收与测试矩阵

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| V-01 | 保存不平衡草稿 | 可保存草稿；不创建 Journal Entry、GL Entry 或正式凭证。 |
| V-02 | 恢复草稿 | 重新打开后公司、日期、凭证字、附件数、摘要和分录完整恢复。 |
| V-03 | 提交不平衡草稿 | 明确阻止，提示借贷不平衡。 |
| V-04 | 父级科目提交 | 明确阻止，提示只能选择末级科目。 |
| V-05 | 启用日期前提交 | 明确阻止。 |
| V-06 | 已关闭/冻结期间 | 页面提前提示；最终 Journal Entry 提交仍被原生机制阻止。 |
| V-07 | 收字凭证 | 正式快照、打印、Journal Entry 元数据、字号均为“收”。 |
| V-08 | 付/转/记字凭证 | 与 V-07 同样一致。 |
| V-09 | 附件数为 3 | 正式凭证、凭证汇总、打印都显示 3。 |
| V-10 | 未启用制审分离 | 平衡凭证允许走兼容的直接记账路径，界面不伪称待审核。 |
| V-11 | 启用制审分离且无 Workflow | 明确阻断，提示管理员配置 Workflow。 |
| V-12 | 启用制审分离 | 制单人不能审核/记账本人单据；独立审核后才能提交。 |
| V-13 | 同月同字并发提交 | 凭证字号唯一且递增，无重复。 |
| V-14 | 会计年度重置配置 | 按年连续；不在月初错误重置。 |
| V-15 | 取消已记账凭证 | 原快照标记冲销，生成可追溯冲销快照；草稿不可恢复修改。 |

Playwright 测试需分为两类：

1. **无写入页面测试**：金额输入、草稿表单、关闭期间提示、按钮状态。
2. **测试数据库受控写入测试**：用唯一标记创建草稿、提交/审核/取消，并在结束后按标准取消流程清理测试单据。

## 11. 风险与回滚

| 风险 | 控制措施 | 回滚方式 |
| --- | --- | --- |
| 草稿与正式 Journal Entry 重复创建 | 草稿加唯一状态锁和来源单据链接；提交接口幂等。 | 保留草稿，不自动重提；管理员选择继续或作废。 |
| 凭证字页面值与快照值不一致 | 在 Journal Entry 上固化元数据，快照优先读取该值。 | 仅关闭新页面入口；旧 `classify_voucher_word()` 继续可用。 |
| 开启审核分离后公司无法提交 | 启用设置前先检查 Workflow；无 Workflow 则阻断配置启用。 | 关闭该公司 `enforce_role_separation`，不影响已记账数据。 |
| 重置周期切换造成序号冲突 | 新 `sequence_key` 加行锁，变更仅允许新会计年度或管理员确认。 | 恢复旧周期设置，不重排历史字号。 |
| 页面预检与原生拦截不一致 | 前端仅提示，提交始终走 ERPNext 原生校验。 | 关闭预检展示不影响正式会计控制。 |
| 新增字段影响升级 | 通过现有 Custom Field 同步机制创建，字段只读且命名加 `custom_china_` 前缀。 | 保留字段和历史数据；停止新逻辑读取即可。 |

## 12. 实施完成后的沉淀要求

实施后必须新增：

```text
docs/08-reference/62-china-manual-voucher-lifecycle-fix-record.md
```

记录至少包括：

1. 实际修改文件、精确函数/字段和新增 DocType 清单；
2. 数据库迁移、Custom Field 同步与缓存刷新命令；
3. 旧接口兼容结论；
4. 草稿、审核、记账、冲销的实际调用链；
5. 单元测试、Playwright、人工测试结果；
6. 测试数据名称、创建/取消记录，明确是否残留；
7. 已知限制、回滚步骤与后续优化建议。

## 13. 方案结论

推荐采用“**新增手工凭证草稿 + 固化到 Journal Entry 的中国财务元数据 + 复用 ERPNext Workflow/结账机制**”的路径。

该方案以新增分支为主：旧 `create_manual_voucher()`、原生 Journal Entry、GL Entry、工作流和关闭期间机制均不被替换；新增凭证页面逐步切换到新的受控流程。这样既能补齐草稿、附件、凭证字、审核和编号策略的合规要求，也能把对存量业务和老接口的影响控制在最小范围内。
