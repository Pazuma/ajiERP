---
title: 物料列表安全库存与物料库存显示实施沉淀
---

# 实施结果

本次采用小增量方式完成 Item 列表展示增强：保留 ERPNext 原生列表和旧接口，新增一个只读批量接口，前端按当前页一次请求库存上下文。`Item.safety_stock` 继续作为物料级安全库存；仓库级阈值单独显示为“仓库安全库存”，不把多个仓库值合并成单值。

## 修改文件

- `development/frappe-bench/apps/custom_filters/custom_filters/public/js/item_list.js`
  - 保留物料组筛选包装并合并原有 list settings。
  - 请求 `safety_stock`、`stock_uom`，将 `item_name`/`safety_stock` 标题兜底为中文。
  - 增加可由列表字段设置控制的“物料库存”和“仓库安全库存”虚拟列。
  - 当前页批量加载，翻页或筛选时通过请求键丢弃旧响应；接口失败时仅摘要列显示 `-`。
- `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/api/item_list.py`
  - 新增 `get_item_list_stock_context` 只读接口。
  - 批量读取 `Item.stock_uom`、`Bin.actual_qty`、`Item Reorder.warehouse_reorder_level`，返回结构化 JSON。
  - 去重并限制最多 100 个物料编码，检查 Item、Bin、Item Reorder、Warehouse 读取权限。
- `development/frappe-bench/apps/client_akivision/client_akivision/config/excel_form_fields.json`
  - 持久化将 `Item.item_name` 标签设为“物料名称”。
  - 将 `Item.safety_stock` 标签设为“安全库存”并加入列表视图。
- `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/api/test_item_list.py`
  - 增加空请求及结构化库存/补货行回归测试。

## 数据流

```text
Item ListView -> reportview 读取 item_name/safety_stock/stock_uom
              -> 当前页 item_code 批量调用 get_item_list_stock_context
              -> Item + Bin.actual_qty + Item Reorder.warehouse_reorder_level
              -> 临时字段 warehouse_stock_summary / warehouse_safety_stock_summary
              -> 仓库维度摘要、单位、负库存提示和 tooltip
```

库存使用 `Bin.actual_qty`，不是 Excel 快照 `custom_live_stock_qty`，也不是包含计划量的 `projected_qty`。没有 Bin 时显示 `-`；零库存默认省略，负库存显示“欠 N”；前端最多展示三个仓库，其余放入 tooltip。

## 依赖清单

- Frappe ListView 的 `add_fields`、`setup_columns`、`before_render`、`frappe.call` 和 formatter 机制。
- ERPNext `Item`、`Bin`、`Item Reorder`、`Warehouse` DocType 及对应读取权限。
- `custom_filters` 已有 Item `doctype_list_js` 挂载点。
- 修改配置后发布需执行 `bench migrate`、`bench clear-cache`；前端资源变更需构建对应 app。

## 风险点与控制

| 风险 | 控制 |
| --- | --- |
| 仓库级安全库存被误当成物料级 | 使用独立“仓库安全库存”列并保留仓库名 |
| 列表请求过多 | 每页单次批量请求，最多 100 个编码，不逐行 RPC |
| 翻页竞态 | 响应返回前校验当前页请求键 |
| 权限不足 | 服务端统一检查读取权限；失败仅摘要列降级 |
| 库存口径错误 | 固定使用 `Bin.actual_qty`，不回写 Item |
| Property Setter 缓存 | 配置源已修改，发布后 migrate/clear-cache 并强刷 |
| 虚拟列不能原生排序导出 | 明确为展示列；排序/导出需求另建报表 |

## 复测场景

1. Item 列表表头显示“物料名称”“安全库存”，并可在字段设置中启用“物料库存”。
2. `螺丝` 的 `Item.safety_stock=15` 时显示 `15.00`（按站点精度）。
3. 多仓库、零库存、负库存、不同 stock UOM、超过三个仓库及无 Bin。
4. 翻页、筛选、刷新后数据不串行；浏览器 Network 每页最多一个上下文请求。
5. 无 Item Reorder/Bin 权限、接口异常或超时，列表仍可打开且摘要列为 `-`。
6. Excel 物料和安全库存导入的内部字段映射保持 `item_name` 与 `reorder_levels.warehouse_reorder_level`。

## 验证记录

已完成：接口代码人工审查、配置定位、文档链路核对；容器内 `bench execute` 空请求通过，真实站点 `aji_test.localhost` 的“螺丝”（编码 `common item1`）返回 `stock_uom=Nos`、`仓库 - T=10`、`进行中 - T=14`，仓库安全库存均为 `12`；新增 Python 测试文件已纳入。

未完成：宿主机缺少可执行的 Python、Node 和 Playwright/Chromium；容器内虽可执行 Python/Node，但站点测试默认关闭（`Testing is disabled for the site!`），且未发现 Playwright/Chromium，因此无法完成浏览器截图、控制台错误和像素布局检查。进入 bench 容器并启用测试后执行：

```bash
bench --site <site> migrate
bench --site <site> clear-cache
bench build --app custom_filters --app client_akivision
bench --site <site> run-tests --module client_akivision.client_akivision.api.test_item_list
```

随后用 Playwright 验证上述六类场景，并记录截图、Network 请求数和 console error；若接口失败，应确认列表主体仍可用，仅新增摘要列降级为 `-`。
