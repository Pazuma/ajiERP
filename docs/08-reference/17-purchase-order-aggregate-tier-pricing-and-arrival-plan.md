---
title: 采购订单同物料合并阶梯报价与实际到货展示方案
---

# 采购订单同物料合并阶梯报价与实际到货展示方案

状态：仅方案，未修改业务代码  
范围：采购订单（`Purchase Order`）明细的同物料合并阶梯报价，以及原“交货计划”区域的实际到货展示

## 1. 目标与结论

采购订单允许同一物料因收料仓、交期、来源采购申请等不同而保留多条明细；但阶梯报价必须以该订单中同一物料的**合计下单数量**取价。收料仓不参与阶梯数量分组。

实际到货不建议再写入采购订单的“交货计划”子表。真实到货、库存和应付的来源应继续是标准 `Purchase Receipt`（采购收货单）。采购订单将该区域改为“实际到货情况”只读汇总，并提供标准收货入口。这样既能按订单内物料选择、展示数量/单位/价格/金额，又不会产生两份到货数据。

本方案采用小增量方式：仅在自定义应用 `mes_integration` 新增采购订单专用分支；不修改 ERPNext 核心文件，不改写既有价格规则接口、采购订单创建接口或采购收货接口。

## 2. 已确认的业务规则

1. 阶梯报价按采购订单的下单数量计算，不按实际收货数量重新定价。
2. 同一采购订单、同一物料的所有有效明细行合计数量参与阶梯判断，即使收料仓不同也合并。
3. 价格命中新的阶梯后，该物料所有参与合计的行同步更新单价和行金额。
4. 明细仍保留物料、数量、单位、单价、金额和收料仓，不能为阶梯计价而合并或删除仓库不同的行。
5. “实际到货情况”仅统计已提交的采购收货单；草稿、取消的收货单不计入。
6. 新建收货时只能从该采购订单未收完的明细中选取物料，沿用标准采购收货单对采购订单行的映射与数量校验。

## 3. 为什么需要专用分支

ERPNext 标准前端在明细行数量变化时调用：

```text
Purchase Order Item.qty
  -> TransactionController.apply_pricing_rule(item)
  -> erpnext.accounts.doctype.pricing_rule.pricing_rule.apply_pricing_rule
  -> Pricing Rule 按当前行 qty / stock_qty 筛选 min_qty、max_qty
```

标准“混合条件”会扫描单据行，但其计算面向不同物料组合；遇到多个相同物料行时，会以触发行的数量参与重复计算，不能作为“同物料重复行合计”的可靠定价基础。

因此不改写标准 `apply_pricing_rule`，而是在采购订单上增加一个独立的“同物料合计报价”分支：先聚合订单行，再复用标准 Pricing Rule 的规则筛选与税费合计能力，将结果回写到对应行。

## 4. 设计范围

### 4.1 同物料合并阶梯报价

分组键为：

```text
item_code + stock_uom + buying_price_list + currency
```

采购订单的供应商、公司、币种和价格表本身为单头字段，参与标准价格规则筛选，但无需在单据内再次分组。`warehouse` 明确不在分组键中。

数量统一以 `stock_qty` 累加，避免同物料不同采购单位造成直接相加错误；命中价格后按各行 `conversion_factor` 换算回当前行的采购单位单价。常规同单位场景下，表现为各行相同单价。

一期仅处理标准“采购、按物料、数量阶梯、价格或折扣”规则。若命中的规则设置了仓库限定、赠品、混合物料、累计历史单据或递归条件，服务端不自动套用该规则，并返回清晰提示，继续保留现有单行定价结果。这样不会在小改动中改变已有复杂促销规则的含义。

### 4.2 价格变化提示

在采购订单明细表下方、添加行按钮上方插入无边框的提示区域，仅在本次编辑导致阶梯价格变化时显示。例如：

```text
阶梯报价调整
螺丝：合计数量 100 -> 300 个，含税单价 CNY 0.10 -> CNY 0.08，订单金额减少 CNY 6.00。
```

多个物料逐行展示。变动涉及的单价和金额单元格短暂加浅色高亮。保存后重新打开单据不展示历史提示，因为价格、价格规则明细和修改记录已保留在标准单据中；一期不新增一套独立报价变更日志。

### 4.3 实际到货情况

