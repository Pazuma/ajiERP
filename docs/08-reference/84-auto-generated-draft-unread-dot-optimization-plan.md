# 自动生成下一步表单草稿未读红点优化方案

> 状态：方案，尚未修改业务代码。路径以 `development/frappe-bench/apps/` 为基准；上线前需在实际站点核对安装应用、字段及权限。本文所说的“已读”只表示当前用户打开过详情，不代表业务审核完成。

## 1. 目标与口径

上一步表单提交后，系统自动保存并预填下一步表单草稿；有权查看该草稿的用户在对应表单列表的单据编号旁看到小红点，工作台对应入口也提示存在未读草稿。详情成功加载后，仅当前用户的红点消失；来源信息保留，草稿仍须人工核对并按原流程提交。刷新、重新登录后保持已读状态。

- 按**用户独立已读**；甲查看不影响乙。暂不建立负责人分配或推送通知，所有实际有权读取该单据的用户可看到提醒。此业务口径如需改为指定岗位/责任人，实施前另行确定。
- 仅对自动创建、已落库且 `docstatus=0` 的草稿生效；未保存的新表单、手动创建、手动点击“创建下一步”产生的单据不标记。单据提交、取消或删除后不再计入提醒；再次运行幂等建单不能把已读重新标为未读。
- 历史草稿默认不追溯标红：新增类型以功能上线时刻之后新建的自动草稿为准；已有送货单/工单需确认是否保留现有显示口径，不能通过发布隐式改变历史提醒数量。
- 列表点按、预览、打开失败均不算已读；详情加载成功才写入已读记录。直接 URL、来源表单关联入口、工作台跳转也必须生效。
- 红点表示“自动生成且未查看”，不是“待办已指派”；不变更提交门禁、财务分录或权限。

## 2. 现状与缺口

`client_akivision/utils/auto_draft_read.py` 已提供 `mark_auto_draft_read`、`get_unread_auto_draft_names`、`get_unread_auto_draft_counts`，并使用 `Auto Draft Read Record` 记录用户和单据；当前仅允许 `Delivery Note`、`Work Order`，依赖 `custom_auto_fulfilment` 字段。`public/js/auto_draft_read_badge.js` 已在两类列表加红点，`public/js/auto_fulfilment_badges.js` 已在工作台侧栏加角标。原 `sales_order_auto_fulfilment.get_auto_draft_badge_counts()` 仍供旧调用者使用，应保持原返回合同。

当前列表在**点击链接时**即调用已读 API，详情尚未加载；直接 URL/其他入口不会消红点。后端查询以 `frappe.has_permission(doctype, "read")` 做类型级校验，需验证查询是否尊重用户权限/共享/单据级限制；不能只据此认为每一行都有权读取。已读记录没有数据库复合唯一约束，双标签并发首次查看可能产生重复记录。`mark_auto_draft_read` 内部显式 `commit` 应按 Frappe 请求事务规则审视。现有列表脚本在同一文件中注册两种类型的 onload 包装，扩展前应测试加载次数和与既有列表设置的组合。

已核对自动生成来源：销售订单履约在 `client_akivision/utils/sales_order_auto_fulfilment.py` 给送货单和工单写入 `custom_auto_fulfilment`；客户 Delivery 对账提交调用 `china_finance/services/sales_settlement.py::ensure_initial_settlement_from_reconciliation`，销售结算单的 `auto_reconciliation_statement` 用于标识自动首张；供应商对账自动创建采购跟进单使用 `reconciliation_statement` 唯一来源字段。后两者尚未纳入现有未读接口，且采购字段是否仅由自动分支写入，应实施前逐条核对。

## 3. 推荐的小增量实现

1. 在现有已读服务内部增加允许类型与“是否自动生成”判定映射：送货单/工单保留现有字段口径；销售结算单仅认非空 `auto_reconciliation_statement`；采购跟进单仅认自动创建分支写入的可靠标识。若采购 `reconciliation_statement` 同时可能被人工建单写入，则新增只读隐藏的自动来源标识，**只由自动建单分支设置**，不要将所有关联采购单误判为自动草稿。不要修改旧 API 路径、参数、返回字段；汇总接口只追加 `china_sales_settlement`、`purchase_follow_up` 等键。
2. 保留现有 `Auto Draft Read Record` 数据；为 `(user, reference_doctype, reference_name)` 增加唯一约束及必要查询索引前先核查/清理重复数据（保留最早 `first_read_at` 和最晚 `last_read_at`），迁移需可重复运行。新增类型如需限定上线后新草稿，使用明确的启用时间/来源标记，不依赖浏览器本地状态。所有查询先按当前用户可读单据过滤，再计算未读；批量仅处理当前页名称，汇总使用有界查询/反连接，避免全量 Python 拉取。权限变化后计数随权限即时变化。
3. 列表复用现有红点样式和查询，移除点击即标记；新增通用详情页脚本在 form load/refresh 确认已加载目标草稿及 read 权限后调用现有标记 API。API 再校验单据级 read、来源及 `docstatus`，成功才写入当前用户记录；并发首次插入按唯一键冲突作幂等处理，失败时保留红点且可重试。避免无条件刷新详情时更新 `last_read_at`，避免修改业务单据或显式提交其他事务。
4. 工作台沿用现有侧栏脚本，扩展对应表单入口的映射和汇总键；详情标记成功后刷新汇总。若侧栏不存在对应入口，不凭空创建工作台入口；列表红点仍正常工作。来源表单的关联入口仍按原路由跳转，详情脚本统一处理已读。
5. 按生成链路逐项接入，不改自动生成触发点、已有预填字段、幂等约束和手工创建接口。先完成现有两类的进入详情修正，再接销售结算与采购跟进；其他自动草稿后续凭可靠来源标识按同一映射追加，不以 `docstatus=0` 直接推断自动生成。

