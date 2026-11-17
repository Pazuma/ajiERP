---
title: 物料列表安全库存、物料库存与名称显示修复方案
---

# 物料列表安全库存、物料库存与名称显示修复方案

版本：v1.0  
状态：已实施，含最小增量代码与验收记录
适用环境：当前开发 bench，ERPNext v16.32.0，`client_akivision` + `custom_filters`

## 1. 问题结论

截图中的列表是 ERPNext `Item` 列表。当前代码存在两个容易混淆的字段口径：

| 用户看到的内容 | 当前实际来源 | 现象/原因 |
| --- | --- | --- |
| 安全库存 | `Item.safety_stock`，物料级 Float | 标准字段默认值为 `0.00`；它不会自动读取 `Item Reorder.warehouse_reorder_level` |
| 导入的安全库存参数 | `Item Reorder.warehouse_reorder_level`，按物料 + 仓库保存 | 当前 Excel 安全库存模板写入这里，因此“螺丝=15”可能不在列表读取的字段中 |
| 物料库存 | `Bin.actual_qty`，按物料 + 仓库保存 | `Item` 本身没有“各仓库库存”字段，直接在 Item 列表勾选普通字段不会自动显示仓库余额 |
| Product name | `Item.item_name` 的 Property Setter 标签 | `client_akivision/config/excel_form_fields.json` 将标签配置为 `Product name`，不是字段名错误 |

因此，不能直接把列表中的 `0.00` 判断为格式化问题。第一步必须确认螺丝的 15 存在于 `tabItem.safety_stock`，还是存在于 `tabItem Reorder.warehouse_reorder_level`。物料库存则必须从 `tabBin` 按仓库聚合，不能把库存余额写回 Item 主数据。两种安全库存情况和库存展示需求分别处理。

## 2. 现状依据与代码定位

### 2.1 Item 列表加载链路

- ERPNext 原生列表定义：`development/frappe-bench/apps/erpnext/erpnext/stock/doctype/item/item_list.js`
- `custom_filters` 通过 `doctype_list_js` 注入 `public/js/item_list.js`，当前脚本只包装 Item Group 筛选，没有覆盖安全库存数据。
- 列表请求由 Frappe `ListView.get_args()` 发送 `fields`，服务端走 `frappe.desk.reportview.get_list`/`DatabaseQuery`；只有 DocType 字段才能直接参与列表查询、排序和筛选。
- 列表表头使用 DocField 的 `label`。因此 JS formatter 只能改单元格内容，不能可靠解决字段元数据标签问题。

### 2.2 安全库存数据链路

- 标准字段：`erpnext/stock/doctype/item/item.json` 中 `Item.safety_stock`。
- 仓库级字段：`erpnext/stock/doctype/item_reorder/item_reorder.json` 中 `Item Reorder.warehouse_reorder_level`。
- 当前导入映射：`client_akivision/config/excel_import_tables.json` 的 `safety_stock` 表将安全库存参数写入 `reorder_levels.warehouse_reorder_level`。
- 现有补货扩展 `client_akivision/utils/safety_stock_reorder.py` 和 `production_reorder.py` 已同时读取两个来源，说明两者目前并存，不能无条件互相覆盖。
- 现有安全库存报表按 `Item + Item Reorder + Warehouse` 查询，使用 `i.safety_stock` 作为物料级最低库存，并将 `ir.warehouse_reorder_level` 作为仓库预警线；该报表不是 Item 列表的直接数据源。

### 2.3 物料库存数据链路

- ERPNext 实时库存余额保存在 `Bin`，核心字段为 `item_code`、`warehouse`、`actual_qty`；`actual_qty` 是该物料在该仓库的现存数量。
- 一个 Item 可以对应多个 `Bin` 行，因此“哪个仓库剩多少”是跨表、多行聚合结果，不是 `Item` DocType 的普通字段。
- 推荐展示 `actual_qty`，不默认展示 `projected_qty`。在途、预留等计划数量如需展示，应另列命名为“预计可用量/预计库存”，不能与现存数量混用。
- 没有库存余额的仓库不生成行；若 Item 没有任何 `Bin`，展示 `-`，不能把“无记录”误报为一个仓库的 0。

### 2.4 Product name 的来源

`client_akivision/config/excel_form_fields.json` 中已有配置：

