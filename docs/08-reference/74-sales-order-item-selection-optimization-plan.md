---
title: 销售订单物料选择范围优化方案
---

# 销售订单物料选择范围优化方案

版本：v1.0  
状态：方案沉淀，尚未实施  
范围：销售订单物料搜索、手工录入、复制/映射、Excel 导入、CRM 接口创建  
原则：先治理数据、后启用增强；小增量；默认兼容；不修改 ERPNext 核心和老接口

## 1. 背景与问题定义

销售订单的物料选择结果中混入原材料、半成品、包材等内部生产物料，导致销售人员搜索困难，也增加误下单风险。

问题需要拆成两类，不能使用同一种方式处理：

1. 物料的标准字段“允许销售”`is_sales_item = 0`，但仍能在销售订单搜索结果中出现。这不符合当前 ERPNext 标准逻辑，应先排查现场脚本、缓存、字段值和实际入口。
2. 原材料或半成品的“允许销售”被勾选为 `1`，因此出现在销售订单中。这符合 ERPNext 标准逻辑，根因是主数据含义不清或历史数据设置不准确。

本方案中的“成品”是业务概念，不直接等同于 `is_stock_item`、`has_bom` 或固定的物料组名称。外购商品、配件、样品和服务也可能合法销售，因此不能简单使用“有 BOM”“库存物料”或硬编码“产品”物料组来判断。

## 2. 当前代码基线

当前 ERPNext 已经具备第一层标准保护：

| 能力 | 当前代码位置 | 当前行为 |
| --- | --- | --- |
| 销售订单物料搜索 | `erpnext/public/js/utils/sales_common.js` | 调用标准 `item_query`，传入 `is_sales_item: 1`、`has_variants: 0` 和客户条件 |
| 通用物料查询 | `erpnext/controllers/queries.py::item_query` | 排除禁用、模板、过期物料，并合并前端传入过滤条件和用户权限条件 |
| 销售单据服务端校验 | `erpnext/controllers/selling_controller.py::validate_items` | 调用 `validate_item_type(..., "is_sales_item", "sales")` |
| 物料类型校验 | `erpnext/controllers/buying_controller.py::validate_item_type` | 发现 `is_sales_item = 0` 时阻止销售单据保存/提交 |

因此，本次不应改写以上 ERPNext 文件，也不应覆盖 `erpnext.controllers.queries.item_query`。标准接口已经可以接收附加过滤条件，新增分支只需复用它。

仓库中已有三个应用为 Sales Order 加载脚本：

- `crm_integration`：CRM、收款、生产和履约状态；
- `custom_filters`：销售出货明细展示；
- `client_akivision`：销售订单字段、交付和导出能力。

新的物料准入逻辑建议归属 `client_akivision`，并作为独立脚本和独立 Python 模块追加，避免修改另外两个应用的既有销售订单逻辑。

## 3. 方案结论

### 3.1 第一层：继续以“允许销售”为基础准入

所有销售订单物料必须满足：

```text
Item.disabled = 0
AND Item.is_sales_item = 1
AND Item.has_variants = 0
AND 未超过生命周期结束日期
AND 满足用户权限和客户专属物料规则
```

先盘点并修正主数据：原材料、半成品和包材如果永远不对外销售，应取消“允许销售”；确实可以单独销售的配件、样品或原料则保留。

这一步不需要代码改动，也是优先推荐的处理方式。

### 3.2 第二层：可选的“严格销售目录”

如果业务上确实存在“物料允许用于其他销售场景，但不允许销售人员在销售订单选取”的情况，再新增两个配置：

| DocType | 字段 | 类型 | 默认值 | 用途 |
| --- | --- | --- | ---: | --- |
| Selling Settings | `custom_enable_strict_sales_order_item_filter` | Check | 0 | 全局启用严格销售目录；默认关闭，保证升级后行为不变 |
| Item | `custom_sales_order_selectable` | Check | 0 | 标识是否进入销售订单产品目录 |

严格模式启用后，销售订单准入条件在标准条件上追加：

```text
AND Item.custom_sales_order_selectable = 1
```

