---
title: 多采购申请合并生成采购订单方案
---

# 多采购申请合并生成采购订单方案

版本：v1.0  
方案范围：`Material Request`（采购申请）列表批量选择、合并确认、生成一张 `Purchase Order`（采购订单）草稿  
设计原则：小增量、复用标准映射、保留旧入口、不自动保存或提交、不修改 ERPNext 核心

## 1. 需求理解与结论

业务目标是：采购员选择多张采购申请，将其中尚未下单的物料统一交给同一个供应商，确认后生成一张包含多条物料的采购订单；后续按这张采购订单集中跟踪到货，并在全部到齐后进入开票、结算和付款流程。

本方案不建议再创建一张实际的“合并采购申请”。合并后的中间结果只作为确认弹窗展示，确认后直接生成一张未保存的采购订单草稿。原因如下：

1. ERPNext 的 `Purchase Order Item` 已原生包含 `material_request` 和 `material_request_item`，一张采购订单可以逐行追溯多张采购申请。
2. 标准 `make_purchase_order` 会按申请明细的 `stock_qty - ordered_qty` 计算剩余可下单数量，并在采购订单提交、取消时更新原采购申请的 `ordered_qty` / `per_ordered`。
3. 若额外创建“合并采购申请”，原申请、合并申请和采购订单之间会形成重复需求，容易造成重复采购、状态失真和审计链路变长。
4. “选择 -> 合并预览 -> 确认 -> 采购订单草稿”已满足业务上的合并确认，同时保留每张原采购申请不变。

因此，本文中的“合并”是多张采购申请映射为同一张采购订单，不是合并或作废原采购申请。

## 2. 一期范围

### 2.1 包含范围

- 在采购申请列表的批量操作菜单新增“合并生成采购订单”。
- 只处理已提交、类型为 `Purchase`、未停止且存在未下单数量的采购申请。
- 同一次合并只允许同一公司；供应商在确认弹窗中统一选择，因此生成的采购订单天然只有一个供应商。
- 展示选中的申请、可采购明细、剩余数量、单位、仓库和要求日期，用户确认后生成一张采购订单草稿。
- 每个采购订单明细保留来源 `material_request` 和 `material_request_item`。
- 不自动保存、不自动提交采购订单，采购员仍可检查价格、税费、交期、仓库和条款。
- 部分到货继续使用标准 `Purchase Receipt`；整单是否到齐使用采购订单 `per_received` 和标准状态判断。

### 2.2 不包含范围

- 不新建“合并采购申请”DocType，不复制或修改原采购申请。
- 不修改 ERPNext 的 `make_purchase_order`、采购订单提交和取消接口；只在 `mes_integration` 新增一个薄编排接口。
- 不把相同物料的不同申请行压缩成一行。即使物料相同，也保留多行来源，确保数量回写和审计准确。
- 不在一期修改全局采购发票、付款单或预付款校验。预付款、服务类采购、非库存物料等流程可能不以收货 100% 为前提，直接全局拦截风险过大。
- 不在确认时落库；用户关闭采购订单草稿不会产生业务单据或改变申请状态。

## 3. 用户流程与预期效果

```text
采购申请列表
  -> 勾选多张采购申请
  -> 批量操作 / 合并生成采购订单
  -> 前端读取选中申请并做基础校验
  -> 展示合并确认弹窗
       - 统一供应商（必填）
       - 公司（只读）
       - 来源采购申请
       - 待采购物料、剩余数量、单位、仓库、要求日期
  -> 点击“创建采购订单”
  -> 调用 mes_integration 新增 make_merged_purchase_order
  -> 新接口校验权限、公司、状态和所选明细
  -> 对每张申请调用 ERPNext 标准 make_purchase_order
  -> 返回一张合并后的 Purchase Order（未保存）
  -> 打开采购订单表单
  -> 用户核对价格、税费、交期和条款后保存/审批/提交
  -> 分批收货时 per_received 逐步增加
  -> per_received = 100 时整单到齐，可进入结算/付款
```

预期页面效果：