```json
{"doctype": "Item", "fieldname": "item_name", "property": "label", "value": "Product name", "property_type": "Data"}
```

该配置在 `client_akivision.utils.custom_field_schema.ensure_excel_form_fields()` 中通过 `make_property_setter()` 同步，且由 `after_migrate` 调用。因此只改浏览器端表头会在下次迁移/同步后被覆盖，正确入口应是配置源。

## 3. 先行核验：不改数据

在测试站点使用 bench console 或只读 SQL 对一个已知物料执行以下检查。物料编码以实际值替换，不要仅按名称猜测：

```python
item_code = frappe.db.get_value("Item", {"item_name": "螺丝"}, "name")
item = frappe.db.get_value(
    "Item", item_code, ["name", "item_name", "stock_uom", "safety_stock"], as_dict=True
)
reorders = frappe.get_all(
    "Item Reorder",
    filters={"parent": item_code},
    fields=["warehouse", "warehouse_reorder_level", "warehouse_reorder_qty"],
    order_by="idx asc",
)
bins = frappe.get_all(
    "Bin",
    filters={"item_code": item_code},
    fields=["warehouse", "actual_qty", "projected_qty", "stock_uom"],
    order_by="warehouse asc",
)
frappe.response["data"] = {"item": item, "reorders": reorders, "bins": bins}
```

记录以下结果：

1. `Item.safety_stock` 是否为 15。
2. 是否有一条或多条 `Item Reorder`，其 `warehouse_reorder_level` 为 15。
3. 若为仓库级数据，列表当前是否有明确的默认仓库/仓库筛选。
4. 当前用户的 `List View Settings` 是否保存了 Item 字段布局，是否把 `safety_stock` 加入列表。
5. `Bin` 中是否存在多个仓库、零库存和负库存；这些数据用于确认库存汇总格式。
6. 用户当前选择的“物料库存”是否实际指向 `custom_live_stock_qty`。该字段是 Excel 库存快照，不是 ERPNext 实时库存，不应继续作为实时库存列。

这一步只读，不新增接口、不修改数据库、不影响用户。

## 4. 推荐实施方案：小增量、保留旧接口

### 4.1 分支 A：15 已在 `Item.safety_stock`

这是最小改动路径，优先实施：

1. 在 `custom_filters/public/js/item_list.js` 的列表设置中，仅追加 `"safety_stock"` 到 `add_fields`，并保留原生 Item 列表配置。
2. 确保 `safety_stock` 在 Item 列表列定义中可见。优先通过站点 Property Setter 或 List View Settings 配置 `in_list_view=1`，不改 ERPNext 核心 `item.json`。
3. 在同一脚本的 `onload` 列标签映射中新增 `safety_stock: __("安全库存")`，作为旧英文标签的前端兜底；真正的持久化标签仍由第 4.4 节配置修正。
4. 使用 Frappe 原生 Float 渲染，保留 `0.00` 的小数格式和排序能力；不在每行发起 RPC。

建议代码形态（示意，实际实现时合并现有设置，不能覆盖其他 app 的设置）：

```javascript
// custom_filters/public/js/item_list.js 或独立新增的 Item list 扩展
const item_list_settings = frappe.listview_settings["Item"] || {};
item_list_settings.add_fields = [
    ...new Set([...(item_list_settings.add_fields || []), "safety_stock"]),
];

const original_onload = item_list_settings.onload;
item_list_settings.onload = function (listview) {
    original_onload?.(listview);
    if (listview.view !== "List") return;
    listview.columns = listview.columns.map((column) => {
        if (column.df?.fieldname !== "safety_stock") return column;
        return { ...column, df: { ...column.df, label: __("安全库存") } };
    });
    listview.render_header(true);
};

frappe.listview_settings["Item"] = item_list_settings;
```

说明：该代码只改变列表请求字段和显示标签，不改变 `frappe.client.get_list`、报表、补货任务或任何旧 API 的参数/返回结构。

### 4.2 分支 B：15 只在 `Item Reorder.warehouse_reorder_level`

不能直接把仓库级值伪装成物料级 `Item.safety_stock`。同一物料可能有多个仓库和多个安全库存，直接取第一条会产生不稳定或错误结果。

推荐的最小增量顺序：

