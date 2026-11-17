---
title: 采购订单关联与质检前置正式入库优化方案
---

# 方案目标

当前业务要求是：采购到货必须来源于采购订单，质检合格后才允许进行正式入库。方案只做小增量调整，优先复用 ERPNext 标准 `Purchase Order -> Purchase Receipt -> Quality Inspection` 能力，不修改 ERPNext 老接口、不重写库存过账逻辑。

本方案暂不实施代码修改，仅作为后续开发、测试和验收依据。

## 目标流程

```text
已提交采购订单
  -> 从采购订单创建采购收货/待检单
  -> 关联采购订单行与收货行
  -> 创建并提交质量检验单
  -> 质检合格
  -> 提交正式采购收货单
  -> 库存正式增加并进入可用库存
```

不合格分支：

```text
质检不合格
  -> 禁止正式入库
  -> 退货、返工或让步接收
  -> 通过明确的业务单据处理，不直接改库存余额
```

## 业务规则

| 规则 | 说明 |
| --- | --- |
| 采购订单前置 | 正式采购收货必须关联已提交且未关闭的采购订单；不允许手工录入无来源的采购收货。 |
| 采购订单行关联 | 每条收货明细保留 `purchase_order`、`purchase_order_item`，物料、单位、可收数量优先由订单带出。 |
| 分批收货 | 同一采购订单允许多次收货，仅按剩余数量生成收货行；沿用标准超收和并发校验。 |
| 质检前置 | 物料启用 `inspection_required_before_purchase` 时，必须存在关联质检单，且质检单已提交。 |
| 合格才入库 | 质检状态为 `Accepted`/合格时才允许正式提交采购收货；`Rejected`/不合格禁止提交。 |
| 退货隔离 | 退货、返工、让步接收使用对应标准分支，不把不合格数量直接记入可用库存。 |
| 非采购入库 | 生产入库、退料、盘点等非采购业务不强制套用采购订单规则，但不能伪装成采购收货。 |

## ERPNext 配置前提

1. `Stock Settings.allow_to_make_quality_inspection_after_purchase_or_delivery` 关闭，避免采购收货提交后再补质检。
2. 需要质检的物料启用 `Item.inspection_required_before_purchase`。
3. `Stock Settings.action_if_quality_inspection_is_not_submitted` 设置为 `Stop`。
4. `Stock Settings.action_if_quality_inspection_is_rejected` 设置为 `Stop`。
5. 采购人员通过采购订单的标准“创建采购收货”入口操作，不从空白采购收货单开始填来源。

## 拟修改文件与代码职责

以下是实施阶段的拟修改范围，当前不修改。

| 文件/模块 | 拟改内容 | 策略 |
| --- | --- | --- |
| `client_akivision/hooks.py` | 增加 `Purchase Receipt` 的前端脚本和后端校验事件挂载。 | 新增挂载，不替换原事件。 |
| `client_akivision/public/js/purchase_receipt_quality_gate.js`（新增） | 新建单据时引导从采购订单创建；展示来源订单；提交前提示质检状态；隐藏或禁用无来源的正式提交入口。 | 新增前端分支，保留标准表单。 |
| `client_akivision/utils/purchase_receipt_quality_gate.py`（新增） | 在服务端校验采购订单来源、订单状态、订单行、剩余数量、质检关联和质检结果。 | 只增加业务前置校验，不改库存过账。 |
| `client_akivision/utils/custom_field_schema.py` | 如现有站点缺少展示字段，注册采购订单/采购订单行/质检状态的只读字段。 | 只新增字段，不改旧字段名。 |
| `client_akivision/utils/test_purchase_receipt_quality_gate.py`（新增） | 覆盖订单来源、分批收货、缺质检、未提交质检、不合格、合格提交和非采购分支。 | 新增回归测试。 |
| `docs/playwright_purchase_receipt_quality_gate.mjs`（新增） | 验证采购订单入口、质检状态展示、提交拦截和移动端布局。 | 新增浏览器回归脚本。 |
| ERPNext `stock_controller.py`、`buying_controller.py` | 原则上不修改。仅作为标准校验和调用链依赖。 | 保持核心接口和库存逻辑不变。 |

如现有自定义字段已经存在，应复用字段，不重复创建；如标准字段已满足展示需求，不增加自定义字段。

## 调用链路

