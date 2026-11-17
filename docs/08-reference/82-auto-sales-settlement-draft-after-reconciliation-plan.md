# 对账完成后自动生成销售结算/采购跟进草稿：优化方案

> 状态：已按第 1-8 节主要链路实施；历史单据未批量补建。采购侧仅在发票明细与整条收货行数量完整对应时自动建草稿，部分开票/退货/缺失来源提示人工处理。实现已同步开发及测试站点字段；仍须用实际业务单据执行人工端到端验收。

## 1. 范围与现状

“对账完成”定义为 `China Reconciliation Statement` **成功提交**，且 `docstatus=1`、`status=Confirmed`。仅对 `statement_type=Customer`、`statement_basis=Delivery` 自动创建销售结算单。默认的 `Customer + Ledger` 是客户往来账口径，其流水/订单账单行不等于送货明细，不能直接映射结算子表；供应商、银行对账也不参与。对账单仅保存、加载明细、导出 PDF 时均不创建结算单。

当前 `ChinaReconciliationStatement.before_submit` 设置确认状态，`on_submit` 处理归档与替代；前端“创建销售结算单”调用 `create_settlement_from_reconciliation`。该接口已核验确认的 Delivery 对账单，筛选有剩余数量的送货行并插入关联对账单、公司、客户、币种、日期和明细的未提交结算单。结算单保存时会把内部复核方式的展示状态由“草稿”改为“待内部复核”；**以 `docstatus=0` 为草稿判断，不以状态文字判断**。当前结算单校验要求至少一行且每行结算数量大于零。

## 2. 预期业务效果

1. 符合范围的客户送货对账单提交成功后，自动保存**一张**可编辑、未提交的销售结算单，自动带入对账单编号、公司、客户、客户名称、币种、结算日期及对账送货明细；不自动提交、不生成销售发票或应收。
2. 对账单完成后展示已关联结算单入口；自动创建的第一张草稿可直接打开、删减明细和修改本次结算数量。后续允许通过原“创建销售结算单”按钮再建其他分次结算单，不把一张对账单限制为一张结算单。
3. 自动建单只发生在首次符合条件的提交事件；重复调用自动分支只返回已有**自动创建的首张**草稿，不创建第二张。不能用“存在任意关联结算单”作为分次结算的全局唯一约束。
4. 不满足口径、无可结算行时，对账单照常确认，不创建空结算单；界面明确提示“无可结算明细，未创建结算单”。符合口径且有可结算行时，若权限或建单校验失败，则提交事务整体失败、显示原因，不留已确认对账单却缺少首张结算单的半成品。

## 3. 调用链路与边界

```text
用户提交客户送货对账单
  -> before_submit：执行原有对账校验并标记 Confirmed
  -> on_submit：保留归档/替代处理，进入新增 Customer + Delivery 分支
  -> 自动创建服务：确认数据、检查自动建单幂等、查剩余可结算送货行
  -> 复用结算建单的数据映射/权限及 insert 校验
  -> 同一数据库事务保存 docstatus=0 的结算单与对账单
  -> 页面重新加载后展示关联结算单入口
  -> 用户调整本次结算量并保存/提交（原结算确认、开票链路不变）
  -> 有剩余额度时，仍可手动调用原 API 创建后续分次结算单
```

Frappe 提交事务内不能调用 `frappe.db.commit()`；插入失败直接抛异常回滚。不要把自动创建放到浏览器 `on_submit`、异步后台队列或 `after_commit`，否则无法保证业务提交与首张建单的一致性。需要先验证 `on_submit` 时数据库中对账单已具备 `docstatus=1`，以及复用的读取校验对本次提交可见。

## 4. 拟修改文件与具体代码

以下路径相对于 `development/frappe-bench/apps/china_finance/china_finance/`，均为**未来实施清单**，本次没有修改业务代码。