两个字段职责不同：

- `is_sales_item` 是 ERPNext 的通用销售资格，保留标准语义和标准校验；
- `custom_sales_order_selectable` 是本企业销售订单目录准入，不替换、不反向同步标准字段；
- 严格开关关闭时完全沿用标准行为；开启前必须完成数据盘点。

不推荐用固定物料组过滤。物料组调整、改名或跨组销售都会改变结果；显式准入字段更容易审计，也不会把采购、库存和生产分类规则耦合进销售流程。

## 4. 用户流程与预期效果

```text
销售人员打开 Sales Order
  -> client_akivision 独立脚本读取 Selling Settings 严格模式开关
  -> 关闭：保留 ERPNext 标准 item_code 查询
  -> 开启：给 Sales Order Item.item_code 追加 custom_sales_order_selectable = 1
  -> 用户输入编码/名称
  -> 继续调用 erpnext.controllers.queries.item_query
  -> 标准查询合并：可销售、未禁用、非模板、客户规则、权限、严格目录
  -> 返回精简后的产品列表
  -> 用户选择物料并保存
  -> Sales Order before_validate 追加服务端准入校验
  -> 标准 Sales Order validate_items 再校验 is_sales_item
  -> 保存/提交成功
```

预期界面效果：

- 严格模式关闭时，销售订单选择行为与当前系统一致；
- 严格模式开启后，只显示同时勾选“允许销售”和“销售订单可选”的物料；
- 原材料、半成品和包材不再污染搜索结果；
- 禁用、模板和受客户专属规则限制的物料仍按 ERPNext 标准规则排除；
- 物料编码精确输入也不能绕过服务端校验；
- 采购订单、物料需求、库存凭证、BOM 和生产工单的物料搜索不变。

## 5. 计划修改的文件与代码

以下均为后续实施计划，本次只创建方案文档，不修改业务代码。

### 5.1 必须新增或修改

| 文件 | 类型 | 计划内容 |
| --- | --- | --- |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/sales_order_item_eligibility.py` | 新增 | 封装严格模式读取、物料准入判定、Sales Order 服务端校验和盘点查询；私有辅助函数不暴露为新接口 |
| `development/frappe-bench/apps/client_akivision/client_akivision/public/js/sales_order_item_filter.js` | 新增 | 仅在严格模式启用时为 `items.item_code` 安装附加查询条件；继续调用标准 `item_query` |
| `development/frappe-bench/apps/client_akivision/client_akivision/hooks.py` | 小改 | 将 Sales Order 的 `doctype_js` 改为脚本数组并追加新脚本；在现有 `before_validate` 列表末尾追加准入校验 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/custom_field_schema.py` | 小改 | 以幂等方式同步 Selling Settings 开关和 Item 准入字段，不修改标准字段定义 |
| `development/frappe-bench/apps/client_akivision/client_akivision/patches/v0_0_1/add_sales_order_item_eligibility_fields.py` | 新增 | 创建字段、输出/记录待治理数量；不自动启用严格模式，不自动批量放行全部销售物料 |
| `development/frappe-bench/apps/client_akivision/client_akivision/patches.txt` | 小改 | 登记一次性 schema patch |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/test_sales_order_item_eligibility.py` | 新增 | 服务端单元测试 |
| `tests/playwright_sales_order_item_filter.mjs` | 新增 | 销售订单搜索和错误提示的端到端验收 |

`hooks.py` 的目标形态是追加而不是替换现有逻辑：

```python
doctype_js = {
	# 其他配置保持不变
	"Sales Order": [
		"public/js/sales_order_delivery.js",
		"public/js/sales_order_item_filter.js",
	],
}

doc_events = {
	"Sales Order": {
		"before_validate": [
			# 现有三个处理函数顺序保持不变
			"client_akivision.utils.sales_order_fields.sync_sales_order_period",
			"client_akivision.utils.sales_order_fields.sync_customer_code",
			"client_akivision.utils.sales_order_fields.sync_customer_sales_person",
			"client_akivision.utils.sales_order_item_eligibility.validate_sales_order_items",
		],
	},
}
```

前端新增分支示意：

```javascript
frappe.ui.form.on("Sales Order", {
	setup(frm) {
		install_strict_sales_item_query(frm);
	},
});