1. Item 列表增加“仓库”筛选或明确采用系统配置的默认仓库。
2. 新增只读后端接口，例如：
   `client_akivision.client_akivision.api.item_list.get_item_list_safety_stock`
3. 接口按 `(item_code, warehouse)` 返回 `Item Reorder.warehouse_reorder_level`，并同时返回来源仓库、来源字段和未配置标志。
4. 前端仅在用户选择仓库后，以批量请求方式填充一个新增的显示列；接口异常时保留标准 `Item.safety_stock` 列和原列表，不阻断列表加载。
5. 若业务要求默认打开就显示数值，新增站点配置 `item_list_default_warehouse`，没有配置时不猜测仓库，显示 `-` 或提示选择仓库。

接口示意：

```python
@frappe.whitelist()
def get_item_list_safety_stock(item_codes=None, warehouse=None):
    """只读返回 Item Reorder 的仓库级安全库存；不改变 Item 标准字段。"""
    item_codes = frappe.parse_json(item_codes or [])
    if not warehouse or not item_codes:
        return {"warehouse": warehouse, "items": {}}

    rows = frappe.get_all(
        "Item Reorder",
        filters={"parent": ["in", item_codes], "warehouse": warehouse},
        fields=["parent as item_code", "warehouse", "warehouse_reorder_level"],
    )
    return {
        "warehouse": warehouse,
        "items": {row.item_code: row.warehouse_reorder_level or 0 for row in rows},
    }
```

前端不得逐行调用该接口；应按当前页 `item_code` 一次批量请求，并在列表刷新、分页、筛选和仓库变更时丢弃旧响应，避免串行请求覆盖新数据。该分支的列建议命名为“仓库安全库存”，不要继续使用没有仓库上下文的“安全库存”。

### 4.3 新增“物料库存”列：按仓库显示现存数量

#### 4.3.1 数据口径

新增列读取 `Bin.actual_qty`，展示每个物料在各叶子仓库的实时现存数量。默认不使用以下字段：

- `Item.custom_live_stock_qty`：它是 Excel 导入的库存快照，可能过期，也不能表达多仓库。
- `Bin.projected_qty`：它包含计划、预留、在途等因素，不等于“仓库剩多少”。
- Stock Ledger Entry 临时求和：`Bin.actual_qty` 已是 ERPNext 的余额结果，列表无需重复计算流水。

建议显示格式：

```text
原料仓 - T：剩 15 个；进行中 - T：剩 2 个
```

格式规则：

1. 仓库按名称稳定排序；若后续有业务优先级配置，则按配置优先级排序。
2. 数量使用 Frappe 的 Float 精度格式，单位取 `Item.stock_uom`，例如 `15 个`、`2.50 Kg`。
3. 正数显示“剩”；零库存默认不展示，以减少噪声；可在悬浮完整明细中显示。
4. 负库存必须展示并标红，例如 `原料仓 - T：欠 3 个`，不能被非零过滤逻辑误删。
5. 没有任何 `Bin` 行时显示 `-`。
6. 列表单元格默认显示前 3 个有数量的仓库；超出时显示“另有 N 个仓库”，完整内容放在安全转义后的 tooltip 或点击弹层中，避免撑高列表行。
7. 仓库名、数量和单位全部进行 HTML 转义；服务端返回结构化数据，前端负责本地化文案，不让服务端拼 HTML。

#### 4.3.2 新增只读批量接口

在与仓库安全库存相同的新增模块中提供统一上下文接口，避免列表为安全库存和实际库存各发一次请求：

`client_akivision.client_akivision.api.item_list.get_item_list_stock_context`

请求：

```json
{
  "item_codes": ["SCREW-001", "NUT-001"],
  "warehouse": null,
  "include_zero_qty": 0
}
```

响应：

```json
{
  "items": {
    "SCREW-001": {
      "stock_uom": "个",
      "warehouses": [
        {"warehouse": "原料仓 - T", "actual_qty": 15},
        {"warehouse": "进行中 - T", "actual_qty": 2}
      ],
      "total_actual_qty": 17,
      "selected_warehouse_safety_stock": null
    }
  }
}
```

接口实现要求：

