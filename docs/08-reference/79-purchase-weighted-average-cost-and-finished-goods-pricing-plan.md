---
title: 采购加权平均成本与成品销售定价分流优化方案
status: 一期已实现（预计材料成本只读分支）；财务口径待确认
---

# 采购加权平均成本与成品销售定价分流优化方案

## 一、修正后的业务目标

本方案取代 `78-item-purchase-price-vs-finished-goods-pricing-optimization-plan.md` 中“在采购页增加供应商阶梯展示”的实施方向。采购页已经支持多供应商报价及规则，本次**不新增采购报价形式、不搬迁页签、不重新实现供应商定价**。需要解决的是成本计算的取价来源：采购物料用于预算/生产前估算的参考成本，来自该物料**历史实际采购的数量加权平均单价**；自产成品对外**销售价格**来自定价；外购成品既有采购成本，也有独立的销售定价。同一成品可同时自产和外购，不按 Item Group 或“是否成品”二选一决定价格来源，而按交易方向、成本阶段决定。

“采购平均单价”不得与三个概念混淆：供应商当前报价用于选商和采购订单；采购历史均价用于预计成本；库存估值、生产领料、完工、销售出库及财务入账按实际库存凭证和现有会计规则执行。销售定价不作为任何一种成本。**不把历史采购均价写入 Item.valuation_rate、已过账的库存账、总账或历史工单。**

## 二、预期效果和调用链（文字图）

```text
采购页已有多供应商报价 ─→ 采购比价 ─→ 采购订单采购价
                                         │
                                         ▼
                         已提交的实际采购收货及退货记录
                                         │ 按公司/物料/库存单位/期间
                                         ▼
                        历史采购数量加权平均单价
                                         │
                              BOM/工单【预计】材料成本

采购实际入库 ─→ 库存计价 ─→ 工单实际领料 ─→ 完工成品实际成本
                                                     │
                           财务库存/销售成本 ← 销售出库┘

成品销售定价 ─→ 销售报价/订单售价 ─→ 应收及收入
外购成品报价 ─→ 采购订单 ─→ 外购入库成本 ─→ 成品库存/财务成本
```

| 业务场景 | 预计价格来源 | 实际过账成本来源 | 预期效果 |
| --- | --- | --- | --- |
| 原料、辅料、外购零件 | 历史采购加权平均单价 | 对应库存发出估值 | 计划时能看参考成本，工单实际成本不被报价/售价干扰 |
| 自产成品销售 | 对外售价取销售定价；预计生产成本由 BOM 材料均价及工费测算 | 完工入库、交付出库成本 | 售价、预计毛利、实际毛利口径清楚 |
| 外购成品销售 | 采购成本参考取历史采购均价，采购成交价仍取供应商报价；对外售价仍取销售定价 | 外购入库与交付出库成本 | 同一成品两侧价格共存，不相互覆盖 |
| 同物料既自产又外购 | 按该次业务来源分别展示预计/实际成本；外购估算可取采购均价 | 按实际凭证与库存计价 | 不凭物料分类覆盖工单成本或采购价 |
| 尚无采购记录 | 显示“无历史均价”及数据来源状态 | 不自动制造库存成本 | 不静默取销售价，也不将当前报价伪装为历史成交价 |

## 三、平均采购单价的建议口径（实施前待确认）

建议一期只对**库存物料的已提交采购收货（Purchase Receipt）及其退货**计算：在指定公司和统计区间内，按库存单位折算，`净采购金额（公司本位币）÷ 净入库数量（库存单位）`；其中净额扣减采购退货，排除草稿/已取消、零数量、无效或无法换算的行。供应商报价、采购订单（未收货）、销售 Item Price、生产领料、内部仓库调拨均不计入样本。采购发票与收货发票并存时不可双计；是否纳入后续发票价差、运杂费及非库存采购，须与财务确认，再决定采用收货金额还是另一统一的已确认成本数据源。历史补录和跨公司汇总不默认混算。

举例：同公司同库存单位实际收货 10 件×8 元、90 件×10 元，均价为 9.8 元，不是两个价格简单平均 9 元。退回 10 件、退款 100 元后，若无其他差异，净额 880 元/净量 90 件≈9.7778 元。金额与数量应以同一交易口径处理，退货/费用差额不得只调整分子。

待业务确认的参数：统计期间（建议可配置近 12 个月、默认按过账日期）；仓库维度（一期建议同公司聚合，库存实际估值仍按既有仓库规则）；汇率和含税口径（建议本位币、不含可抵扣税）；无历史数据时是否允许**另行标识的报价估算**，默认不回退；外协、非库存、赠品、零金额、负净量的处理；定价页销售价格是否适用于非成品销售。参数未确认前不得让均价直接参与账务过账。

