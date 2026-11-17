# 销售订单无法选择导入物料：排查与修复

## 现象

物料已导入，在物料页面检查时显示“允许销售”，但新建销售订单时搜索不到该物料。

## 原因

销售订单中的物料查询不是只检查“允许销售”。ERPNext 默认还会过滤以下条件：

- `is_sales_item = 1`：允许销售
- `disabled = 0`：物料未禁用
- `has_variants = 0`：不是变体父项
- `end_of_life` 为空，或晚于当前日期
- 当前用户拥有物料读取权限
- 当前客户没有通过 Party Specific Item 规则排除该物料

相关逻辑位于：

- `apps/erpnext/erpnext/public/js/utils/sales_common.js`
- `apps/erpnext/erpnext/controllers/queries.py`

## 第一步：确认站点

本地环境可能同时存在多个站点，例如 `dev.localhost` 和 `aki_test.localhost`。必须确认导入和创建销售订单使用的是同一个站点。

```bash
cd /home/cst/frappe_docker/development/frappe-bench
bench --site aki_test.localhost console
```

后续 SQL 和控制台操作均应针对 `aki_test.localhost`，不要切换到 `dev.localhost`。

## 第二步：查询物料状态

在 MariaDB 中执行：

```sql
SELECT
    name,
    item_code,
    item_name,
    disabled,
    is_sales_item,
    has_variants,
    end_of_life,
    item_group
FROM `tabItem`
WHERE name = '<物料编码>'
   OR item_code = '<物料编码>';
```

正常情况下应满足：

```text
disabled = 0
is_sales_item = 1
has_variants = 0
end_of_life 为空，或大于当前日期
```

## 第三步：检查导入脚本造成的批量禁用

当前临时导入脚本包含以下逻辑：

```python
for name in frappe.get_all('Item', pluck='name', limit_page_length=0):
    if name not in valid:
        frappe.db.set_value('Item', name, 'disabled', 1, update_modified=False)
```

这会把“不在本次 Excel 有效编码列表中的所有物料”设置为禁用。即使物料的 `is_sales_item=1`，只要 `disabled=1`，销售订单中仍然不会显示。

可先查询最近被禁用的物料：

```sql
SELECT name, item_code, item_name, disabled, is_sales_item, modified
FROM `tabItem`
WHERE disabled = 1
ORDER BY modified DESC;
```

## 第四步：检查客户专属物料规则

销售订单按客户查询时，Party Specific Item 规则可能排除物料。检查当前客户是否存在相关规则：

```sql
SELECT name, party_type, party, restrict_based_on, based_on_value
FROM `tabParty Specific Item`
WHERE party_type = 'Customer'
  AND party = '<客户名称或编码>';
```

如规则按物料、物料组或品牌限制销售，需要确认该物料是否被排除。

## 临时修复

确认物料编码正确且业务上允许销售后，可在物料页面手工确认：

1. `禁用` 取消勾选。
2. `允许销售` 勾选。
3. 确认不是变体父项。
4. 清空已过期的 `生命周期结束日期`，或填写未来日期。
5. 保存后刷新销售订单页面，并重新搜索物料编码。

也可以在受控环境中使用 Bench 控制台修复单个物料：

```python
item = frappe.get_doc('Item', '<物料编码>')
item.disabled = 0
item.is_sales_item = 1
item.save(ignore_permissions=True)
frappe.db.commit()
```

## 导入规范

后续导入物料时应遵循：

- 新建和更新都显式写入 `is_sales_item`、`disabled`、`has_variants`、`end_of_life`。
- 导入脚本不得默认禁用所有“不在本次文件中的物料”。如需停用，应使用单独的停用清单并二次确认。
- 导入完成后，随机抽查物料，并用 SQL 验证上述字段。
- 导入和销售订单操作必须明确站点名称，避免跨站点核查。

## 验证标准

修复后，在同一站点中：

1. 物料列表能按编码和名称找到该物料。
2. 物料字段满足 `disabled=0`、`is_sales_item=1`。
3. 新建销售订单，选择客户后，在明细行搜索该物料编码可以返回。
4. 保存销售订单时不再提示物料不可用于销售。