```text
Purchase Order（已提交）
  -> ERPNext make_purchase_receipt
  -> Purchase Receipt 草稿
       - purchase_order
       - Purchase Receipt Item.purchase_order
       - Purchase Receipt Item.purchase_order_item
  -> 前端显示来源订单及剩余可收数量
  -> 创建 Quality Inspection
       - reference_type = Purchase Receipt
       - reference_name = Purchase Receipt
       - item_code / child_row_reference 对应收货行
  -> Quality Inspection 提交
  -> Purchase Receipt 保存/提交前新增 gate 校验
       - 订单存在、已提交、未关闭
       - 数量未超订单剩余数量
       - 必检物料存在已提交质检单
       - 质检结果不是 Rejected
  -> ERPNext 原生 Purchase Receipt submit
  -> Stock Ledger / GL 原生过账
```

服务端校验应挂在采购收货保存/提交前的扩展事件上；最终库存写入仍由 ERPNext 原生 `Purchase Receipt` 提交流程完成。

## 受影响模块

| 模块 | 影响 |
| --- | --- |
| 采购 | 采购收货必须有采购订单来源；订单状态和剩余数量更严格。 |
| 质量 | 必检物料必须先完成质量检验；质检结果与收货行绑定。 |
| 库存 | 正式库存只在合格采购收货提交后增加；库存过账代码不变。 |
| 财务 | 采购收货形成的库存价值和应付关联沿用标准逻辑，提交时点后移。 |
| 退货/返工 | 不合格数量转入对应业务分支，不直接冲改库存。 |
| 报表/追溯 | 可从采购收货追溯采购订单和质检单；历史单据保持可读。 |
| 权限 | 采购、仓库、质检角色按现有权限操作；新增校验不扩大权限。 |
| 生产入库 | 不受采购订单规则影响，仍走生产工单/Stock Entry 原生链路。 |

## 兼容与小增量原则

- 不修改 ERPNext 标准 `make_purchase_receipt`、`StockController.validate_inspection` 和库存过账函数。
- 不改变既有采购订单、采购收货、质检单的 DocType 名称和标准字段含义。
- 新逻辑只针对“采购收货且非退货”的分支生效。
- 历史已提交单据不回溯拦截；取消、退货仍走原标准逻辑。
- 前端拦截只改善入口和提示，服务端校验作为最终控制点。
- 允许保留标准接口供 API、导入和集成使用，但所有入口都必须经过同一服务端 gate。

## 预期效果

1. 没有关联采购订单的采购收货不能作为正式采购入库提交。
2. 收货数量、物料和价格来源清晰，可追溯到采购订单行。
3. 必检物料在质检未完成或不合格时不能进入正式可用库存。
4. 质检合格后才触发标准库存、库存估值和财务过账。
5. 分批收货、超收校验、采购订单状态更新继续使用 ERPNext 标准能力。
6. 采购订单、采购收货、质检单、库存流水和财务凭证形成闭环追溯。
7. 非采购入库、历史单据和原有接口不因本次调整而改变行为。

## 验收场景

| 场景 | 预期结果 |
| --- | --- |
| 从已提交采购订单创建收货，质检合格后提交 | 成功提交，产生正式库存和标准库存流水。 |
| 空白创建采购收货，不关联采购订单 | 服务端拒绝正式提交，并提示必须关联采购订单。 |
| 采购订单已关闭或已取消 | 拒绝新增正式收货。 |
| 收货数量超过订单剩余数量 | 沿用标准超收校验并拒绝。 |
| 必检物料未创建质检单 | 拒绝提交。 |
| 质检单已保存但未提交 | 按配置 `Stop` 拒绝提交。 |
| 质检结果为不合格 | 拒绝正式入库，提示走退货/返工/让步接收。 |
| 非必检物料且订单来源有效 | 可按标准流程提交。 |
| 生产入库或退料 | 不触发采购订单校验，保持原流程。 |
| 同一订单分两次收货 | 每次只允许剩余数量，订单累计收货状态正确。 |

## 实施顺序

1. 先核对站点配置、物料质检标记和现有自定义字段。
2. 先实现服务端 gate 和单元测试。
3. 再增加前端入口提示、来源展示和质检状态提示。
4. 使用真实采购订单进行分批收货、合格、不合格和退货回归。
5. 最后执行迁移、权限核验和浏览器回归，不修改历史库存数据。