## 四、现有代码与影响分析

| 已定位文件 | 代码现状 | 本次职责 |
| --- | --- | --- |
| `development/frappe-bench/apps/custom_filters/custom_filters/item_supplier_pricing.py`、`custom_filters/quote_pricing.py` | 维护多供应商规则和购买型 Item Price/Pricing Rule | 采购报价链路保持；**不改变**均价样本为当前报价 |
| `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/report/purchase_recommendation/purchase_recommendation.py`、`client_akivision/utils/purchase_comparison.py` | 采购推荐/比价读取有效报价、规则、历史采购参考 | 保持采购实际下单按供应商及数量取价；不把均价伪装为供应商报价 |
| `development/frappe-bench/apps/erpnext/erpnext/manufacturing/doctype/bom/bom.py` | `get_bom_item_rate` 的现有来源是 Valuation Rate、Last Purchase Rate 或购买 Price List；默认 Valuation Rate；目前**没有“历史采购加权均价”选项** | 不修改原生控制器；若要显示该均价，先新增独立预计成本分支，不悄悄重释标准 BOM 选项 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/sales_order_production_cost.py`、`client_akivision/hooks.py` | 已提交的生产 Stock Entry 计算实际材料/完工成本，交付成本取 Stock Ledger Entry | 实际成本刷新链路保持，不用平均采购价覆盖实际材料或生产成本 |
| `development/frappe-bench/apps/mes_integration/mes_integration/mes_integration/stock_entry.py` | MES 库存单据走库存金额计算，另有无成本允许零估值逻辑 | 做零成本边界回归，不能将平均采购价无条件写为估值率 |
| `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/report/sales_order_production_cost_and_margin/sales_order_production_cost_and_margin.py` | 消费销售订单已记录的实际成本和毛利 | 有预计毛利需要时另列，实际毛利原口径不动 |
| ERPNext Stock Ledger、Purchase Receipt、Delivery Note、GL 及财务扩展 | 库存价值与总账凭证的实际成本通道 | 只核对、不直接修改原生过账代码；对账核验历史行为 |

## 五、小增量实施清单：拟新增/拟修改文件

| 文件（拟定，实施前复核实际路径） | 代码改动与调用方式 | 预期效果 |
| --- | --- | --- |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/purchase_average_cost.py`（新增） | 新增纯计算/查询服务 `get_purchase_weighted_average_cost(item_code, company, from_date, to_date, ...)`；按已确认采购记录、退货、公司币种及库存单位聚合；返回均价、净量、净额、期间、样本数和来源状态，不直接写 Item/BOM/GL | 各预计成本消费者共用一套可追溯算法，避免散落 SQL |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/estimated_material_cost.py`（按实际入口新增） | 新增可选的 BOM/工单预计材料成本计算分支：材料需求数量 × 采购历史均价，并递归处理半成品、单位换算；预计人工/制造费沿用已有配置；显式记录缺价物料，不以售价补齐 | 工单开工前有独立的“预计成本”；不污染 ERPNext 标准 BOM 的估值率/最后采购价选项 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/sales_order_production_cost.py` | 原实际成本计算及公开接口不变；如需在订单显示预计/实际差异，仅追加读取预计成本的独立分支/字段，不改 `custom_material_cost`、`custom_delivered_cost` 的语义 | 实际材料/交付成本和财务链路维持原样，可单独观察预算偏差 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/custom_field_schema.py` 或既有 `ensure_schema` 所在模块 | 仅在需要持久化预计值时幂等追加只读字段：预计均价/预计材料成本、公司、计算时点、统计区间、来源状态；若仅即时展示，则不新增字段 | 历史订单字段不迁移；预计/实际字段明确分离 |
| BOM/Work Order 现有自定义表单 JS（先定位项目使用的脚本，优先 `client_akivision/public/js/` 新增并在 hooks 注册） | 增加“查看采购均价成本估算”的独立动作/展示区，调用新增白名单读取接口；保留原生 BOM `update_cost`、工单及采购/定价页原交互 | 用户能查均价、样本量、期间和缺价提示；旧表单行为不变 |
| `development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/report/sales_order_production_cost_and_margin/sales_order_production_cost_and_margin.py`（可选） | 如果需要预计/实际对比才追加单独列，现有实际成本列原样输出 | 报表不会把采购均价估算当财务实际成本 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/test_purchase_average_cost.py` 及预计成本集成测试（新增） | 测试数量加权、退货、币种/UOM、跨公司、空样本、自/外购成品、实际成本不受影响 | 取价边界可回归 |