| 文件 | 增量修改 | 预期效果 |
| --- | --- | --- |
| `china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.py` | 在现有 `on_submit` 末尾仅对 `Customer + Delivery + Confirmed` 调用自动创建服务；保留既有归档/替代逻辑及其他口径路径 | 真正提交确认后生成草稿，不影响 Ledger/Supplier/Bank |
| `services/sales_settlement.py` | 增加内部 `ensure_initial_settlement_from_reconciliation(...)`；抽取现有 `create_settlement_from_reconciliation` 的组装/插入逻辑供自动及手动复用，但保留公开 API 的名称、参数和 `{name}` 返回；自动分支加入幂等及无剩余行处理，手动分支仍按剩余量新建 | 自动首张只建一次，手动分次不受唯一性误伤 |
| `china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js` | 已确认 Delivery 单据显示关联结算单列表/打开首张入口及无明细提示；原“创建销售结算单”按钮保留，可考虑改文案为“创建下一次结算单”，但仅在已有结算单时显示 | 用户可找到自动草稿，仍可继续分次结算 |
| `china_finance/doctype/china_sales_settlement/china_sales_settlement.js` | 仅在现有详情没有可用回链时增加对账单跳转/来源提示，不改保存提交按钮 | 从结算单可返回对账单，明白数据来源 |
| `china_finance/doctype/china_sales_settlement/china_sales_settlement.json` | **仅在需要可靠区分自动首张与手动分次时**新增隐藏/只读来源标记字段；不改变已有 `reconciliation_statement` Link、子表及老数据必填规则 | 幂等查询有精确标识，不误把手工单当自动单；如采用其他可靠标识则无需改 schema |
| `tests/test_sales_settlement_auto_from_reconciliation.py`（新增） | 对真实 DocType 提交流程和原公开接口增加定向回归测试 | 覆盖自动建单、幂等、手动分次和回滚 |

实现前先核对当前权限：对账单提交人未必拥有 `PREPARER_ROLES` 或结算单 `create` 权限。不能简单调用带 `_require_roles(PREPARER_ROLES)` 的公开接口并以 `ignore_permissions=True` 绕过限制。建议对自动建单增加明确的对账提交角色/结算创建权限判定；若业务希望“有权确认对账者即能自动建草稿”，则需明确授权规则并记录实际创建人，不静默扩大手动入口权限。

幂等仅防止自动路径重复创建首张；并发还需在事务中锁定对账单行或采用可靠的自动来源唯一标识，不能依赖单纯 `exists` 检查。任何新增来源字段只用于标记自动单，不应对历史手工结算单做虚构回填。若 Frappe 的 `on_submit` 生命周期保证同一对账单只能提交一次，仍要测试重复调用服务的安全性。

## 5. 关联模块及不改动项

- **结算数量与分次**：沿用对账行和出库行的剩余额度校验。自动草稿预填当前全部剩余数量，但草稿不占用额度；其他人手动新建/提交结算后，自动草稿可能过期，提交时必须走原有余额复核，不承诺多张草稿可同时全部提交。现有“部分数量需填写调整原因”规则也须在验收中确认是否符合业务操作。
- **客户往来账及 PDF**：Ledger 对账单继续用于账务核对与 PDF 导出，不自动结算，也不改导出模板。截图所示 `CNR-2026-00001` 是否符合自动建单条件，须实际核对其 `statement_basis`；仅编号和客户名称无法判定。
- **销售订单、送货单、发票/应收**：保留现有“先送货对账再结算”门禁和从结算提交生成正式发票的路径；自动草稿不触发开票、库存和财务分录。
- **对账替代/取消**：自动分支应在现有替代处理之后执行；必须回归已关联结算单时的版本/取消行为，避免旧草稿引用失效版本导致用户无法提交。此类版本策略如需改变，应单列需求，不在自动建单时暗改历史单据。
- **权限、索引与迁移**：如新增标识字段，需迁移 DocType 并验证读写权限和过滤器；不修改旧公开 API 合约或批量补生成历史已确认对账单的结算草稿。

## 6. 验收测试流程与预期结果

