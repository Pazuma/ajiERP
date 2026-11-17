---
title: 采购订单同物料合并阶梯报价与实际到货实施记录
---

# 采购订单同物料合并阶梯报价与实际到货实施记录

状态：已完成代码实现与离线界面验证；待可用 Frappe 站点完成端到端回归。

## 1. 交付效果

- 采购订单中相同物料、不同收料仓的行仍分别保留；其下单数量按库存单位合计后命中同一个数量阶梯价。
- 命中阶梯后，同组行按各自换算率回写采购单位单价、折扣、金额计算基础和 Pricing Rule 追溯字段。
- 明细表下方仅在本次操作实际改价时显示“阶梯报价调整”，包含合计数量和旧/新单价。
- 原交货计划的业务入口不新增第二份到货数据，而是在明细下方展示已提交采购收货单的实际到货情况，并使用标准收货单创建入口。
- 实际到货区域采用与订单明细一致的 Grid 风格：表头/行选择框、字段选择和“添加行”工具条；展示字段为采购收货单、收货日期、物料编码、物料名称、实际到货数量、单位、单价、金额、收料仓、累计到货、剩余未到货。
- “添加行”并不直接插入到货数据，而是进入标准采购收货单创建流程，保证库存、质检、批次和超收校验不被绕过。
- 实际到货区域采用标准 Grid 的表头、复选框、空态、横向滚动和底部工具条规范；采购订单内所有标准 Table 标题旁增加统一的展开/收纳按钮，状态按用户浏览器保存。

## 2. 修改清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `development/frappe-bench/apps/mes_integration/mes_integration/hooks.py` | 修改 | 注册 Purchase Order 表单 JS/CSS，并在 `Purchase Order.validate` 注册服务端复算钩子。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/purchase_order.py` | 新增 | 新报价预览 API、提交前复算、实际到货只读汇总及可测试的辅助函数。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/public/js/purchase_order.js` | 新增 | 防抖报价预览、行价回写与提示、实际到货表、标准采购收货入口。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/public/css/purchase_order.css` | 新增 | 无边框提示区、到货表样式、移动端横向滚动。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/tests/test_purchase_order_pricing.py` | 新增 | 同物料跨仓分组、单价换算、到货汇总辅助函数测试。 |
| `development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing.mjs` | 新增 | Frappe 表单/API 桩下的 Playwright 界面和交互测试。 |
| `development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing.png` | 新增 | Playwright 移动端截图。 |
| `development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing_result.json` | 新增 | Playwright 可机器读取结果。 |

未修改 ERPNext 核心 Pricing Rule、Purchase Order、Purchase Receipt 文件，也未修改既有接口、数据库表、DocType、Custom Field 或 patch。

## 3. 数据流与调用链路

```text
采购订单明细变更（物料/数量/单位/换算率/仓库/增删行）
  -> purchase_order.js 防抖请求新 API preview_aggregate_item_pricing
  -> purchase_order.py 按 item_code + stock_uom 汇总 stock_qty（不含 warehouse）
  -> ERPNext get_pricing_rule_for_item 查询标准 Pricing Rule
  -> 返回当前明细价格补丁和不支持规则警告
  -> 前端回写单价/折扣/规则，调用标准 calculate_taxes_and_totals
  -> 显示本次阶梯报价调整
  -> 保存或提交时 Purchase Order.validate 再次服务端复算

打开已保存采购订单
  -> get_actual_arrival_summary（新只读 API）
  -> 已提交 Purchase Receipt + Purchase Receipt Item
  -> 实际到货表与按订单行的累计/剩余汇总

点击“登记实际到货”
  -> ERPNext make_purchase_receipt（既有标准接口）
  -> Purchase Receipt 标准校验、库存/质检/批次/应付链路
```

## 4. 依赖清单

| 依赖 | 用途 | 变更 |
| --- | --- | --- |
| Frappe `doctype_js`、`doctype_css`、`doc_events` | 加载表单资源与提交前校验 | 仅新增 Purchase Order 配置。 |
| ERPNext `get_pricing_rule_for_item` | 复用既有采购阶梯规则筛选 | 未修改。 |
| ERPNext `make_purchase_receipt` | 从采购订单生成仅剩余数量的收货单 | 未修改。 |
| Purchase Receipt / Purchase Receipt Item | 实际到货的唯一数据源 | 仅读取已提交记录。 |
| 浏览器 Frappe Form API | 表单刷新、总额计算、路由 | 使用现有 API。 |