以上文件为**拟实施范围，不是已改文件**；财务过账、BOM/Work Order 原生文件、采购报价代码默认只做回归，发现具体越域缺陷才另列最小修改文件并补测试。新增白名单接口必须校验物料读取权限及采购成本相关角色权限，避免通过预计成本泄露采购底价。

## 六、分阶段实施与关联回归

1. 先确认平均口径及期间；独立服务计算并单测；查询结果不写账。核对采购收货退货、发票差异、不含税本位币字段后再固化 SQL，避免用供应商报价代替实际成交。
2. 只在已有 BOM/工单**预计成本展示**处新增分支，已有标准 BOM 更新成本、工单领料和实际成本不变。若需改变标准 BOM 的 `rm_cost_as_per` 选项，必须作为后续单独需求评估，而非此次隐式替换。
3. 核对自产/外购成品的采购订单、生产领料、完工、出库及财务总账，补齐可追溯的预计/实际差异；改采购均价或成品售价均不自动修改已提交库存/财务凭证。
4. 复核现有采购比价、多供应商规则和销售定价均可正常取价；财务与库存实际成本一致，并执行权限检查。

验收样例：原料收货 10×8 与 90×10，预计材料均价 9.8；销售定价改为 20 不改变该均价及工单实际领料；成品外购时采购订单取有效供应商报价、估算参考历史均价、销售订单取销售定价；同一成品自产工单按实际领料归集、外购批次按实际入库估值，销售出库及总账均取库存实际成本；无历史成交显示“缺价”且不悄悄取销售定价；采购退货/取消收货后均价可重新计算但既有已入账凭证不被均价服务反写。

## 七、已存在但不属于本方案的工作区改动

前次实施在 `custom_filters/custom_filters/item_details.py`、`custom_filters/public/js/item.js`、`custom_filters/patches.txt` 及 `patches/v0_0_1/add_item_purchase_pricing_display.py` 留有“采购页增加阶梯展示/分域”的**未提交代码**。这与本方案目标不一致；本次只记载，不修改、清理或重置它们。后续实施前应先与用户确认如何处置这批改动，以免把不相关采购页面改造一并上线。

## 八、一期实现记录（2026-09-24）

已增加 `client_akivision/utils/purchase_average_cost.py`（已提交收货/退货、本位币、库存单位、权限限定的历史数量加权均价）、`client_akivision/utils/estimated_material_cost.py`（BOM 递归展开与工单计划材料的只读估算）、`client_akivision/public/js/estimated_material_cost.js`（BOM/Work Order 查看入口），并在 `client_akivision/hooks.py` 追加脚本注册；对应两个 `test_*.py` 覆盖计算、无历史记录与子 BOM。无新 DocType 或字段，不修改原生 BOM 标准成本、实际库存计价、供应商报价、销售定价或财务凭证。

测试：容器内 Python/JS 语法通过，4 项定向单元测试通过，`bench build --app client_akivision` 通过。在 `aki_test.localhost` 上只读调用真实采购收货生成历史均价，并对真实生产工单及关联 BOM 执行预计材料成本预览；未通过页面浏览器自动化验证按钮。待财务确认发票价差、费用分摊、非库存采购和跨期间退货口径后，才能扩展为包含这些情形的预算规则；**不得**直接将目前的均价写入库存/总账。部署其他站点仍需构建资源、清理缓存并按权限实测。

### 物料档案采购/定价页补充修复

在 `client_akivision/utils/item_purchase_average.py` 添加幂等 Item 采购页 HTML 字段及独立销售价格只读 API，`client_akivision/public/js/item_purchase_average.js` 在采购页显示公司/期间可选的加权平均成本，在定价页仅展示销售型 Item Price；`hooks.py` 注册字段同步及 Item 脚本。原生 ERPNext `get_item_prices` 接口和供应商报价规则保持不变。历史均价只读，和最近采购价、供应商报价、实际成本同时存在但不相互覆盖。

测试站点执行字段同步、清缓存及前端构建后，Playwright 只读验证 `1007209102-v0` 采购页可见“无有效历史采购记录”，`test item1` 显示 CNY 11.53/Nos 的采购加权均价和 CNY 100.00/Nos 的销售价，`test item3` 采购均价为 CNY 29.14/Nos，定价页原先出现的购买型 CNY 30.00/Nos 已不显示；三个页面均无 JS 错误及失败 API 请求。另加销售价格筛选单测，总共 5 项定向测试通过。无效期间、不同权限角色及生产环境仍需单独验收。