- 未勾选记录点击入口时提示“请先选择采购申请”。
- 选择草稿、已取消、已停止、非采购类型或已全部下单的申请时，弹窗逐项说明不可合并原因，不静默跳过。
- 选择不同公司的申请时阻止继续，并提示需按公司分别生成采购订单。
- 确认弹窗只有一个供应商字段；所有物料进入同一张采购订单。
- 生成后进入标准采购订单新建页，单据处于未保存状态。
- 采购订单每行可看到对应的采购申请和申请明细；相同物料来自两张申请时保留两行。
- 原有单张采购申请“创建 -> 采购订单”和采购订单“从采购申请取明细”入口保持原行为。

## 4. 复用的标准能力

本方案的核心不是重新实现合并算法，而是组合以下现有接口：

| 标准能力 | 位置 | 本方案用途 |
| --- | --- | --- |
| `make_purchase_order` | `erpnext/stock/doctype/material_request/material_request.py` | 校验申请状态和类型、筛选剩余数量、生成采购订单行 |
| `update_item` | 同上 | 使用 `stock_qty - ordered_qty` 计算本次采购数量并处理单位换算 |
| `set_missing_values` | 同上 | 初始化采购订单缺省值并重新计算税费合计 |
| `Purchase Order Item.material_request` | ERPNext 标准字段 | 记录来源采购申请 |
| `Purchase Order Item.material_request_item` | ERPNext 标准字段 | 记录来源申请明细，支持提交/取消后的数量回写 |

ERPNext 的 `make_purchase_order(source_name, target_doc, args)` 支持传入已有 `target_doc`。新增接口按顺序处理采购申请，并把上一次返回的采购订单草稿继续传给下一次调用，即可得到一张包含多来源明细的采购订单，无需修改 ERPNext 核心。

## 5. 计划修改的文件与代码

### 5.1 必须修改

| 文件 | 修改内容 |
| --- | --- |
| `development/frappe-bench/apps/mes_integration/mes_integration/public/js/material_request_list.js` | 在现有 `onload` 中新增批量操作；读取所选申请；展示供应商和合并明细确认弹窗；调用新增编排接口；同步返回草稿并跳转采购订单。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/material_request.py` | 新增白名单方法 `make_merged_purchase_order`；服务端校验权限、申请状态、同公司和明细归属；循环调用 ERPNext 原生 `make_purchase_order`，返回未保存草稿。 |

该文件目前已经通过“保留原列表配置并追加功能”的方式扩展 Material Request 列表，也已经使用 `listview.page.add_action_item` 和 `listview.get_checked_items` 实现批量发料。本次沿用同一模式，只新增独立的采购类型分支，不改已有批量发料函数。

建议新增的前端函数职责如下：

```javascript
function merge_purchase_requests_to_purchase_order(listview) {
	const names = listview.get_checked_items(true);
	// 读取申请 -> validate_merge_candidates -> show_merge_purchase_order_dialog
}

function validate_merge_candidates(docs) {
	// 校验 docstatus、material_request_type、status、company、剩余数量
	// 返回 { company, items, errors }
}

function get_mergeable_purchase_request_items(docs) {
	// remaining_stock_qty = stock_qty - ordered_qty
	// remaining_qty = remaining_stock_qty / conversion_factor
}

function show_merge_purchase_order_dialog(listview, context) {
	// supplier 必填；公司只读；明细只读并保留来源行
}

function open_merged_purchase_order(listview, context, supplier) {
	return frappe.call({
		type: "POST",
		method: "mes_integration.mes_integration.material_request.make_merged_purchase_order",
		args: {
			material_requests: context.material_request_names,
			supplier,
			selected_items: context.material_request_item_names,
		},
		freeze: true,
		freeze_message: __("正在生成采购订单..."),
	}).then((r) => {
		const purchase_order = frappe.model.sync(r.message)[0];
		purchase_order.__run_link_triggers = 1;
		frappe.set_route("Form", purchase_order.doctype, purchase_order.name);
	});
}
```

后端编排代码骨架：

```python
@frappe.whitelist()
def make_merged_purchase_order(material_requests, supplier, selected_items=None):
	from erpnext.stock.doctype.material_request.material_request import (
		make_purchase_order as erpnext_make_purchase_order,
	)

	names = parse_unique_names(material_requests)
	item_names = set(parse_unique_names(selected_items))
	frappe.has_permission("Purchase Order", "create", throw=True)
	frappe.get_cached_doc("Supplier", supplier).check_permission("read")

	target_doc = frappe.new_doc("Purchase Order")
	target_doc.supplier = supplier
	company = None

	for name in names:
		material_request = frappe.get_doc("Material Request", name)
		material_request.check_permission("read")
		validate_mergeable_purchase_request(material_request, company, item_names)
		company = company or material_request.company
		target_doc.company = company
		target_doc = erpnext_make_purchase_order(
			name,
			target_doc=target_doc,
			args={"filtered_children": list(item_names)},
		)

	if not target_doc.items:
		frappe.throw(_("选中的采购申请没有可下单明细。"))

	target_doc.supplier = supplier
	return target_doc
