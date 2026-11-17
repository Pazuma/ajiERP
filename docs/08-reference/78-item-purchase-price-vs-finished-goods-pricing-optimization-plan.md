---
title: 物料采购价格与成品定价分域优化方案
status: 待评审，未实施
---

# 物料采购价格与成品定价分域优化方案

## 1. 目标与边界

业务口径：采购物料的价格来源于采购侧的有效供应商报价及其派生的购买型价格数据；“定价”页不参与采购物料取价。成品的对外销售价格由销售定价侧维护。这里的“物料价格”指采购询价、比价和下单使用的采购单价，不等同于库存估值率、实际入库成本、BOM 成本或财务成本；本方案不修改后四者的计算口径。

不按 `is_stock_item`、是否存在 BOM 或页面所在页签直接推断价格方向：同一 Item 可能既采购又销售，成品也可能外购。按交易场景决定取价域：采购单据只使用购买型报价/规则，销售单据只使用销售型定价。若业务确实要求某些物料不得销售或某些成品不得采购，应另设业务资格约束，不通过清除另一侧历史价格实现。

本文件是设计方案，当前不修改代码、数据库、接口或现有数据。待确认口径：无有效供应商报价时，采购是否允许使用历史采购订单价作为明确标记的参考价；建议保留现有比价回退用于参考，但不得伪装为“供应商报价”，也不得将销售定价作为回退。

## 2. 现状与问题（按仓库代码核对）

| 位置 | 现状 | 风险 |
| --- | --- | --- |
| `custom_filters/public/js/item.js` | 物料“采购”表的供应商行已可打开“供应商报价规则”弹窗；“定价”页另加载阶梯价格表 | 采购报价的编辑与展示分属两个页签 |
| `custom_filters/custom_filters/item_details.py` | `get_item_tier_pricing` 从 Pricing Rule 查询该物料规则，没有按 `buying/selling` 分域 | 购买型阶梯规则可能显示在定价页，被理解为销售定价 |
| 两个既有物料字段 patch | `custom_cf_tier_pricing_html` 锚定 `prices_html`，位于定价页 | 只修改 JS 不能真正移动展示位置 |
| `custom_filters/item_supplier_pricing.py` | 保存物料供应商规则，并同步购买型 Item Price 或 Pricing Rule | 标准价格表是采购规则的落地载体，不能简单删除 |
| `client_akivision` 采购推荐/比价 | 同时考虑购买型规则、已提交报价、Item Price、历史采购价；公式规则也参与比价 | 必须复核购买型与供应商、币种、数量、有效期过滤，避免混入销售价格 |
| `mes_integration` 采购订单校验 | 采购订单存在同物料合计阶梯取价逻辑 | 改展示时仍须保持实际订单取价一致 |

截图中的 ERPNext 原生“物料价格 / Add Price”区块由标准 Item 页面提供，可能同时显示购买和销售价格；仅移动自定义阶梯表不足以完成页面分域，须单独评估原生区块的展示能力和最小化前端调整，不能误称已完全分离。

## 3. 目标调用链路

采购维护：物料 → 采购页供应商行/供应商报价单 → 供应商报价规则或正式报价 → 保留既有同步 → 购买型 Pricing Rule / Item Price → 采购页展示“供应商/数量/币种/有效期/来源”。

采购取价：采购申请数量 → 采购推荐与供应商比价 → 按供应商、采购单位/换算、数量档、公司、币种、有效期匹配购买型报价/规则 → 来源与价格快照 → 采购订单复核及取价 → 采购收货按原有逻辑计算实际成本。定价页和销售型价格不进入这条链路。

销售取价：销售报价/订单 → 销售型 Item Price / Pricing Rule → 成品对外售价；物料页面的“定价”页只承担销售定价展示，不读取供应商购买型规则。既有销售取价接口和 ERPNext 原生逻辑保持不变。

