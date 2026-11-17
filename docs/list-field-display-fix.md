# 列表视图已选择字段但未显示：原因与修复方案

## 1. 问题现象

在供应商列表中，列表视图设置里已经包含“供应商名称”，但实际列表第一列显示的是供应商编号，例如 `SUP-2026-00001`，没有显示供应商名称。

客户列表和入库单列表存在同类问题：列表第一列可能显示系统编号，而不是业务名称。

该问题与 `Data Import` 字段选择器无关，属于列表视图列渲染逻辑覆盖了 Frappe 原生标题字段。

## 2. 根因

Frappe 列表视图会把 DocType 的 `title_field` 固定作为第一列：

- `Supplier.title_field = supplier_name`
- `Customer.title_field = customer_name`
- `Purchase Receipt.title_field = supplier_name`

对应代码位于：

```text
apps/frappe/frappe/public/js/frappe/list/list_view.js:417-422
```

列表初始化时，Frappe 创建的第一列类型为 `Subject`，其字段分别是 `supplier_name`、`customer_name` 或 `supplier_name`。

但客户端应用在以下文件中将该列强制替换为 `name`：

```text
apps/client_akivision/client_akivision/public/js/supplier_list.js:85-93
apps/client_akivision/client_akivision/public/js/customer_list.js:55-63
apps/client_akivision/client_akivision/public/js/purchase_receipt_list.js:29-37
```

供应商和客户列表的当前逻辑等价于：

```javascript
subject_col.df = {
	fieldname: "name",
	label: __("供应商编号"),
	fieldtype: "Data",
};
```

因此产生以下结果：

1. 列表设置仍然把 `supplier_name` / `customer_name` 作为固定首列展示，所以设置弹窗看起来是正确的。
2. 列表实际渲染时，`Subject` 列已经被改成 `name`，因此显示的是编号。
3. `remove_duplicate_name_column()` 又删除了原生自动追加的编号列，导致名称和编号不能同时正常出现。

这也解释了为什么其他使用相同“重写 Subject 列”模式的表单可能出现类似问题：只要 DocType 的 `title_field` 不是 `name`，就可能把业务名称替换成系统编号。

## 3. 其他表单的统一处理方式

其他表单出现“设置中已选字段但列表不显示”时，按以下顺序排查，不要直接修改 Frappe 公共 `ListView`：

### 3.1 先区分字段未查询还是列未渲染

- `add_fields` 只表示把字段加入列表查询，**不会自动把字段显示为列**。
- 列表列来源主要是 DocType 字段的 `in_list_view`、保存的列表视图字段配置，以及脚本对 `listview.columns` 的修改。

### 3.2 检查 DocType 的 `title_field`

如果问题是第一列显示编号而不是名称，检查：

```text
frappe.get_meta("目标表单").title_field
```

如果自定义列表脚本包含以下逻辑，应删除该逻辑：

```javascript
const subject_col = listview.columns.find((col) => col.type === "Subject");
subject_col.df = { fieldname: "name", ... };
```

`Subject` 应保留 Frappe 根据 `title_field` 创建的字段。需要显示编号时，让 Frappe 自动追加 `name` 列，或在列表设置中单独选择编号。

### 3.3 检查列表视图保存配置

如果脚本没有覆盖 `Subject`，继续检查“列表视图设置”中是否保存了旧字段顺序。处理方式是：

1. 打开目标表单列表；
2. 打开列表视图设置；
3. 移除失效字段并重新添加；
4. 保存后刷新页面。

如果仍不显示，再清理该 DocType 的 `List View Settings` 记录或通过开发环境重新保存一次默认列配置。不要直接改数据库业务数据。

### 3.4 检查列数和字段元数据

- 字段必须有正确的 `fieldname`，并且用户有读取权限；
- 普通业务字段需要设置 `in_list_view = 1`，或加入列表视图保存配置；
- Frappe 列表最多保留 `max_number_of_fields` 个列，当前默认值为 50；
- 屏幕宽度较小时，列可能被隐藏或折叠，应先确认 DOM 中是否存在该列，再判断是否为 CSS 或宽度问题。

### 3.5 只对确有业务目的的脚本做定制

当前仓库中的 `crm_integration` 销售订单脚本只追加业务员、产品列，没有覆盖 `Subject`，不属于本次根因，可以保留。

`china_finance` 的会计凭证列表脚本会把“会计凭证”和“付款记录”的首列改为来源凭证号，这是明确的业务需求，不应按本问题自动删除；如果用户希望显示原始标题，需要单独调整该业务规则。