```

实际实现时，`parse_unique_names` 负责兼容 JSON 字符串/数组、去重、拒绝空值并限制单次合并数量；`validate_mergeable_purchase_request` 负责校验 `docstatus`、类型、状态、公司、明细归属和剩余数量。辅助函数保持私有，不新增远程接口。

入口以新增分支追加到现有 `onload`：

```javascript
listview.page.add_action_item(__("合并生成采购订单"), function() {
	merge_purchase_requests_to_purchase_order(listview);
});
```

新增接口把确认弹窗中的申请明细名称作为 `filtered_children` 传给原生 mapper。即使一期默认选中全部剩余行，也明确限定本次映射范围；同时服务端先验证所有明细确实属于选中的申请，避免伪造或夹带其他申请明细。

### 5.2 建议新增测试文件

| 文件 | 修改内容 |
| --- | --- |
| `development/frappe-bench/apps/mes_integration/mes_integration/tests/test_material_request_purchase_order_merge.py` | 覆盖多申请映射、剩余数量、来源字段、跨公司拒绝、不可采购状态、权限和不落库。 |
| `tests/playwright_material_request_merge_purchase_order.mjs` | 覆盖列表多选、确认弹窗、供应商必填、生成后路由、采购订单行来源与窄屏可用性。 |

若当前交付批次只做方案评审，以上测试文件在实施阶段新增；不建议只依赖人工测试。

### 5.3 明确不修改

以下 ERPNext/Frappe 文件只作为被调用方，不做代码修改：

- `development/frappe-bench/apps/erpnext/erpnext/stock/doctype/material_request/material_request.py`
- `development/frappe-bench/apps/erpnext/erpnext/stock/doctype/material_request/material_request.js`
- `development/frappe-bench/apps/erpnext/erpnext/buying/doctype/purchase_order/purchase_order.py`
- `development/frappe-bench/apps/erpnext/erpnext/buying/doctype/purchase_order/purchase_order.js`

一期不新增 Custom Field、DocType、patch、数据库表或第三方依赖，因此不需要修改 `hooks.py`、`setup.py` 和 `patches.txt`。

## 6. 详细调用链路

```text
Material Request List.onLoad
  -> mes_integration/material_request_list.js
  -> add_action_item("合并生成采购订单")
  -> listview.get_checked_items(true)
  -> frappe.client.get（逐张读取完整申请和明细）
  -> validate_merge_candidates
       -> docstatus == 1
       -> material_request_type == "Purchase"
       -> status not in ["Stopped", "Cancelled"]
       -> 所有申请 company 相同
       -> 至少一行 stock_qty > ordered_qty
  -> show_merge_purchase_order_dialog
       -> 用户选择一个 Supplier
       -> 用户确认来源申请和剩余明细
  -> POST mes_integration...make_merged_purchase_order
       -> 校验 Purchase Order create 权限和 Supplier read 权限
       -> 解析并去重申请、明细名称
       -> 遍历 Material Request
            -> source_doc.check_permission("read")
            -> 校验状态、类型、同公司、明细归属和剩余数量
       -> 创建一个未保存 Purchase Order 并设置 company / supplier
       -> 遍历 Material Request，调用 ERPNext make_purchase_order
            -> get_mapped_doc
            -> source_doc.check_permission("read")
            -> target_doc.check_permission("create")
            -> 校验已提交且类型为 Purchase
            -> select_item：过滤已全部下单和未选明细
            -> update_item：计算剩余采购数量
            -> 映射 material_request / material_request_item
            -> set_missing_values / calculate_taxes_and_totals
       -> 返回同一张合并后的 Purchase Order 草稿
  -> frappe.model.sync
  -> frappe.set_route("Form", "Purchase Order", new-name)
  -> 用户保存/提交
  -> ERPNext 标准 Purchase Order 更新各来源申请的 ordered_qty / per_ordered