## 4. 调用链路

```text
销售订单提交 -> 既有异步履约 -> 写来源字段并保存送货单/工单草稿
客户 Delivery 对账提交 -> 既有 ensure_initial_settlement_from_reconciliation -> 自动首张销售结算草稿
供应商对账提交 -> 既有采购自动建单分支 -> 带可靠自动来源标识的采购跟进草稿
上述事务提交成功 -> 用户打开对应列表/工作台 -> 未读查询按权限、来源、状态及用户已读记录返回结果 -> 红点
任一入口打开详情且加载成功 -> mark_auto_draft_read -> 服务端复核权限和自动草稿 -> 幂等写当前用户已读记录 -> 列表/工作台刷新，红点消失
```

建单失败或事务回滚不产生提醒；提醒查询和已读写入不调用生成接口。实时事件可用于主动刷新，但页面重新进入必须从服务端取状态，不能依赖事件一定送达。

## 5. 预计修改文件与影响范围

以下是未来实施清单，不表示本次已修改。优先改项目应用，不修改 Frappe/ERPNext 核心代码。

| 文件（相对 `development/frappe-bench/apps/`） | 预计最小改动 | 预期效果 |
| --- | --- | --- |
| `client_akivision/client_akivision/utils/auto_draft_read.py` | 扩展类型/来源判定，逐单据权限过滤与查询，已读幂等；保留现有三个公开 API | 四类表单使用同一未读口径，杜绝权限泄漏 |
| `client_akivision/client_akivision/public/js/auto_draft_read_badge.js` | 复用列表渲染，追加新类型、移除点击即已读，并处理重绘/查询竞态 | 列表编号旁显示正确红点，点开失败不误消失 |
| `client_akivision/client_akivision/public/js/auto_draft_form_read.js`（新增） | 详情加载成功后标记，防重复请求并刷新角标 | 直接链接及关联入口也能消除当前用户红点 |
| `client_akivision/client_akivision/public/js/auto_fulfilment_badges.js` | 扩展侧栏类型映射及返回键，保持原两类逻辑 | 新类型入口同步提示未读 |
| `client_akivision/client_akivision/hooks.py` | 在 `doctype_js`、`doctype_list_js` 为目标类型追加脚本，沿用现有 CSS | 原有表单/列表脚本和功能不被替换 |
| `client_akivision/client_akivision/client_akivision/doctype/auto_draft_read_record/auto_draft_read_record.json` 与新增 patch | 仅在核实重复数据后加复合唯一键及索引；不删除用户已读历史 | 多窗口幂等、查询稳定 |
| `china_finance/china_finance/china_finance/doctype/purchase_follow_up/purchase_follow_up.json` 及其自动生成服务（路径实施前确认） | **仅当现有来源字段无法可靠区分手工/自动时**加来源字段并只在自动分支写入 | 人工采购跟进单不误标红 |
| `client_akivision/client_akivision/public/css/auto_draft_read_badge.css` | 仅按新增列表布局微调间距、无障碍提示 | 红点不遮挡编号或操作 |
| 对应应用的定向 Python 测试、列表/详情 Playwright 用例（新增或扩展） | 覆盖权限、四类来源、已读和关联跳转 | 防止旧业务链路回归 |

销售结算现有 `auto_reconciliation_statement`、采购现有 `reconciliation_statement`、既有送货/工单来源字段及建单方法原则上**不改**；只有实测发现采购来源无法区分自动创建时才改其建单分支。`draft_notifications` 的通知中心红点属于另一套 Notification Log，不接入、不修改其已读语义。旧 `get_auto_draft_badge_counts()` 不重定义为“未读数”，避免旧调用者语义变化。

## 6. 验收与预期效果

- 四类自动草稿成功预填并保存后，各自在列表和存在对应入口的侧栏出现红点；手工草稿、未保存表单、失败回滚、重复幂等调用均不产生新红点。
- A、B 两个有权用户同时看见红点；A 从列表、工作台、来源表单关联入口或直达链接打开详情后，仅 A 的红点消失；B 不受影响。点击后页面加载失败、仅列表预览时红点保持。
- A 刷新、重新登录仍已读；新生成另一张自动草稿再次出现红点；已提交/取消/删除的草稿不再显示。无权用户列表查询、汇总及标记 API 均不可见或不可写。
- 双标签并发打开只有一条已读记录；快速切换列表/翻页不会把上一页的红点画在当前页；大列表和大量历史记录的汇总不发生明显性能退化。
- 销售订单履约、对账单提交、分次手工结算、采购跟进提交、原关联跳转、原工作台角标与通知中心均保持原业务行为；自动草稿仍须人工检查后提交。

实施前需核实目标站点是否已安装并迁移 `Auto Draft Read Record`，以及供应商对账建单函数的准确位置/来源标识写入规则；如用户希望仅指定负责人看到提醒，应先确定分配规则，再调整“所有可读用户”的口径。