## 4. 修复原则

保留 Frappe 的 `Subject` 列，不再覆盖 `title_field`。这样可以：

- 供应商列表继续使用 `supplier_name` 作为第一列；
- 客户列表继续使用 `customer_name` 作为第一列；
- 入库单列表继续使用 `supplier_name` 作为第一列；
- 保留列表设置、权限、排序和原有扩展列逻辑；
- 在需要显示编号时，由 Frappe 原生逻辑追加 `name` 列；
- 不修改 `data_import.js`，避免影响 Excel 导入字段选择和模板下载。

## 5. 本次已修改文件与代码

### 5.1 供应商列表

文件：

```text
apps/client_akivision/client_akivision/public/js/supplier_list.js
```

将 `setup_supplier_columns` 和 `remove_duplicate_name_column` 修改为：

```javascript
function setup_supplier_columns(listview) {
	supplier_list_settings._listview = listview;
}
```

删除以下旧代码：

```javascript
// 第一列：勾选框 + 供应商编号（显示 name）
const subject_col = (listview.columns || []).find((col) => col.type === "Subject");
if (subject_col) {
	subject_col.df = {
		fieldname: "name",
		label: __("供应商编号"),
		fieldtype: "Data",
	};
}
remove_duplicate_name_column(listview);
```

同时删除不再需要的函数：

```javascript
function remove_duplicate_name_column(listview) {
	const index = (listview.columns || []).findIndex(
		(col) => col.type === "Field" && col.df?.fieldname === "name"
	);
	if (index !== -1) listview.columns.splice(index, 1);
}
```

### 5.2 客户列表

文件：

```text
apps/client_akivision/client_akivision/public/js/customer_list.js
```

将 `setup_customer_columns` 和 `remove_duplicate_name_column` 修改为：

```javascript
function setup_customer_columns(listview) {
	customer_list_settings._listview = listview;
}
```

删除客户列表中对应的 Subject 覆盖代码和 `remove_duplicate_name_column` 函数。

### 5.3 入库单列表

文件：

```text
apps/client_akivision/client_akivision/public/js/purchase_receipt_list.js
```

该文件只用于覆盖 `Subject` 列，没有其他业务逻辑。建议直接停用该自定义列表脚本：

1. 从 `apps/client_akivision/client_akivision/hooks.py` 的 `doctype_list_js` 中删除：

```python
"Purchase Receipt": "public/js/purchase_receipt_list.js",
```

2. 删除文件：

```text
apps/client_akivision/client_akivision/public/js/purchase_receipt_list.js
```

这样会恢复 ERPNext 原生入库单列表逻辑，并保留 `supplier_name` 作为标题字段。

## 6. 不修改的文件

### `data_import.js`

该文件只负责：

- 获取可导入表单；
- 获取可导入字段；
- 过滤只读字段；
- 校验字段选择；
- 下载 Excel 模板。

它不负责 Desk 列表视图的列渲染，因此不应在此处增加兼容逻辑。

## 7. 验证步骤

1. 更新上述三个 JS 文件并执行前端资源构建或清理缓存。
2. 重新登录或使用浏览器强制刷新。
3. 打开“供应商”列表，确认第一列显示“供应商名称”，例如“供应商1”。
4. 打开列表视图设置，确认“供应商名称”仍然存在且为固定首列。
5. 如需显示编号，确认 `name` 作为独立列出现；如果列数受屏幕宽度限制，可在列表设置中调整显示字段。
6. 打开“客户”列表，确认第一列显示“客户名称”。
7. 打开“入库单”列表，确认第一列显示供应商名称，而不是入库单号；如需入库单号，确认 `name` 作为独立列显示。
8. 验证状态、供应商类型、供应商评级、供应商备注、筛选、排序和新增记录功能不受影响。
9. 新建一条 Excel 导入任务，确认模块、业务表、字段选择和模板下载仍正常。

## 8. 风险与回滚

本修复只取消三个列表脚本对 Frappe `Subject` 列的覆盖，不修改数据库字段、DocType 元数据、权限或导入接口，风险较低。

如需回滚，只恢复三个文件中原来的 `setup_*_columns` 和 `remove_duplicate_name_column` 实现即可。

## 9. 结论

本问题的核心不是字段没有被选择，也不是数据库缺少业务名称，而是自定义列表脚本把 Frappe 原生的业务标题字段替换成了 `name`。修复应集中在 `supplier_list.js`、`customer_list.js` 和 `purchase_receipt_list.js`，通过保留原生 `Subject` 列恢复名称显示，并避免修改导入相关代码。