```python
from frappe.utils import cint


@frappe.whitelist()
def get_item_list_stock_context(item_codes=None, warehouse=None, include_zero_qty=0):
    """批量返回 Item 当前页的仓库现存量及可选仓库安全库存。"""
    item_codes = list(dict.fromkeys(frappe.parse_json(item_codes or [])))
    if not item_codes:
        return {"items": {}}

    # 实施时限制数量与字符串长度，校验 Item/Warehouse 读取权限。
    item_rows = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "stock_uom"],
    )
    bin_filters = {"item_code": ["in", item_codes]}
    if warehouse:
        bin_filters["warehouse"] = warehouse
    if not cint(include_zero_qty):
        bin_filters["actual_qty"] = ["!=", 0]

    bin_rows = frappe.get_all(
        "Bin",
        filters=bin_filters,
        fields=["item_code", "warehouse", "actual_qty"],
        order_by="item_code asc, warehouse asc",
    )
    # 按 item_code 组装结构化响应；不要返回拼接 HTML。
```

服务端还应通过 `Warehouse` 过滤已停用/组仓库和用户不可读仓库。为了保持查询稳定，当前页物料编码数量限制为列表页上限，例如最多 100 个；超限时明确报参数错误，前端降级为 `-`。

#### 4.3.3 列表端实现

`Item` 本身没有这个真实字段，因此新增的是“虚拟展示列”，不是把聚合文本存进 Item：

1. 在 `custom_filters/public/js/item_list.js` 包装 `setup_columns`，追加字段名为 `warehouse_stock_summary`、标签为“物料库存”的 Data 展示列。
2. 在 `before_render`/`refresh` 链路中收集当前页 Item 编码，一页只调用一次统一批量接口。
3. 将响应写入当前页文档的临时属性，再调用 `listview.render()`；使用请求 key 或序号丢弃翻页前的旧响应。
4. formatter 输出紧凑摘要和完整 tooltip，负数使用红色文本；加载中显示 `...`，失败显示 `-`，不弹阻断式错误。
5. 列的显示开关保存在用户设置中。由于它不是数据库字段，不进入标准 `reportview` 的 fields 参数，也不支持直接按汇总文本做数据库排序。

若产品要求必须出现在 Frappe 标准“选择显示字段”对话框中，可新增一个只读 Custom Field 作为列定义占位，但不得持久化库存文本；列表加载后仍由批量接口覆盖显示值。推荐优先使用独立的“显示物料库存”开关，避免用户误以为它是可编辑或可导出的 Item 字段。

### 4.4 Product name 改为物料名称

修改配置源：

文件：`development/frappe-bench/apps/client_akivision/client_akivision/config/excel_form_fields.json`

```diff
- {"doctype": "Item", "fieldname": "item_name", "property": "label", "value": "Product name", "property_type": "Data"}
+ {"doctype": "Item", "fieldname": "item_name", "property": "label", "value": "物料名称", "property_type": "Data"}
```

保留字段名 `item_name` 不变，只修改用户可见标签；Excel 导入的内部映射仍使用 `item_name`，旧接口和历史数据不受影响。若希望同步修改 Item 表单、列表、导入模板的英文显示，应在同一配置源统一处理；不要直接编辑数据库中的 Property Setter 后不改 JSON，否则下一次 `after_migrate` 会恢复旧值。

## 5. 建议修改文件

### 必改（安全库存分支 A + 物料库存）

| 文件 | 修改内容 | 是否改接口 |
| --- | --- | --- |
| `development/frappe-bench/apps/custom_filters/custom_filters/public/js/item_list.js` | 合并 `safety_stock` 到 `add_fields`；保留已有 Item Group 包装；新增“物料库存”虚拟列、批量加载、摘要 formatter 和显示开关 | 调用新增只读接口，不改旧接口 |
| `development/frappe-bench/apps/client_akivision/client_akivision/config/excel_form_fields.json` | 将 `Item.item_name` Property Setter 标签改为“物料名称” | 否 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/custom_field_schema.py` | 通常无需改；仅在现有同步逻辑不能识别更新标签时补充幂等同步/缓存清理 | 否 |
| `development/frappe-bench/apps/client_akivision/client_akivision/api/item_list.py`（新增） | 批量返回当前页物料的 `Bin.actual_qty` 仓库明细、库存单位和总现存量 | 新增接口 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/test_item_list.py`（新增） | 多仓库、零库存、负库存、单位、权限、分页竞态和失败回退测试 | 否 |