将当前“交货计划”的用户入口改为“实际到货情况”：

- 表格列：采购收货单、收货日期、物料编码、物料名称、实际到货数量、单位、订单单价、行金额、收料仓、累计到货、剩余未到货。
- 数据源：已提交 `Purchase Receipt` 及其 `Purchase Receipt Item`，过滤 `purchase_order = 当前采购订单`。
- “登记实际到货”按钮：调用标准从采购订单创建采购收货单的动作，不新增采购订单子表、不直接写库存。
- 标准映射生成的收货单只带入当前采购订单的未收完明细；服务端仍由 ERPNext 标准校验防止超收、跨订单物料或并发超量。

若历史“交货计划”已有用于供应商承诺交期的业务数据，本期不删除该字段和子表。仅在表单隐藏其编辑入口并保留数据兼容；是否清理历史计划数据，另立数据迁移需求确认。

## 5. 拟修改文件与代码

本节是实施清单，不代表这些代码已经存在或已执行。

| 文件 | 变更类型 | 拟修改内容 |
| --- | --- | --- |
| `development/frappe-bench/apps/mes_integration/mes_integration/hooks.py` | 修改 | 在 `doctype_js` 新增 `Purchase Order` 脚本；在 `doc_events` 新增采购订单 `validate` 钩子。既有单据钩子不变。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/public/js/purchase_order.js` | 新增 | 监听明细物料、数量、单位、换算率、增删行；调用新增报价预览接口；回写行价并渲染“阶梯报价调整”；渲染实际到货汇总和标准收货按钮。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/purchase_order.py` | 新增 | 提供采购订单专用的报价聚合、价格规则适配、提交前复算、实际到货汇总接口。私有函数供 API 和 `validate` 钩子共用。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/tests/test_purchase_order_aggregate_pricing.py` | 新增 | 单元测试合计、跨仓、跨单位、阶梯变更、复杂规则跳过和提交前篡改回算。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/tests/test_purchase_order_actual_arrivals.py` | 新增 | 单元测试已提交/草稿/已取消收货单过滤、累计/剩余数量、仅订单关联行展示。 |
| `docs/08-reference/17-purchase-order-aggregate-tier-pricing-and-arrival-plan.md` | 新增 | 本方案文档。 |

不修改：

- `erpnext/accounts/doctype/pricing_rule/pricing_rule.py`
- `erpnext/accounts/doctype/pricing_rule/utils.py`
- `erpnext/buying/doctype/purchase_order/purchase_order.py`
- `erpnext/buying/doctype/purchase_order/purchase_order.js`
- 标准 `Purchase Receipt` 控制器和创建接口

不新增 Custom Field、DocType、数据库表或 patch；因此不需要修改 `patches.txt`，也没有数据迁移。

## 6. 关键代码结构（拟实现）

### 6.1 新增报价计算接口

新增白名单方法：

```python
@frappe.whitelist()
def preview_aggregate_item_pricing(purchase_order):
    """仅计算草稿报价，不保存采购订单。"""
    doc = frappe.get_doc(frappe.parse_json(purchase_order))
    doc.check_permission("write")
    return build_aggregate_pricing_result(doc, apply_to_doc=False)
```

返回只包含当前订单行的补丁和提示，不返回或修改其他单据：

```json
{
  "row_updates": [
    {
      "name": "new-purchase-order-item-1",
      "price_list_rate": 0.08,
      "rate": 0.08,
      "discount_percentage": 0,
      "pricing_rules": "[\"BUY-SCREW-QTY-300\"]"
    }
  ],
  "changes": [
    {
      "item_code": "SCREW",
      "stock_uom": "Nos",
      "old_total_qty": 100,
      "new_total_qty": 300,
      "old_rate": 0.1,
      "new_rate": 0.08,
      "amount_delta": -6
    }
  ],
  "warnings": []
}
```

接口名称、参数和返回值均为新接口，不改变现有 `apply_pricing_rule` 或 `get_item_details` 的入参和行为。

### 6.2 聚合及回写逻辑

`build_aggregate_pricing_result` 的步骤：