1. 准备有未结算、已提交、同客户同币种且启用对账结算模式的送货行；创建 `Customer + Delivery` 对账单，提交前确认没有关联结算单。提交成功后应恰好新增一张 `docstatus=0`、关联字段及明细正确的结算单；此时无新增销售发票/应收。
2. 刷新对账单页面，打开自动草稿，调低结算数量并填写所需原因，提交后检查发票及剩余量；再从原按钮生成下一张并完成剩余结算，累计不得超过对账行与出库行上限。
3. 重试自动服务或刷新表单不应产生第二张自动单；手动创建两张及以上草稿仍可行，超额提交按既有校验拒绝。
4. 分别提交 `Customer + Ledger`、Supplier、Bank 对账单，均无自动结算；Delivery 对账无可结算行时只确认不建空单并展示原因。
5. 模拟无创建权限、插入校验错误，确保有明细时确认与结算创建整体回滚、报错清晰；测试并发重复触发、已替代/取消对账、历史手工单及现有公开 API 不回归。
6. 使用 Playwright 验证对账提交后页面关联入口、自动草稿预填、分次入口和错误提示；服务端测试核对事务和数量边界。上线前测试数据库迁移（如有新增字段）。

## 7. 实施前需确认的选择

本方案默认仅 Delivery 口径、无可结算明细允许对账确认但不建单、建单失败则回滚对账提交。若希望截图中的 **Ledger 往来账对账单也自动建结算**，须先单独设计“账务/订单账单行 -> 送货结算明细”的可验证映射与余额规则，不能直接套用 Delivery 分支。另需明确有权提交对账但无权新建结算单的角色应如何授权，以及“自动草稿预填全部剩余数量”是否符合分次结算默认操作习惯。

## 8. 采购侧追加方案：供应商对账确认后生成采购对账草稿

### 8.1 名称与实际单据

这里暂按“`China Reconciliation Statement` 的 `statement_type=Supplier` 对账单提交确认后，生成一张 `Purchase Follow Up`（界面名称：采购对账单〔财务待接收〕）草稿”理解。`China Purchase Reconciliation` 在现有系统中是**查询报表**，不是可保存的草稿单据。`Purchase Follow Up` 当前本身也是一张需要加载收货行、确认差异、提交后移交财务的采购对账单；自动创建只能预填草稿，不能自动提交或自动接收，更不能直接生成采购发票/付款。

### 8.2 数据口径与前置条件

- Supplier 对账单现有明细侧重**已提交采购发票**及齐套/豁免检查；`Purchase Follow Up.sources` 则严格要求 `Purchase Receipt Item`（收货行），提交时检查明细必须对应同一公司、供应商、币种，且收货行不得已在其他已提交采购跟进单中确认。不能把 `Purchase Invoice` 的行号当收货行号，也不能从日期范围重新加载全部收货行，否则会将未参与本次供应商对账的业务带入草稿。
- 需要先确定有依据的映射：只从本次 Supplier 对账单**确认的采购发票**逐条读取其 `Purchase Invoice Item.purchase_receipt_item` / `purchase_receipt`，定位已提交的原始 `Purchase Receipt Item`；对多个发票引用同一收货行进行去重，排除其他公司/供应商/币种和已被有效采购跟进单占用的行。无收货行关联的发票、跨币种、退货冲减、部分开票及一个收货行跨期多发票必须显式处理/提示，不可猜测关联。
- Supplier 对账单的确认金额与采购跟进单的 `supplier_amount` **并非天然相等**：后者是供应商含税确认金额，系统金额由收货行金额计算。不能从 Supplier 对账单 `closing_balance`、差额或发票未付余额直接填入；优先保持待人工确认的供应商金额，并依现有差异规则填写。当前 `Purchase Follow Up` 的确认/收货行唯一占用模型也不支持把同一收货行拆到多张已提交跟进单；采购侧分次付款由关联采购发票/付款链路处理，不照搬销售分次结算。
- 映射不完整或存在已占用收货行时，建议 Supplier 对账单**照常确认**、不生成不完整草稿，并明确提示待人工创建/处理；不得静默丢行。完整映射下如插入失败，回滚确认事务。这个策略与销售侧“无剩余行不建单”一致，但必须在验收中明确对账单提交页的可见提示和审计记录。