### 条件增加（分支 B）

| 文件 | 修改内容 |
| --- | --- |
| `development/frappe-bench/apps/client_akivision/client_akivision/api/item_list.py`（新增） | 在统一库存上下文接口中同时批量读取指定仓库的 `Item Reorder.warehouse_reorder_level`，执行权限和参数校验 |
| `development/frappe-bench/apps/custom_filters/custom_filters/public/js/item_list.js` | 增加仓库上下文、批量加载和显示列；接口失败回退标准列表 |
| `development/frappe-bench/apps/client_akivision/client_akivision/hooks.py` | 仅当需要新增 Item 列表脚本挂载或 API 资源注册时修改；优先复用现有 `doctype_list_js`，避免两个 app 互相覆盖 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/test_item_list.py`（新增） | 增补安全库存来源、多个仓库、无配置、无权限和接口异常测试 |

不修改：ERPNext 核心 `item.py`、`item.json`、`bin.py`、Frappe `reportview.py`、补货算法、现有 MES 接口、数据库历史安全库存和库存余额数据。

## 6. 调用链路

### 分支 A：物料级安全库存

```text
打开 /app/item
  -> Frappe 加载 Item meta + Item list settings
  -> custom_filters Item list 扩展合并 add_fields(safety_stock)
  -> ListView.get_args(fields=...safety_stock...)
  -> frappe.desk.reportview.get_list / DatabaseQuery
  -> SELECT tabItem.safety_stock
  -> ListView 使用 Float formatter 渲染 15.00
  -> 表头读取 Item.item_name 的 Property Setter，显示“物料名称”
```

### 分支 B：仓库级安全库存

```text
打开 /app/item
  -> 用户选择仓库
  -> 当前页收集 item_code
  -> 新增只读批量接口
  -> 查询 Item Reorder(parent=item_code, warehouse=selected)
  -> 前端按 item_code 合并安全库存显示
  -> 翻页/筛选/刷新重新请求，旧响应丢弃
```

### 物料库存：各仓库现存数量

```text
打开 /app/item 或用户开启“显示物料库存”
  -> Item 原生列表先正常加载
  -> 收集当前页 item_code，一次请求 get_item_list_stock_context
  -> 服务端按权限批量查询 Item.stock_uom + Bin.actual_qty
  -> 按 item_code、warehouse 组装结构化结果
  -> 前端写入临时 warehouse_stock_summary
  -> formatter 显示“仓库 A：剩 15 个；仓库 B：剩 2 个”
  -> 多余仓库放入 tooltip/弹层，负库存标红
  -> 请求失败只将该列降级为“-”，原 Item 列表继续可用