1. 忽略空物料、免费物料和零数量行，按分组键累计 `stock_qty`。
2. 用聚合后的数量构造临时 Pricing Rule 上下文，复用 ERPNext 的 `get_pricing_rule_for_item` 获取命中的标准规则、折扣或价格。
3. 对每一组检查规则是否落在一期支持范围；复杂规则写入 `warnings`，不覆盖原有行价格。
4. 按行换算得到 `price_list_rate`、`rate`、折扣字段及标准 `pricing_rules` 追溯字段。
5. 前端将行补丁静默写入后，调用既有 `calculate_taxes_and_totals()`，由标准税费逻辑计算金额、税额和订单总额。
6. 表单 `validate` 钩子再次调用同一私有函数并写回结果，然后调用标准总额计算。浏览器绕过、导入、API 创建或并发编辑时，提交结果仍以服务端为准。

服务端伪代码：

```python
def validate_aggregate_item_pricing(doc, method=None):
    if doc.doctype != "Purchase Order" or doc.docstatus != 0:
        return

    result = build_aggregate_pricing_result(doc, apply_to_doc=True)
    if result.warnings:
        frappe.msgprint("<br>".join(result.warnings), indicator="orange")
    doc.calculate_taxes_and_totals()
```

该钩子只处理采购订单草稿。已提交采购订单的价格仍按标准 ERPNext 的取消/修订流程处理，不允许通过保存已提交单据改价。

### 6.3 前端触发与提示

`purchase_order.js` 以防抖方式监听 `Purchase Order Item` 的 `item_code`、`qty`、`uom`、`conversion_factor`、`warehouse`，以及 `items_add` / `items_remove`。`warehouse` 变化也触发重算，是为了当用户把同物料拆到不同仓库行时立刻刷新同物料合计；它本身不会参与价格分组。

前端采用请求序号避免异步返回乱序：仅应用最后一次请求的结果。应用结果时不触发标准单行 `price_list_rate` 的重复取价，随后统一调用标准税费合计。单行标准报价触发保留，采购订单专用分支在其后覆盖为聚合后的正确结果。

提示基于重算前后的行价快照生成，属于浏览器会话状态，不落库。服务器返回的规则和价格是价格值的唯一权威来源。

### 6.4 实际到货汇总接口

新增白名单只读方法：

```python
@frappe.whitelist()
def get_actual_arrival_summary(purchase_order: str) -> dict:
    """返回当前用户有读取权限的已提交采购收货明细及按订单行汇总。"""
```

查询条件固定为：`Purchase Receipt.docstatus = 1`、`Purchase Receipt Item.purchase_order = purchase_order`，并执行采购订单读取权限校验。金额优先显示采购收货行的实际 `amount`；同时保留订单行单价以支持差异核对。查询不写入任何数据。

创建收货不新增自定义接口，前端复用采购订单标准 “Create -> Purchase Receipt” 路径。这样物料选择范围、关联订单行、收货仓、批次、质检、库存、应付和超收校验均保持 ERPNext 标准行为。

## 7. 调用链路

### 7.1 阶梯报价

```text
采购订单明细：新增/删除行，修改物料、数量、单位、换算率或收料仓
  -> mes_integration/public/js/purchase_order.js（防抖并取当前草稿）
  -> preview_aggregate_item_pricing（新接口，只计算）
  -> build_aggregate_pricing_result（新私有服务）
  -> ERPNext get_pricing_rule_for_item（复用标准规则筛选）
  -> 返回各明细行价格补丁、变更提示、警告
  -> 前端回写单价/折扣/规则并调用标准税费总计
  -> 明细下方显示本次“阶梯报价调整”
  -> 用户保存/提交采购订单
  -> Purchase Order.validate
  -> mes_integration validate_aggregate_item_pricing（服务端复算并回写）
  -> ERPNext 标准校验、税费计算、保存/提交
```

### 7.2 实际到货

```text
打开采购订单
  -> purchase_order.js 请求 get_actual_arrival_summary（新只读接口）
  -> 查询已提交 Purchase Receipt / Purchase Receipt Item
  -> 在“实际到货情况”展示数量、单位、单价、金额、仓库及累计/剩余

点击“登记实际到货”
  -> ERPNext 标准 Purchase Order -> Purchase Receipt 映射
  -> 仅带入该订单尚未收完的物料行
  -> 用户确认实际数量、收料仓、批次、质检
  -> 标准 Purchase Receipt 提交
  -> 更新库存、采购订单 received_qty / per_received，后续刷新时反映在汇总中
```