async function install_strict_sales_item_query(frm) {
	const enabled = await get_strict_sales_item_filter_enabled();
	if (!enabled) return;

	frm.set_query("item_code", "items", function () {
		return {
			query: "erpnext.controllers.queries.item_query",
			filters: {
				is_sales_item: 1,
				custom_sales_order_selectable: 1,
				customer: frm.doc.customer,
				has_variants: 0,
			},
		};
	});
}
```

实际实现应缓存开关读取结果，并在安装查询前确认字段存在。查询函数仍是 ERPNext 原接口，不新增或覆盖远程搜索接口。

服务端新增校验示意：

```python
def validate_sales_order_items(doc, method=None):
	if doc.doctype != "Sales Order" or not is_strict_filter_enabled():
		return
	if doc.docstatus == 1 and not doc.is_new():
		return  # 兼容现有已提交订单的允许字段更新流程

	item_codes = {row.item_code for row in doc.items if row.item_code}
	invalid_items = get_ineligible_item_codes(item_codes)
	if invalid_items:
		frappe.throw(_("以下物料不可用于销售订单：{0}").format(", ".join(invalid_items)))
```

实际查询必须一次批量读取所有物料，避免按明细逐行访问数据库；错误信息应包含行号、物料编码以及处理建议。

### 5.2 明确不修改

- 不修改 `erpnext/public/js/utils/sales_common.js`；
- 不修改或覆盖 `erpnext.controllers.queries.item_query`；
- 不修改 `SellingController.validate_items` 和 `validate_item_type`；
- 不修改 Sales Order、Sales Order Item、Item 的 ERPNext JSON；
- 不修改 `crm_integration` 的销售订单创建接口签名、请求体和响应体；
- 不修改 `custom_filters` 的出货明细脚本；
- 不修改采购、库存、BOM、工单、销售出库和销售发票的标准接口。

## 6. 各入口调用链与处理策略

### 6.1 销售订单页面手工选择

```text
Sales Order setup
  -> sales_order_item_filter.js
  -> 读取严格模式开关
  -> frm.set_query(items.item_code)
  -> erpnext.controllers.queries.item_query（老接口）
  -> 返回符合双重准入的物料
```

前端负责减少噪音，服务端负责最终正确性。

### 6.2 手工输入编码、复制和修改草稿

```text
Sales Order.save
  -> client_akivision Sales Order.before_validate 现有函数
  -> validate_sales_order_items（新增末尾分支）
  -> ERPNext Sales Order.validate
  -> SellingController.validate_items（标准校验）
```

直接粘贴编码、浏览器篡改请求或从旧订单复制都不能绕过新增校验。

### 6.3 CRM 创建并提交销售订单

```text
crm_integration.api.create_and_submit_sales_order（接口不变）
  -> frappe.get_doc(payload)
  -> doc.insert(ignore_permissions=True)
  -> Sales Order.before_validate
  -> validate_sales_order_items
  -> doc.submit
  -> ERPNext 标准销售物料校验
```

严格模式开启后，CRM 传入不在销售目录中的物料将返回明确错误。上线前必须先用 CRM 常用物料清单做差异核对，避免接口突然失败。

### 6.4 Excel/批量导入

```text
client_akivision 数据导入
  -> 构造 Sales Order
  -> insert/save
  -> Sales Order.before_validate
  -> validate_sales_order_items
