---
title: 多采购申请合并生成采购订单实施沉淀
---

# 多采购申请合并生成采购订单实施沉淀

版本：v1.0  
对应方案：[15-material-request-merge-purchase-order-plan.md](15-material-request-merge-purchase-order-plan.md)

## 1. 实施结果

已在采购申请列表增加“合并生成采购订单”批量入口。用户选择多张已提交、采购类型且有剩余数量的采购申请后，在确认弹窗中选择一个供应商，系统按来源明细生成一张未保存的采购订单草稿。

本次实现不创建“合并采购申请”单据，不修改或提交原采购申请，不修改 ERPNext 核心接口。采购订单保存、提交、收货、结算和付款仍沿用标准 ERPNext 流程；采购订单行保留 `material_request` 与 `material_request_item` 来源字段。

## 2. 修改文件与代码说明

### 2.1 后端接口

文件：`development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/material_request.py`

新增白名单方法：`make_merged_purchase_order(material_requests, supplier, selected_items=None)`。

主要逻辑：

- 解析 JSON 字符串、数组或单值参数，去重并限制单次最多 50 张申请。
- 校验当前用户具有 `Purchase Order` 创建权限、供应商读取权限和每张采购申请读取权限。
- 校验申请已提交、类型为 `Purchase`、状态不是 `Stopped` / `Cancelled`，且所有申请属于同一公司。
- 校验明细名称确实属于所选申请，并且存在 `stock_qty > ordered_qty` 的剩余数量。
- 创建一个内存中的 `Purchase Order`，依次调用 ERPNext 原生 `make_purchase_order`，每次只传入当前申请的明细名称：

```python
target_doc = erpnext_make_purchase_order(
    material_request.name,
    target_doc=target_doc,
    args={"filtered_children": list(request_item_names)},
)
```

- 返回未保存的采购订单文档；接口本身没有 `insert`、`save` 或 `submit`。

### 2.2 前端列表入口

文件：`development/frappe-bench/apps/mes_integration/mes_integration/public/js/material_request_list.js`

新增函数职责：

- `merge_purchase_requests_to_purchase_order`：读取列表勾选项并启动流程。
- `validate_merge_candidates`：前端提前校验状态、类型、公司和剩余数量。
- `show_merge_candidate_errors`：集中展示不可合并原因。
- `show_merge_purchase_order_dialog`：展示统一供应商字段、公司和完整明细确认表。
- `open_merged_purchase_order`：调用后端接口，使用 `frappe.model.sync` 同步草稿并跳转 Purchase Order 表单。

明细确认表包含：采购申请、物料编码、物料名称、剩余数量、单位、仓库、要求日期。表格容器在窄屏下启用横向滚动，避免撑破视口。

### 2.3 Playwright 检查资产

- 脚本：`development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order.mjs`
- 结果：`development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order_result.json`
- 截图：`development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order.png`
- 真实站点入口截图：`development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order_real.png`

## 3. 数据流与调用链路

```text
Material Request 列表
  -> 勾选多张申请
  -> 合并生成采购订单
  -> frappe.client.get 读取完整申请
  -> 前端校验并展示确认弹窗
  -> 用户选择 Supplier 并确认
  -> make_merged_purchase_order
  -> 后端权限、状态、公司、明细归属和剩余数量校验
  -> 创建内存 Purchase Order
  -> 对每张申请调用 ERPNext make_purchase_order
  -> 标准 mapper 写入来源、数量、仓库和日期
  -> 返回未保存 Purchase Order
  -> frappe.model.sync + 跳转采购订单表单
  -> 用户检查价格/税费/交期后保存、提交
  -> 标准 ERPNext 更新申请 ordered_qty / per_ordered
  -> Purchase Receipt 分批收货
  -> Purchase Order.per_received = 100 后按现有流程结算付款
```

数量以服务端标准 mapper 为最终依据。前端仅用于预览；确认时后端会重新读取数据库，避免并发下单导致数量过期。相同物料不会跨申请聚合，来源行一一保留。

## 4. 依赖清单

| 依赖 | 用途 | 变更 |
| --- | --- | --- |
| Frappe `frappe.whitelist` / `frappe.call` | 暴露和调用接口 | 复用现有能力 |
| Frappe `frappe.client.get` | 读取列表勾选的申请 | 复用现有接口 |
| Frappe `frappe.model.sync` / `frappe.set_route` | 将草稿同步到表单并导航 | 复用现有能力 |
| ERPNext `make_purchase_order` | 标准映射、剩余数量和来源字段 | 不修改核心 |
| ERPNext Purchase Order / Item 标准字段 | 供应商、公司、来源申请、数量、仓库、交期 | 不新增字段 |
| `format_number` 与 Frappe number format | 弹窗数量格式化 | 运行时已有全局函数 |
| Chromium + Playwright | UI/DOM 自动化检查 | 仅测试依赖 |

不需要数据库迁移、Custom Field、第三方运行时包、`hooks.py` 或 `patches.txt` 变更。