## 8. 受影响模块

| 模块 | 影响 | 风险 |
| --- | --- | --- |
| 采购订单表单 | 新增同物料合并定价、价格变更提示、实际到货汇总 | 中 |
| Pricing Rule / Item Price | 复用配置和现有规则，不改配置结构 | 低 |
| 采购收货 | 不改收货逻辑，只在订单展示其结果并复用创建入口 | 低 |
| 库存、质检、批次/序列号 | 继续只由 Purchase Receipt 驱动 | 低 |
| 税费、应付、采购发票 | 沿用订单行价格和标准税费/收货链路 | 低 |
| 采购申请合并生成订单 | 保留多条来源行；新分支只在订单草稿定价时按物料合并数量 | 中 |
| ERPNext 核心升级 | 无核心文件修改 | 低 |

## 9. 边界与待确认项

1. **手工改单价**：一期不新增“手工锁价”字段。任何数量、物料、单位或仓库变动都可能触发该物料的自动重定价。确需锁价时，应在二期增加明确的行级锁价标志、权限和审计日志，不能仅凭“当前价格不同”猜测是否人工修改。
2. **不同采购单位**：一期按库存单位合计并换算行单价；需用测试数据验证供应商报价规则中存在 UOM 限定时的换算精度。若业务存在“一箱”和“一个”采用不同报价阶梯，应配置为不同物料或明确为不同计价单位，不能盲目合并。
3. **仓库限定价格规则**：本次业务规则规定收料仓不影响阶梯价；带仓库条件的 Pricing Rule 不自动兼容，应先清理或单独确认其优先级。
4. **订单变更**：下单数量是定价基础。草稿及提交前的修订单可重算；已经提交且已收货的订单不得直接改价，需走标准修订/差额流程，避免回写历史库存成本和应付依据。
5. **“交货计划”历史用途**：若它还承担供应商承诺交期或 MRP 排程，不能直接删除。应保留为只读历史或迁移为“承诺交期”，实际到货则以收货单为准。

## 10. 验收场景

1. 同物料两行，仓库 A 数量 100、仓库 B 数量 200；规则 300 起单价 0.08。两行均更新为 0.08，金额和订单总额正确，提示显示 0.10 -> 0.08。
2. 删除仓库 B 行后总量低于阶梯，两行或剩余行恢复较低阶梯对应价格，提示正确。
3. 两个不同物料分别满足不同阶梯，只更新各自分组，不互相影响。
4. 相同物料来自不同采购申请、仓库不同，来源字段仍保留，数量合并用于定价但明细不合并。
5. 浏览器手工篡改单价后提交，服务端按合并数量重新计算，不能以客户端值绕过规则。
6. 配置仓库限定或赠品/递归等不在一期范围的规则时，出现明确警告，现有复杂规则不被静默改写。
7. 创建草稿、提交、取消三类采购收货单后，实际到货表只统计已提交单据；数量、单位、金额、收料仓和剩余数量正确。
8. 从“登记实际到货”进入收货单时，仅可处理该采购订单的未收明细；超收、跨订单物料由标准服务端拦截。
9. 原采购订单单行定价、采购收货、采购发票、采购申请合并生成采购订单以及移动端表格横向滚动无回归。

## 11. 发布与回滚

发布仅涉及 `mes_integration` 的新增模块、表单脚本、钩子和测试。部署后构建该应用前端资产、清理站点缓存并重启相关 Frappe 进程。

由于没有数据迁移和新表，回滚可移除采购订单专用脚本、钩子和新接口，再构建资产、清理缓存、重启服务。已经按新规则保存的采购订单保留其当时已写入的标准行价；回滚不会自动反算或改写历史订单。

## 12. 预期效果

采购员可以继续按不同收料仓维护多条采购订单明细，同时系统以同物料总下单数量自动命中阶梯价。任何跨阶梯变动都会在明细下方明确说明物料、合计数量、旧单价、新单价和金额影响。

采购订单中的“实际到货情况”展示真实已收货数据，而实际收货仍通过标准采购收货单完成。用户看到的物料、数量、单位、价格、金额和仓库均可追溯到正式收货凭证，库存、质检、应付和采购订单到货状态保持同一条标准链路。