## 4. 小增量实施设计及拟修改文件

| 文件或位置 | 预期修改（实施阶段） | 预期效果 |
| --- | --- | --- |
| `development/frappe-bench/apps/custom_filters/custom_filters/custom_filters/item_details.py` | 保留 `get_item_tier_pricing(item_code)` 现有签名与响应结构，优先新增采购规则查询入口，例如 `get_item_purchase_pricing(item_code)`；定价页调用旧入口时仅返回销售型规则。新入口限定 `buying=1`、供应商，并明确禁用/过期状态的展示口径；权限分别校验 Item 与相关报价/规则 | 旧调用方无参数兼容问题；采购规则与销售规则不再混排。变更旧入口结果语义须先检索其他调用方并回归 |
| `development/frappe-bench/apps/custom_filters/custom_filters/public/js/item.js` | 在采购页新增独立报价展示加载、渲染和刷新分支，复用现有供应商弹窗；定价页只渲染销售规则。保存弹窗后刷新采购区块，保留旧表格列和原有按钮行为 | 采购维护和查看聚合，定价页不展示购买型阶梯 |
| `development/frappe-bench/apps/custom_filters/custom_filters/patches/` 新增幂等 patch（并注册至 `patches.txt`） | 新建采购页 HTML 字段并锚定采购页已有稳定字段；旧 `custom_cf_tier_pricing_html` 留在定价页用于销售规则，避免直接迁移历史字段。实际锚点需先读取 Item 元数据验证 | 无须改写或重跑旧 patch，可回滚新展示而不丢历史配置 |
| `development/frappe-bench/apps/custom_filters/custom_filters/item_supplier_pricing.py`、供应商报价同步处理代码 | 原保存、提交/取消与同步接口原则上不改；仅补充必要的来源标记、有效性过滤或展示适配，确认同步结果始终 `buying=1, selling=0` 且供应商一致 | 保留老报价、阶梯规则和 ERPNext 原生采购取价兼容性 |
| `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/report/purchase_recommendation/purchase_recommendation.py` | 核查并按需收紧 `_get_tier_rules_by_item`、`_get_item_prices_by_item` 等采购读取分支，明确只读取购买型、供应商关联价格；不改报告公开参数和返回结构 | 采购推荐不会将销售定价当采购价格 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/purchase_comparison.py` | 保留 `run_comparison` 和既有接口；复用上述采购引擎及公式规则，核实来源优先级和快照，不在此重建第二套取价规则 | 比价结果与采购推荐一致，来源可追溯 |
| `development/frappe-bench/apps/mes_integration/mes_integration/purchase_order.py` | 核查同物料聚合阶梯逻辑只命中购买型供应商规则；只有发现越域取价时增加购买域保护分支，不改 ERPNext 核心接口 | 采购订单按原数量阶梯正确取价，且不受销售规则干扰 |
| 对应测试文件（优先 `custom_filters/tests/`、`client_akivision` 与 `mes_integration/tests/`） | 新增采购/销售同物料隔离、多供应商阶梯、失效报价、原有下单及页面交互用例 | 能证明分域不破坏旧链路 |

涉及 Item 原生“物料价格”区块时，先验证 ERPNext 当前版本是否已有购买/销售过滤能力；若无，仅增加局部页面展示过滤或提示，不篡改标准 DocType/控制器，也不删除历史 Item Price。若原生区块无法安全过滤，需在验收中明确其仍显示混合价格，另列为后续独立改进，而不能声称页面完全分域。

## 5. 取价口径与关联模块

1. 正式报价、供应商规则、同步的购买型规则/Item Price 属于采购域；同一报价的派生数据不得被当作不同来源重复比价。公式规则沿用现有计算服务，报价取消/失效后不得继续作为有效报价。
2. 采购推荐、采购申请比价、采购订单（含合计数量阶梯）必须共用一致的购买域筛选；采购订单上的人工改价及已有审批行为不因页面调整被强制覆盖。
3. 报价缺失时保留“未报价”或标注“历史采购价参考”的状态；禁止静默拿销售价补齐。采购报表与比价行的 `price_source`、报价号、命中数量档继续可追溯。
4. 定价页销售规则和销售订单只消费销售型数据；是否允许非成品销售仍由现有销售业务规则决定。本次不以 Item 分类为由改动销售单据可用性。
5. 库存估值、采购入库、BOM 成本、财务核算、已有数据及权限体系保持原状；新增采购展示接口需遵守 Item、供应商报价、Pricing Rule 的读取权限，不因页面展示泄露供应商底价。

### 5.1 生产工单与财务的成本价链路（补充范围）

“生产工单和流转到财务使用成本价”，这里明确为：**不使用成品销售定价或供应商报价直接记账**。供应商报价用于采购决策及采购订单定价；采购收货/发票按实际交易与库存计价形成原料成本，生产领料沿库存计价结转，生产完工归集材料成本及适用的人工/制造费用，财务消费有来源凭证的实际成本与差异。工单尚未领料时允许展示“预计成本”，但必须标识为估算，与已发生的实际成本分开。

```text
供应商报价 → 采购比价 → 采购订单价格
                            │
                            ▼
                     采购收货/实际入库
                            │
                            ▼
                    原材料库存成本价
                            │
                            ▼
                    生产工单领料实际成本 ─┐
                                        ├→ 完工成品成本 → 库存/销售成本 → 财务凭证与报表
                    人工/制造费用（如启用） ─┘