```

失败链路保持无副作用：任何一张申请在服务端权限、状态或并发数据校验中失败时，新增接口返回错误，不保存采购订单，也不修改采购申请。

## 7. 数据规则

### 7.1 合并条件

| 规则 | 处理方式 |
| --- | --- |
| 申请状态 | 必须 `docstatus = 1`，且不是 `Stopped` / `Cancelled` |
| 申请类型 | 一期仅允许 `material_request_type = Purchase`，不混入 Subcontracting |
| 公司 | 所有申请必须相同，采购订单公司取该唯一值 |
| 供应商 | 确认弹窗只选择一个，写入采购订单单头 |
| 可采购数量 | `remaining_stock_qty = stock_qty - ordered_qty`，必须大于 0 |
| 采购单位数量 | `remaining_qty = remaining_stock_qty / conversion_factor`，最终仍以服务端 mapper 计算为准 |
| 仓库和交期 | 按申请明细映射到采购订单明细，不强制合并为单头值 |
| 相同物料 | 不跨来源行聚合，保留一行一来源 |
| 数量精度 | 展示使用系统 Float Precision；服务端使用 ERPNext 原计算逻辑 |

前端计算仅用于预览和提前提示，不能作为最终可信值。点击确认后由标准 mapper 重新读取数据库中的申请和剩余数量，以处理多人同时下单造成的数据变化。

### 7.2 供应商规则

Material Request 标准单头没有供应商字段，因此不以申请单头判断供应商。采购员在合并确认时选择本次统一供应商。若物料维护了 `Item Default.default_supplier`，一期可在弹窗中显示“默认供应商不一致”的警告，但不强制阻断，因为实际采购供应商可能由询价结果决定。

选择供应商后仍由标准采购订单 Link Trigger、价格清单和 Buying Controller 补齐币种、价格、税费、地址及付款条款。用户必须在未保存草稿中复核后再提交。

### 7.3 到齐后结算

合并成一张采购订单后，整单到齐状态直接采用标准字段：

- `Purchase Order.per_received < 100`：未全部到齐，不进入常规结算/付款操作。
- `Purchase Order.per_received = 100`：全部采购订单行已完成收货，可创建采购发票并按现有财务流程付款。
- 分批到货通过多张 `Purchase Receipt` 关联同一采购订单，不能因第一次部分到货就把整单视为完成。

一期将其定义为业务流程和验收规则，不修改采购发票/付款的全局服务端校验。建议通过角色权限和操作规范，让采购发票从已全部收货的采购订单创建。

如果财务要求系统强制禁止“未到齐开票/付款”，应作为二期独立开关实施：在 Company 或 Buying Settings 新增“采购订单全部收货后才允许结算”，仅对启用公司、非预付款、非退货、明确关联采购订单的采购发票/付款分支校验。该规则影响面远大于本次合并入口，不能在一期顺带加入。

## 8. 受影响模块

| 模块 | 影响 | 风险等级 |
| --- | --- | --- |
| Material Request 列表 | 新增批量入口和合并确认弹窗 | 中 |
| Material Request 表单 | 无修改；原单张创建采购订单入口保留 | 低 |
| Purchase Order | 新增一种草稿来源方式；保存、审批、提交逻辑不变 | 中 |
| Purchase Order Item | 使用原生来源字段，不新增字段 | 低 |
| Purchase Receipt | 无代码修改；多次收货汇总到同一采购订单 | 低 |
| Purchase Invoice / Payment Entry | 一期无代码修改；仅形成“整单到齐后办理”的业务口径 | 低 |
| MES 批量发料 | 同处一个列表脚本，但函数和申请类型分支独立，行为不变 | 中 |
| 权限与工作流 | 沿用 Material Request 读取权限和 Purchase Order 创建权限 | 低 |
| 数据库与迁移 | 无字段、表和补丁变化 | 低 |

## 9. 风险与处理

| 风险 | 表现 | 处理方式 |
| --- | --- | --- |
| 用户误把“合并”理解为生成新申请 | 查找不到合并申请编号 | 弹窗文案明确“不会新建或修改采购申请，将生成一张采购订单草稿” |
| 跨公司合并 | 采购订单公司、币种和会计维度冲突 | 前端提前提示，新增接口服务端强制拒绝 |
| 并发下单 | 预览数量与生成数量不一致 | 预览不落库，确认时由 mapper 重读 `ordered_qty`；生成后提示用户复核 |
| 相同物料被错误聚合 | 一个采购订单行无法对应多个申请行 | 不聚合来源行，保留 `material_request_item` 一对一关系 |
| 多供应商物料被合并 | 默认供应商与所选供应商不一致 | 确认弹窗显示警告，采购员以本次供应商选择为准 |
| 供应商触发字段未刷新 | 地址、价格、税费未按供应商更新 | 设置 `__run_link_triggers`，进入表单后触发标准字段逻辑，并要求提交前复核 |
| 无权限 | 可看到入口但无法读取申请或创建采购订单 | 标准 `check_permission` 拒绝；前端展示原始权限错误 |
| 一张申请没有剩余数量 | 生成空行或重复采购 | 前端列出错误；服务端 `select_item` 再次过滤 |
| 已过要求日期 | 采购订单交期落在过去 | 标准 mapper 将过期 `schedule_date` 清空，由用户重新确认 |
| 前端脚本修改影响批量发料 | 列表入口加载或 indicator 异常 | 保留原对象展开和原函数；新增采购分支独立测试 |
| “到齐后付款”被绕过 | 用户从其他入口直接建发票或付款 | 一期属于流程控制；需要系统硬拦截时按独立二期需求实施 |

## 10. 测试与验收

### 10.1 自动化测试

服务端/集成测试至少覆盖：

1. 两张同公司采购申请、不同物料，生成一张采购订单和两条来源正确的明细。
2. 两张申请包含相同物料，采购订单保留两行，分别关联各自 `material_request_item`。
3. 申请已部分下单时，只映射剩余数量。
4. 已全部下单、Stopped、Cancelled、草稿和非 Purchase 类型不能合并。
5. 跨公司选择被阻止。
6. 无采购申请读取权限或无采购订单创建权限时失败。
7. 接口只返回本地草稿，数据库中没有新增 Purchase Order。
8. 草稿提交后各来源申请的 `ordered_qty` / `per_ordered` 正确更新；取消后正确回退。

Playwright/UI 测试至少覆盖：

1. 列表勾选两张申请后能看到“合并生成采购订单”。
2. 未选择、无效状态、跨公司、供应商为空时提示准确。
3. 确认弹窗展示全部来源和剩余数量。
4. 点击创建后路由到一张未保存 Purchase Order。
5. 采购订单 supplier、company、item、qty、warehouse、schedule_date、material_request 和 material_request_item 正确。
6. 原“发料并推送至DLM”批量入口和列表状态颜色无回归。
7. 390px 窄屏下弹窗可滚动，供应商字段和主操作按钮可见且无重叠。

### 10.2 业务验收场景

准备采购申请 `MR-A`（物料 A、B）和 `MR-B`（物料 C），选择供应商 S：

- 合并确认后只出现一张采购订单草稿，供应商为 S，包含 A、B、C 三条来源明细。
- 保存、审批和提交后，`MR-A`、`MR-B` 的已订购比例按各自行数量更新。
- 对采购订单先收 A、B，采购订单仍显示未完全收货，不能按业务流程结算。
- 再收 C，采购订单 `per_received = 100`，整单显示已到齐并可进入结算、付款。
- 取消采购订单后，原采购申请恢复相应的可下单数量。

## 11. 发布与回滚

发布步骤：

1. 更新 `mes_integration/material_request.py` 和 `mes_integration/public/js/material_request_list.js`。
2. 重启后端进程，执行前端资产构建和站点缓存清理。
3. 使用有/无 Purchase Order 创建权限的账号分别复测。
4. 验证采购申请列表批量发料入口未受影响。

本方案没有数据库迁移。回滚只需撤销 `material_request.py` 中的新增接口和 `material_request_list.js` 中的新增入口，重启进程、重新构建资产并清理缓存。已由用户保存或提交的采购订单仍是标准单据，回滚后不受影响。

## 12. 实施拆分建议

一期按本文实施多申请合并生成采购订单，预计只触碰 `mes_integration` 的两个现有业务文件并新增测试文件。验收稳定后，再单独确认是否需要二期“未全部收货禁止开票/付款”的服务端强校验；二期必须先明确预付款、服务/费用物料、退货、超收、短关闭和免收货供应商等例外规则。