## 5. 风险点与控制

| 风险 | 控制措施 | 需要复测 |
| --- | --- | --- |
| 复杂 Pricing Rule 改变历史语义 | 仓库限定、累计、混合条件、其他物料、递归规则会提示并保留原行价。 | 对每种现存复杂规则建单验证。 |
| 不同采购单位的精度 | 合计使用 `stock_qty`，回写按 `conversion_factor` 换算。 | 箱/个等不同 UOM，检查阶梯边界、四舍五入、税费。 |
| 标准单行定价异步覆盖聚合结果 | 聚合请求采用序号，只应用最后一次响应。 | 连续快速修改数量、物料、仓库后保存。 |
| 手工改单价被重算 | 一期没有锁价字段，明细触发字段变更会自动定价。 | 手工锁价需求需另做权限、字段和审计。 |
| 历史交货计划有其他用途 | 本次不删除字段或历史数据，只增加实际到货展示。 | 确认 MRP/承诺交期是否仍读取原字段。 |
| 并发收货/超收 | 仍完全依赖标准 Purchase Receipt 服务端校验。 | 双窗口同时创建并提交收货。 |

## 6. 验证记录

静态检查已通过：

```text
python3 -m py_compile ...purchase_order.py ...test_purchase_order_pricing.py
node --check purchase_order.js
node --check playwright_purchase_order_aggregate_pricing.mjs
git diff --check
```

Playwright 使用 Chromium 在 Frappe 表单/API 桩环境中通过 4 项检查：

1. 实际到货 11 个字段完整，且显示收货行数据。
2. 同物料两行、不同仓库、合计数量 300 时，两行单价均从 `CNY 0.10` 回写为 `CNY 0.08`，提示内容正确。
3. “登记实际到货”路由到标准 `Purchase Receipt` 创建结果。
4. 390px 移动端宽表在内部容器横向滚动，汇总区换行；Grid 工具条和行选择框正常展示。
5. 实际到货区域可展开/收纳；收纳后隐藏汇总、表格和工具条，展开后数据与操作完整恢复。

结果文件：[playwright_purchase_order_aggregate_pricing_result.json](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing_result.json)。截图：[playwright_purchase_order_aggregate_pricing.png](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing.png)。

## 7. 问题记录与解决方案

| 问题 | 影响 | 处理/方案 |
| --- | --- | --- |
| 容器内 Chromium crashpad 套接字被沙箱拒绝 | 首次 Playwright 无法启动。 | 在授权的本地浏览器执行环境重跑，测试通过。 |
| 初版测试引用 jQuery 源码模块，浏览器内没有 `window.jQuery` | 测试桩初始化失败，不影响业务脚本。 | 改为最小 DOM 包装器，覆盖本脚本实际使用的 `find/append/html/show/hide/remove`，重跑通过。 |
| Bench Python 软链接指向不存在的 `/home/frappe/.pyenv/versions/3.14.2/bin/python3`，系统 Python 又缺 `orjson` | 无法在当前环境运行真实 Frappe 单元测试和站点端到端测试。 | 修复 bench 虚拟环境或在有完整依赖的站点执行第 8 节复测；静态编译与离线 Playwright 已完成。 |

## 8. 上线前复测与发布

需在可用 Frappe 站点按以下场景复测：

1. 同物料跨两仓、跨阶梯升降、不同物料互不干扰、删除行恢复低阶梯。
2. 不同采购单位和 UOM 限定 Pricing Rule 的换算与税费总额。
3. 草稿、提交、取消采购收货单只统计已提交到货；累计/剩余与订单行一致。
4. 标准收货单只携带未收完行，批次、序列号、质检、超收和并发收货仍受标准校验。
5. 浏览器绕过、导入/API 创建采购订单时，`validate` 仍按合计数量复算。
6. 既有单行报价、采购发票、采购申请合并生成订单无回归。

部署后执行应用资源构建、站点清缓存、迁移并重启 Frappe 进程；具体命令应使用目标环境既有发布流程。回滚时移除本次 Purchase Order 的 hook 与静态资源后重新构建和清缓存；已保存订单保留当时的标准行价，不自动改写历史单据。