成品销售定价 → 销售订单售价 → 收入/应收（不是生产或库存成本）
```

关联核查与拟改范围：ERPNext 原生 `manufacturing/doctype/work_order/`、`manufacturing/doctype/bom/`、`stock/doctype/stock_entry/`、`stock/stock_ledger.py` 的估算、领料、完工、库存计价调用链；财务侧对应库存凭证、总账及成本报表；仓库自定义的生产/财务成本展示或同步代码。实施前应逐条定位具体自定义调用方和文件，原则上**不修改 ERPNext 原生成本及总账控制器**。如发现某个自定义工单/财务字段当前直接读取 `Item Price` 或销售 `Pricing Rule` 作为成本，仅对该消费点新增“实际库存成本/工单成本”分支，并保留旧接口结构；未发现越域读取时不改代码。采购报价与实际入库价不一致时，按现有采购、库存、财务规则处理差异，不用报价追溯覆盖已入账成本。

补充验收：工单开工前的预计成本与领料后的实际成本分别标识；领料单价取库存计价而不是销售定价；完工成品成本可追溯到领料及工费，财务凭证与库存价值相符；更改供应商报价或销售定价不会回写历史工单、库存账或总账。

### 5.2 已定位的生产、财务关联文件及改动边界

| 文件 | 当前调用/数据事实 | 拟处理方式与预期效果 |
| --- | --- | --- |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/sales_order_production_cost.py` | `refresh_from_stock_entry` 在库存凭证提交/取消后异步刷新；`refresh_sales_order_cost` 从已提交生产 Stock Entry 明细 `basic_amount` 汇总材料、成品成本，配送成本来自 Stock Ledger Entry 的 `stock_value_difference`，收入来自 Delivery Note | 首先回归核查，不改计算接口。仅在发现预计报价误入实际成本时加独立成本来源校验/展示分支；预计成本不得写入 `custom_material_cost` 等实际值。预期销售订单成本/毛利继续按已发生库存数据计算 |
| `development/frappe-bench/apps/client_akivision/client_akivision/hooks.py` | Work Order、Stock Entry、Delivery Note 等已有成本校验和刷新 hook | 原 hook 不删、不换顺序；只有新增实际必要的事件时追加处理，不扩大同步写账时机。预期取消与重新提交仍能正确刷新 |
| `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/report/sales_order_production_cost_and_margin/sales_order_production_cost_and_margin.py` | 报表消费销售订单的材料、生产、交付成本及毛利字段 | 核查显示标签区分实际与预计；只有新增预计字段时增加可选列，不替换实际成本列。预期报表与已提交凭证一致 |
| `development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/stock_entry.py` | MES 入库准备阶段调用 `calculate_rate_and_amount`；没有正成本时存在 `allow_zero_valuation_rate=1` 分支 | 单列零成本安全用例与异常告警评审；不能为满足“成本价”要求直接将报价写入 `valuation_rate`。若真实生产数据存在错误零成本，另开最小修复分支并确认 MES 配置和库存计价口径 |
| `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/report/realtime_inventory/realtime_inventory.py` 与 `.../doctype/material_stocktake_summary/material_stocktake_summary.py` | 实时库存/盘点已有库存价值和估值率的消费 | 回归确认仍展示库存估值成本，不用采购报价覆盖现有盘点差额与库存价值 |
| ERPNext 原生 Work Order、BOM、Stock Entry、Stock Ledger / GL；`china_finance` 财务扩展 | 原生库存凭证与总账是实际成本的权威链路；财务扩展存在采购收货关联 hook | 先做调用/配置核查，默认不改原生文件或财务过账；如发现自定义财务消费点把销售定价当成本，才在该消费点新增分支并列明具体文件。预期库存与财务可对账 |