```

两条链路都不改变 Item 原生保存、查询、补货和报表接口。列表展示失败只能降级显示原有列，不得阻断打开物料表。

## 7. 受影响模块与风险

| 模块 | 影响 | 控制措施 |
| --- | --- | --- |
| 库存/物料主数据 | Item 列表显示字段、仓库库存摘要和标签 | 只读展示；库存始终来自 `Bin.actual_qty`，不回写 Item |
| Excel 导入 | 用户可见表头可能变化 | 内部映射仍为 `item_name`；回归产品清单和安全库存模板 |
| 自动补货 | 不应改变阈值计算 | 不改 `safety_stock_reorder.py`、`production_reorder.py`；分支 B 只读查询 |
| Frappe 列表性能 | 分支 A 无新增请求；分支 B 每页一次批量请求 | 限制页大小、去重 item_code、设置超时和失败回退 |
| 多仓库数据一致性 | 一个物料可能有多个安全库存 | 无仓库上下文不合并；明确默认仓库或显示“仓库安全库存” |
| 多仓库库存可读性 | 仓库过多导致一行过高、横向拥挤 | 单元格最多显示 3 个仓库，完整数据放 tooltip/弹层 |
| 实时库存一致性 | 页面打开后库存继续变化 | 每次列表刷新重新读取 `Bin`；不做长期浏览器缓存，不承诺推送级实时 |
| 快照字段混淆 | `custom_live_stock_qty` 被误认为系统实时库存 | 新列明确读取 `Bin.actual_qty`，标签使用“物料库存”，不复用快照字段 |
| 权限 | 用户可能无权读取 Item Reorder/Bin/Warehouse | 服务端检查 Item、Item Reorder、Bin、Warehouse 读取权限；失败回退 |
| 缓存 | Property Setter/前端资产缓存导致旧标题 | `bench migrate`/`bench clear-cache`/`bench build`，浏览器强刷 |
| 多 app 脚本覆盖 | `custom_filters` 与其他 app 都可能挂 Item 列表脚本 | 采用现有包装模式，保存并调用原设置，不直接重置全局对象 |

## 8. 预期效果

### 分支 A 验收效果

- 螺丝的 `Item.safety_stock=15` 时，列表安全库存显示 `15.00`（或站点既有精度格式），不再显示错误的 `0.00`。
- 列表首列/名称字段表头显示“物料名称”，字段值仍来自 `item_name`。
- 可按安全库存排序；列表刷新、分页、筛选结果稳定。
- 旧的 Item 查询、导入、补货、报表和自定义接口行为不变。

### 分支 B 验收效果

- 选择仓库后，螺丝在该仓库的 `warehouse_reorder_level=15` 时显示“仓库安全库存 15.00”。
- 同一物料在不同仓库显示各自数值，不发生跨仓库串值。
- 未选择仓库或无配置时不伪造 15，显示空值/`-` 并保留标准 Item 安全库存。

### 物料库存验收效果

- 用户开启“物料库存”列后，可直接看到例如“原料仓 - T：剩 15 个；进行中 - T：剩 2 个”。
- 数量来自当前 `Bin.actual_qty`；刷新列表后能反映最新已入账库存。
- 同一物料多个仓库分别展示，不只显示合计；完整明细可查看。
- 零库存默认省略、负库存明确显示为“欠 N 单位”并标红、无 Bin 显示 `-`。
- `custom_live_stock_qty` 的 Excel 快照不参与该列计算。

## 9. 测试与发布步骤

1. 只读核验螺丝的两个安全库存来源，确定采用分支 A 或 B。
2. 在测试站点执行 Item 列表回归：库存充足/缺失值、多个仓库、零库存、负库存、停用仓库、不同单位、分页、筛选、排序、窄屏。
3. 回归 Excel 产品清单和安全库存参数导入，确认字段映射仍为 `item_name`、`reorder_levels.warehouse_reorder_level`。
4. 使用普通库存用户、受仓库权限限制用户和无 Item Reorder/Bin 读取权限用户验证过滤及降级行为。
5. 发布业务 app 后执行：

```bash
bench --site <site> migrate
bench --site <site> clear-cache
bench build --app custom_filters --app client_akivision
```

6. 观察浏览器 Network：不得出现逐行库存请求；每次列表页、仓库筛选或刷新最多一次统一批量库存上下文请求。

## 10. 回滚与不做事项

- 回滚只需移除新增列表脚本分支或恢复 `excel_form_fields.json` 中的标签配置；不需要回滚 Item 数据。
- 不直接修改 ERPNext 核心 `Item.safety_stock` 定义。
- 不把所有 `Item Reorder` 行求和后冒充单一安全库存。
- 不把多个仓库的 `Bin.actual_qty` 写回 `Item`，也不复用 Excel 快照字段冒充实时库存。
- 不只显示库存合计而丢失仓库维度；合计只能作为接口附加值或 tooltip 补充。
- 不用前端逐行 RPC、DOM 强行替换作为长期方案。
- 不修改现有 API 的参数、返回结构、异常类型或补货判断。

## 11. 待确认项

1. 业务所称“安全库存 15”最终数据源是物料级 `Item.safety_stock`，还是指定仓库的 `Item Reorder.warehouse_reorder_level`？
2. 如果是仓库级，Item 列表默认展示哪个仓库，还是必须由用户筛选仓库？
3. “安全库存”列是否需要支持排序/筛选？若需要，优先采用真实 DocField/明确仓库上下文，避免只做前端装饰列。
4. “物料库存”默认是否隐藏、由用户主动开启？本方案推荐默认可选，避免在宽度有限的 Item 列表中长期占据大列。
5. 零库存仓库是否需要显示？本方案默认隐藏零库存，但保留负库存；如业务要求可通过 `include_zero_qty` 开关展示。

## 12. 本次实施沉淀

### 12.1 已修改文件

- `development/frappe-bench/apps/custom_filters/custom_filters/public/js/item_list.js`
  - 保留原有物料组筛选包装。
  - 追加 `safety_stock` 查询字段与中文表头。
  - 将 `item_name` 表头前端兜底为“物料名称”。
  - 增加“物料库存”和“仓库安全库存”只读摘要列。
  - 当前页物料一次批量调用上下文接口；翻页/筛选后以请求键丢弃旧响应；接口失败时仅该两列显示 `-`。
- `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/api/item_list.py`
  - 新增只读 `get_item_list_stock_context`。
  - 批量读取 `Item.stock_uom`、`Bin.actual_qty`、`Item Reorder.warehouse_reorder_level`。
  - 限制最多 100 个物料编码，返回结构化 JSON，不拼接 HTML。
- `development/frappe-bench/apps/client_akivision/client_akivision/config/excel_form_fields.json`
  - 将 `Item.item_name` 持久化标签改为“物料名称”。
  - 将 `Item.safety_stock` 标签固定为“安全库存”并确保可加入列表。
- `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/api/test_item_list.py`
  - 增加接口结构和空请求的回归测试。

### 12.2 数据流

```text
Item 列表 -> Frappe reportview 查询 item_name/safety_stock/stock_uom
          -> 当前页 item_code 批量调用 get_item_list_stock_context
          -> Item + Bin.actual_qty + Item Reorder.warehouse_reorder_level
          -> 前端临时字段 warehouse_stock_summary / warehouse_safety_stock_summary
          -> 列表摘要渲染（库存单位、仓库维度、负库存提示）