### 8.3 采购侧调用链与拟改文件

```text
Supplier 对账单提交 -> 原 before_submit 齐套/附件/差异检查
  -> on_submit 中新增 Supplier 分支 -> 从已确认发票严格映射收货行
  -> 完整且未占用：幂等创建 Purchase Follow Up docstatus=0 草稿
  -> 采购人员核对供应商金额、差异、附件并提交移交财务
  -> 财务接收、采购发票与付款仍走原有链路
```

| 文件（相对 china_finance 应用目录） | 最小增量 | 预期效果 |
| --- | --- | --- |
| `china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.py` | 在销售 Customer + Delivery 分支之外增加 Supplier 独立分支，调用采购自动草稿服务；不影响 Bank/Ledger | Supplier 对账确认触发一次采购草稿生成 |
| `services/purchase_reconciliation.py`（或新增专用 `services/purchase_follow_up_draft.py`） | 新增按 Supplier 对账行映射发票到收货明细、完整性核验与幂等创建的内部函数，不改变原 `preview_purchase_follow_up_sources` API 的取数语义 | 仅带入已确认来源，避免按日期误引入其他收货 |
| `china_finance/doctype/purchase_follow_up/purchase_follow_up.json` | 增加可空 `reconciliation_statement` Link；只读显示来源；如需严格自动幂等则增加来源标记，必要时以唯一性约束保护自动分支 | 一对一追溯自动草稿来源，旧采购单不受影响 |
| `china_finance/doctype/purchase_follow_up/purchase_follow_up.py` | 校验关联 Supplier 对账单已确认且公司、供应商、币种相同；保留当前收货行锁、已占用检查与现有提交/财务接收规则 | 防止手工篡改来源，自动草稿可以走原采购流程 |
| `china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js`、`public/js/purchase_follow_up.js` | Supplier 已确认页展示已生成采购草稿入口/映射失败提示，采购草稿增加返回来源对账单入口；保留原有“加载采购对账明细”按钮 | 双向追溯及人工处理异常 |
| `tests/test_purchase_follow_up.py`（增量扩展） | 覆盖确认触发、发票-收货映射/去重、币种、退货及部分开票、缺失关联、权限、重复触发与回滚、原财务接收/采购发票限制 | 防止采购链路回归 |

权限差异需先处理：`Purchase Follow Up` 当前允许 `Purchase User/Manager` 创建，而提交 Supplier 对账单的财务人员可能没有该创建权限。不能用 `ignore_permissions=True` 暗中扩大权限；应明确自动草稿由哪一角色授权创建，以及新单的 owner/审计归属。采购跟进单取消时当前仅拦截关联的已提交采购发票，新增对账来源后的取消/重建策略也要测试，但不在此次默改原有规则。

### 8.4 采购侧预期效果与验收

提交一张来源发票全部可准确映射为未占用收货行的 Supplier 对账单后，恰好出现一张关联正确、包含公司/供应商/币种/期间和来源行的 `Purchase Follow Up` 草稿；未发生财务接收、开票或付款。重复自动触发不重复建单，原手工创建入口仍可用。缺少关联收货行或已占用时对账单仍可确认、页面明确展示未生成的原因；原采购跟进单提交规则与既有采购发票 `custom_purchase_follow_up` 关联金额上限保持不变。测试中还应验证采购对账单的 `system_amount` 与人工填入的 `supplier_amount` 差异显示及权限边界。

**实施前的关键确认**：用户所说“采购完成对账单后生成采购对账单草稿”是否确指 `Supplier` 通用对账单 -> `Purchase Follow Up`？若实际是“采购收货完成 -> 自动生成 `Purchase Follow Up` 草稿”，触发源与映射完全不同，应先改口径再实施。