以上“拟处理”不是宣称现有生产或财务取价错误：已核对的订单生产成本计算使用已提交库存凭证而不是销售 Item Price；改造重点是采购页面分域、跨模块回归及针对实际发现的越域调用小范围修补。

### 5.3 可执行回归清单

| 场景 | 预期结果 |
| --- | --- |
| 同物料采购报价 8、销售定价 12，采购订单按有效报价成交 | 采购订单单价来自采购域；生产领料按实际库存估值，不因定价 12 而变为 12 |
| 采购报价 8，实际收货价 9 | 工单领料、库存和财务依库存计价规则体现实际成本，不强制使用报价 8；历史凭证不被改价回写 |
| 工单未领料、已领料、完工后分别查看 | 未领料仅展示清晰标识的预计值（若该展示能力纳入实施）；已领料有实际材料成本；完工汇总实际材料及适用工费 |
| MES 零成本移动、撤销与重提生产库存凭证 | 保留原有零成本控制或明确报错，实际成本刷新无重复累加，财务与库存账一致 |
| 销售交付与退货/取消 | 销售收入与已交付库存成本各走其来源，成本报表、凭证及毛利保持一致 |

## 6. 分阶段实施与验收预期

阶段一：补分域测试与查询入口，证明同一物料的购买型规则只进入采购域、销售型只进入定价域；旧接口签名不变。阶段二：采购页增加独立报价区块及刷新行为，保留既有供应商编辑弹窗；核对原生 Item Price 区块。阶段三：仅针对测试发现的实际越域路径补采购推荐/比价/订单保护分支。每阶段可以独立回归，不迁移、不删除历史报价。

验收场景：① 原材料有两家供应商及数量阶梯时，采购页显示各自来源和有效档位，定价页不出现购买型阶梯；② 同一物料同时存在采购报价和销售价格，两边互不污染；③ 成品销售取销售定价，外购成品采购仍走采购报价；④ 无有效报价时不取销售价格，历史采购参考价仅按确认的口径显示；⑤ 报价取消、过期、币种/UOM 不同、采购数量跨档时，比价与采购订单结果一致；⑥ 旧供应商报价、既有同步规则和手工改单仍可使用；⑦ 权限不足者看不到受限供应商报价。

预期效果：业务人员从采购页维护并追溯物料采购价格，成品销售定价保留在定价侧；数据来源、展示与实际采购/销售单据取价一致，同时最大限度保持已有接口及历史数据不变。