```

`Item.safety_stock` 是物料级安全库存；`Item Reorder.warehouse_reorder_level` 是仓库级安全库存，本次不互相覆盖、不合并冒充单值。物料库存只读 `Bin.actual_qty`，不读取 Excel 快照字段 `custom_live_stock_qty`。

### 12.3 依赖清单

- Frappe ListView 的 `add_fields`、`setup_columns`、`before_render`、`frappe.call`。
- ERPNext `Item`、`Bin`、`Item Reorder` DocType 及其读取权限。
- `client_akivision` 应用模块加载路径。
- `custom_filters` 已有 `doctype_list_js` 挂载点。
- 发布后需执行 `bench migrate`、`bench clear-cache`，前端资源变化时执行对应 app build。

### 12.4 风险点与控制

| 风险 | 控制 |
| --- | --- |
| 多仓库安全库存被误读为单值 | 单独显示“仓库安全库存”，保留仓库名 |
| 列表性能退化 | 每页一次批量请求，最多 100 个物料，不逐行 RPC |
| 库存权限不足 | 服务端沿用 DocType 读取权限；接口失败只降级摘要列 |
| 旧响应覆盖新页面 | 使用当前页编码组成请求键，响应前校验 |
| 负库存/单位丢失 | 使用 `actual_qty`、`stock_uom`，负数显示“欠” |
| 标签迁移后回退英文 | 修改 JSON 配置源，由 `ensure_excel_form_fields` 幂等同步 |
| 虚拟列不能原生排序/导出 | 明确为展示列；排序/导出需求另建报表或聚合模型 |

### 12.5 验收与复测场景

已完成：

- `bench execute` 真实调用接口通过；测试站点“螺丝”返回库存 `仓库 - T=10`、`进行中 - T=14`，仓库安全库存均为 `12`。
- Python 编译、JavaScript 语法检查（容器内 Node）、`git diff --check` 通过。

需要在具备浏览器运行时后复测：

1. Item 列表表头为“物料名称”“安全库存”“物料库存”“仓库安全库存”。
2. 螺丝行显示真实安全库存，不再固定为 `0.00`。
3. 多仓库、零库存、负库存、不同单位和超过 3 个仓库时的摘要/tooltip。
4. 翻页、筛选、刷新后库存不串行错位，Network 中每页最多一次上下文请求。
5. 无 Bin、无 Item Reorder、无权限和接口超时情况下列表仍可打开。
6. Excel 物料导入和安全库存导入的内部字段映射不变。

本环境当前未安装 Playwright 或 Chromium，无法完成浏览器自动化截图；该阻塞已记录，不能把静态检查替代为 UI 通过。