```

不改 Excel 列格式，不要求增加“销售订单可选”列；导入只消费已经维护好的 Item 主数据。

### 6.5 报价单映射到销售订单

报价单可继续沿用标准可销售物料范围。映射成销售订单草稿后，新校验会阻止目录外物料保存。

若后续确认报价环节也只允许正式产品，可在二期复用同一字段为 Quotation 追加查询和校验；一期不扩大范围，以免改变历史报价和商机流程。

### 6.6 销售出库、销售发票和生产

这些下游单据从已提交销售订单取明细，不重新判断当前 Item 的目录勾选状态。原因是订单提交后的物料资格应作为历史业务事实保留，后续取消某个物料的销售资格不能阻断旧订单履约。

下游仍保留其标准状态、数量、库存和权限校验，不修改调用链。

## 7. 兼容与存量数据策略

### 7.1 默认关闭，避免上线即改变业务

新增开关默认值必须是 `0`。代码部署和 migrate 完成后，当前销售订单、CRM、导入和下游流程均保持原行为。

### 7.2 启用前盘点，不自动全量继承

启用前输出以下清单：

| 清单 | 条件 | 用途 |
| --- | --- | --- |
| 标准不可销售却被历史订单使用 | `is_sales_item = 0` 且存在 Sales Order Item | 定位历史或异常入口，不自动改历史订单 |
| 当前可销售但未进入严格目录 | `is_sales_item = 1` 且 `custom_sales_order_selectable = 0` | 由业务确认哪些是真正产品 |
| 严格目录配置矛盾 | `custom_sales_order_selectable = 1` 且 `is_sales_item = 0` | 必须修正，严格目录不能越过标准资格 |
| 未提交草稿含目录外物料 | 草稿 Sales Order 引用了不准入物料 | 启用前处理，否则后续保存会被阻止 |
| CRM 近期使用目录外物料 | CRM 来源订单引用不准入物料 | 避免切换后集成失败 |

不建议把全部 `is_sales_item = 1` 自动复制为“销售订单可选”，否则只会原样复制当前混乱。可以依据业务确认后的物料编码清单批量维护，但批量变更脚本需单独评审，并先导出变更前快照。

### 7.3 历史订单保留

- 不回写历史 Sales Order Item；
- 不因 Item 后续取消准入而阻断已提交订单的出库、开票、取消或状态同步；
- 修订/amend 形成新草稿时按新规则重新校验；
- 现有草稿在严格模式开启后保存时需要符合新规则，启用前必须清理清单。

### 7.4 回滚

出现业务阻断时只需关闭 Selling Settings 严格开关，即恢复 ERPNext 标准 `is_sales_item` 行为。字段和历史配置保留，不删除数据，不需要回滚数据库结构或老接口。

## 8. 受影响模块

| 模块/入口 | 影响 | 处理方式 |
| --- | --- | --- |
| Item 物料主数据 | 新增一个明确准入勾选 | 仅严格模式使用，不改变库存/采购/生产属性 |
| Selling Settings | 新增全局开关 | 默认关闭，可快速回退 |
| Sales Order 页面 | 搜索结果减少 | 前端附加过滤，仍调用标准查询 |
| Sales Order 保存/提交 | 新增严格目录校验 | `before_validate` 追加，不替换标准校验 |
| CRM 销售订单接口 | 请求格式不变；非法物料会失败 | 上线前核对 CRM 使用物料 |
| Excel/Data Import | 模板不变；非法物料会失败 | 错误提示指出物料编码 |
| Quotation -> Sales Order | 映射可以发生，保存时校验 | 一期不改报价模块 |
| Delivery Note / Sales Invoice | 无新增过滤 | 允许历史订单继续履约 |
| Purchase / Stock / BOM / Work Order | 无影响 | 不读取新增字段 |
| 报表和历史数据 | 不改历史结果 | 可另增盘点报表，但非一期必需 |

## 9. 风险与边界

1. 若仅做前端过滤，接口和导入可以绕过，所以必须同时有服务端校验。
2. 若只用物料组过滤，移动物料组可能意外放行或拦截，且配件、服务等合法销售场景难以表达。
3. 若启用时没有维护 `custom_sales_order_selectable`，所有物料都会被严格模式排除，因此启用动作必须放在盘点和验收之后。
4. CRM 接口当前使用 `ignore_permissions=True` 插入，但仍触发文档校验；新增校验会有意约束 CRM 数据，需提前验证错误返回是否能被 CRM 正确展示和重试。
5. Item 在订单提交后被取消准入，不应追溯影响旧订单，否则会阻断出库、开票、取消和接口更新。
6. 如果现场复现 `is_sales_item = 0` 仍能通过标准 Sales Order 保存，应先定位是否使用了非标准 DocType、脚本重设查询、忽略校验标志或缓存未刷新，再决定是否需要修复；不能用第二个字段掩盖这个异常。

## 10. 测试与验收标准

### 10.1 开关兼容

- 新字段部署后严格开关默认关闭；
- 关闭时搜索结果、保存、CRM 和导入行为与部署前一致；
- 开关可反复启停，不修改任何订单或物料数据。

### 10.2 搜索结果

- `is_sales_item = 1` 且严格目录勾选：可搜索；
- `is_sales_item = 1` 但严格目录未勾选：严格模式下不可搜索；
- `is_sales_item = 0`：无论严格目录值如何均不可搜索；
- 禁用、模板、过期物料仍不可搜索；
- 客户专属物料限制与用户权限仍然生效；
- 编码、名称和模糊搜索结果一致。

### 10.3 服务端与旁路入口

- 手工写入目录外编码后保存被阻止；
- 复制旧订单生成新草稿时按新规则校验；
- 修订订单按新规则校验；
- Excel 导入目录外物料时整单失败并返回明确物料信息；
- CRM 创建目录外物料时接口格式不变，并返回可识别的业务错误；
- 合法 CRM 订单仍可创建、提交并进入现有生产状态链路。

### 10.4 下游回归

- 历史已提交订单即使物料后来取消准入，仍可创建销售出库和销售发票；
- 订单取消、状态同步、收款、MES 推送和项目进度同步保持正常；
- 采购订单、物料需求、库存凭证、BOM 和工单仍能选择各自所需物料；
- 页面同时加载 `crm_integration`、`custom_filters` 和 `client_akivision` 脚本时无控制台错误，既有按钮和出货明细正常。

## 11. 分阶段实施建议

### 阶段 A：零代码诊断与数据治理

1. 现场复现并记录搜索入口、物料编码和 `is_sales_item` 实际值；
2. 导出可销售物料并由销售、生产、仓库共同确认；
3. 对永不销售的原材料、半成品和包材取消“允许销售”；
4. 验证标准前端过滤和标准服务端校验；
5. 如果清理后已经满足要求，到此结束，不实施严格目录。

### 阶段 B：部署兼容代码

1. 新增字段、独立脚本、服务端校验和测试；
2. 保持严格开关关闭；
3. 执行自动化回归和现场冒烟测试；
4. 输出待准入物料、存量草稿和 CRM 差异清单。

### 阶段 C：维护目录并灰度启用

1. 业务确认并批量勾选“销售订单可选”；
2. 在测试站点开启严格模式；
3. 验证手工、复制、修订、Excel、CRM、出库和开票链路；
4. 选择低峰期在生产启用；
5. 观察至少一个完整销售订单创建和履约周期。

## 12. 最终预期效果

- 销售订单物料搜索从“所有被标成可销售的物料”收敛为经过确认的产品目录；
- 原料、半成品和包材不再干扰销售人员，同时合法的配件、样品和服务可显式保留；
- 页面搜索、精确输入、复制、导入和 CRM 接口使用同一准入规则，不存在只隐藏不校验的问题；
- ERPNext 标准查询、标准销售校验和所有老接口保持不变；
- 现有 CRM、MES、财务、出库、开票和项目进度逻辑不被替换；
- 严格模式默认关闭且可一键回退，历史订单继续正常履约；
- 如果零代码数据治理已经解决问题，可以不进入代码实施阶段。

## 13. 实施前决策点

进入代码实施前需要业务最终确认：是否确实存在“`is_sales_item = 1`，但不应在 Sales Order 中选择”的物料。

- 如果不存在：只执行阶段 A，统一治理标准“允许销售”，不新增字段和代码。
- 如果存在：执行阶段 B/C，使用本文的独立严格目录字段，不用物料组硬编码。

本文默认推荐先完成阶段 A，再依据盘点结果决定是否实施严格销售目录。