## 5. 风险点与处理方式

| 风险 | 处理方式 |
| --- | --- |
| 跨公司申请造成会计维度冲突 | 前后端均强制同公司 |
| 并发下单导致预览数量过期 | 后端确认时重新读取并复用标准 mapper |
| 伪造其他申请明细名称 | 服务端校验明细归属，并按当前申请传 `filtered_children` |
| 相同物料来源丢失 | 不聚合明细，保留 `material_request` / `material_request_item` |
| 无权限用户看到入口 | 服务端权限校验为最终防线，返回标准权限错误 |
| 供应商触发价格、地址和税费未刷新 | 跳转表单时设置 `__run_link_triggers`，提交前要求人工复核 |
| 旧批量发料功能回归 | 新入口和函数独立，未改发料分支；需回归验证 |
| 未到齐直接结算 | 一期不改全局财务校验，按 `per_received = 100` 业务规则执行；强制拦截列为二期需求 |
| 真实页面环境不可用 | 当前无运行中的 Frappe HTTP 服务，已记录为上线前阻塞复测项 |

## 6. 已执行检查与结果

已执行：

```bash
python3 -m py_compile development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/material_request.py
/home/cst/frappe_docker/development/erpnext.official/.tools/node/bin/node --check development/frappe-bench/apps/mes_integration/mes_integration/public/js/material_request_list.js
/home/cst/frappe_docker/development/erpnext.official/.tools/node/bin/node development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order.mjs
git diff --check
```

结果：Python、JavaScript 语法检查通过，`git diff --check` 通过。Playwright Chromium 轻量 DOM/交互检查通过：

- 批量入口存在；
- 供应商、公司及 7 个明细字段完整；
- 两张申请的两行物料正确显示；
- 供应商、申请和明细参数完整传递；
- 成功路由到未保存 Purchase Order；
- 390px 视口下明细表在容器内横向滚动，无视口级溢出。

已执行真实站点登录后的 Playwright 入口复测：访问 `http://aji_test.localhost:8200`，使用 `Administrator/admin` 登录，进入采购申请列表，勾选申请并打开“操作”菜单，确认“合并生成采购订单”可见且可点击。当前测试数据中的采购申请主要为已取消或已收货状态，没有可直接用于完整合并下单的有效样本，因此真实接口、权限和数据库写入链路仍需在准备有效测试数据后复测。轻量脚本使用真实前端源文件和浏览器渲染验证确认弹窗、参数和移动端布局，不能替代完整业务联调。

## 7. 上线前需要复测的场景

1. 两张同公司申请、不同物料：生成一张订单，来源字段和数量正确。
2. 相同物料来自两张申请：订单保留两行，分别回写来源申请。
3. 部分已下单：只生成剩余数量；全部已下单、草稿、Stopped、Cancelled、非 Purchase 必须阻断。
4. 跨公司、无 Supplier 读取权限、无 Purchase Order 创建权限：错误提示明确且不落库。
5. 订单保存、提交、取消：申请 `ordered_qty` / `per_ordered` 正确增加和回退。
6. 多次 Purchase Receipt：部分到货时不可按整单结算，全部到齐后 `per_received = 100`。
7. 供应商变更后的地址、价格表、币种、税费和付款条款刷新正确。
8. 原有单张“创建采购订单”、批量发料入口、列表 indicator 无回归。
9. 桌面和 390px 移动端：弹窗字段、表格滚动、供应商输入和主按钮不重叠。

## 8. 已发现问题及解决方案

- 发现原实现对每张申请传入全部选中明细集合，存在未来扩展时跨申请过滤的歧义；已改为每次仅传当前申请的 `request_item_names`。
- 发现后端错误信息格式化存在多余空格；已清理，避免代码风格噪声。
- 首轮 Python 语法检查发现 `_parse_unique_names` 的异常分支缩进错误；已修正并通过复查。
- 真实站点入口复测初次受缓存和应用未安装影响；已在 `aji_test.localhost` 安装 `mes_integration`，执行 `clear-cache` 与 `bench build --app mes_integration` 后恢复。当前仍缺少有效的已提交且有剩余数量的采购申请样本，解决方案是按第 7 节准备专用测试数据后完成端到端复测。

## 9. 发布、缓存与回滚

发布时更新上述两个 `mes_integration` 文件，重启 Frappe/后台进程，执行前端资产构建并清理站点缓存，再按第 7 节复测。无需数据库迁移。

回滚仅需移除新增列表入口和后端白名单接口，重启服务并重新构建/清理缓存。已经保存或提交的 Purchase Order 属于标准 ERPNext 单据，不受代码回滚影响。

## 10. 预期用户效果

采购员可以从采购申请列表一次选择多张申请，统一指定供应商，在一个确认窗口中核对完整来源明细，然后直接进入一张可编辑的采购订单草稿。订单保存提交后继续使用标准收货和财务流程，全部到齐的判断以采购订单标准 `per_received` 为准，来源可追溯且不引入新的业务单据类型。
