# 销售结算模式前端配置化方案

## 1. 背景

当前销售订单的“销售结算模式”虽然是 Select 字段，但选项写死在 `china_finance/setup/install.py` 和服务端常量中。财务人员无法通过前端新增、停用或维护模式；如果直接改 JSON 或 Python，还需要重新部署应用，且容易造成订单历史值与业务逻辑不一致。

目标是将“模式清单维护”从代码配置改为前端可维护配置，同时保留现有订单字段和旧接口，不让新增模式绕过财务规则。

## 2. 推荐方案

新增一个独立的配置 DocType：`China Sales Settlement Mode`（中国销售结算模式）。财务人员通过前端列表和表单维护模式；销售订单仍继续使用现有字段 `custom_china_settlement_mode` 保存最终快照。

### 2.1 前端维护字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `mode_code` | Data | 系统唯一编码，创建后不可修改；用于接口和历史数据稳定关联 |
| `mode_name` | Data | 销售订单下拉框显示名称，必填 |
| `description` | Small Text | 给财务和销售说明确认时点、应收和开票规则 |
| `enabled` | Check | 是否允许新订单选择；停用不影响历史订单 |
| `sort_order` | Int | 下拉框显示顺序 |
| `confirmation_method` | Select | 外部客户确认 / 内部复核 |
| `ar_recognition_stage` | Select | 销售发票 / 销售结算 / 不确认应收 |
| `auto_invoice` | Check | 是否允许沿用自动开票分支，默认关闭 |
| `requires_reason` | Check | 修改或覆盖模式时是否必须填写原因 |
| `is_system_mode` | Check | 标记现有系统模式，不允许删除，只允许停用 |

首期创建两条系统数据：

| 编码 | 名称 | 应收确认阶段 |
|---|---|---|
| `direct_receivable` | 直接确认应收 | 销售发票 |
| `reconcile_before_receivable` | 对账结算后确认应收 | 销售结算 |

`custom_china_settlement_mode` 继续保存中文名称，以兼容已有订单、报表和旧接口；`mode_code` 只作为配置记录的稳定标识。

### 2.2 用户操作流程

```text
中国财务 -> 销售结算模式 -> 新建
  -> 填写模式名称、确认方式、应收确认阶段和说明
  -> 保存并启用
  -> 系统校验编码/名称唯一性及业务组合
  -> 草稿销售订单下拉框读取启用模式
  -> 提交后订单保留当时的模式名称快照
```

停用模式后：

- 新建订单不再出现在下拉框；
- 已有草稿若已选择该模式，允许保存但提交时提示模式已停用；
- 已提交订单、历史报表和结算单不回写、不改名；
- 不允许删除已被订单、出库、发票或结算引用的模式。

## 3. JSON 导入/导出格式

前端配置页面可以提供“导出 JSON”和“导入 JSON”，但 JSON 只是配置交换格式，最终仍写入 `China Sales Settlement Mode` 记录，不直接让浏览器修改字段元数据。

```json
[
  {
    "mode_code": "direct_receivable",
    "mode_name": "直接确认应收",
    "description": "销售发票提交后确认应收和销项税",
    "enabled": true,
    "sort_order": 10,
    "confirmation_method": "外部客户确认",
    "ar_recognition_stage": "销售发票",
    "auto_invoice": false,
    "requires_reason": false
  },
  {
    "mode_code": "reconcile_before_receivable",
    "mode_name": "对账结算后确认应收",
    "description": "完成客户确认和销售结算后确认应收",
    "enabled": true,
    "sort_order": 20,
    "confirmation_method": "外部客户确认",
    "ar_recognition_stage": "销售结算",
    "auto_invoice": false,
    "requires_reason": true
  }
]
```

导入规则：

1. 必须是 JSON 数组，每行必须包含 `mode_code`、`mode_name`、`enabled` 和 `sort_order`；
2. `mode_code` 只允许小写字母、数字和下划线，且全局唯一；
3. `mode_name` 不得重复；
4. 系统模式编码不能被改名、删除或覆盖核心业务属性；
5. 新模式先以“未启用”导入，财务确认后再启用；
6. 导入采用预览、校验、确认三步，不直接覆盖现有配置；
7. 导入记录操作人、时间、变更前后 JSON 和失败原因。

## 4. 调用链路

```text
财务前端新增/编辑/导入模式
  -> 配置 DocType 校验
  -> 保存 China Sales Settlement Mode
  -> 清理销售订单字段缓存

销售订单加载
  -> 前端读取 enabled=1 的模式清单
  -> 草稿订单显示可用模式
  -> 服务端 before_validate 再次校验模式仍存在且启用
  -> 保存中文模式名称作为订单快照

销售出库/销售发票/销售结算
  -> 读取订单已保存的 custom_china_settlement_mode
  -> 通过兼容解析器映射到 mode_code 和业务阶段
  -> 沿用现有分支执行应收、开票和凭证链路
```

服务端不得仅相信前端下拉值；订单保存、提交、出库和结算入口都必须通过同一个模式解析器校验。

## 5. 建议代码与文件

| 文件 | 类型 | 计划改动 |
|---|---|---|
| `china_finance/china_finance/doctype/china_sales_settlement_mode/` | 新增 | 配置 DocType、权限和表单字段 |
| `china_finance/china_finance/services/sales_settlement_mode_config.py` | 新增 | 模式查询、唯一性校验、启用状态校验、旧中文名称兼容映射 |
| `china_finance/china_finance/api/sales_settlement_mode_config.py` | 新增 | JSON 预览、导入、导出和确认接口；导入接口要求财务管理权限 |
| `china_finance/china_finance/public/js/sales_settlement_mode_config.js` | 新增 | JSON 导入预览、字段提示和启用确认交互 |
| `china_finance/china_finance/services/sales_settlement.py` | 增量修改 | 使用兼容解析器；保留 `MODE_DIRECT`、`MODE_SETTLEMENT` 和旧中文值 |
| `china_finance/china_finance/public/js/sales_order_settlement.js` | 增量修改 | 草稿订单下拉框读取启用模式，提交后继续只读 |
| `china_finance/china_finance/setup/install.py` | 增量修改 | 创建 DocType 和两条系统初始数据；不改历史订单 |
| `china_finance/china_finance/tests/test_sales_settlement_mode_config.py` | 新增 | 覆盖 JSON 校验、停用模式、历史中文值、引用保护和权限 |
| `docs/08-reference/37-sales-settlement-mode-frontend-config-plan.md` | 已新增 | 本方案沉淀 |

## 6. 兼容策略

- 不修改 `Sales Order.custom_china_settlement_mode` 字段类型和字段名；
- 不要求 Excel、CRM、API 调用方新增 `mode_code`；
- 旧中文值继续可被解析，历史订单无需迁移；
- 新模式如果没有明确的应收、开票和凭证行为，只能保存为“未启用”，不能进入销售订单下拉框；
- 停用只影响新订单，不影响已提交订单的结算、发票和凭证；
- 不允许在配置页面直接编辑系统字段元数据，避免破坏 ERPNext 表单结构。

## 7. 受影响模块

| 模块 | 影响 |
|---|---|
| 中国财务设置 | 增加“销售结算模式”配置入口或快捷入口 |
| 销售订单 | 下拉选项由启用的配置记录生成，订单仍保存原字段 |
| 销售出库 | 继续按订单模式校验，不直接读取未启用的新配置 |
| 销售发票/自动开票 | 仅对已实现业务阶段的模式执行；未实现模式禁止启用 |
| 销售结算 | 使用模式解析器判断是否允许确认应收 |
| 会计凭证 | 不改生成接口，仅使用订单最终模式和已有业务来源 |
| Excel/CRM/API | 无破坏性变更，继续接受旧中文模式或空值 |
| 权限与审计 | 配置新增、导入、启停和删除受财务管理权限控制并记录日志 |

## 8. 预期效果

1. 财务人员可在前端新增和停用销售结算模式，不需要改代码或重新部署。
2. 可通过 JSON 导入/导出批量维护配置，但所有变更经过校验和确认。
3. 下拉框只展示已启用且业务规则完整的模式，降低误选风险。
4. 历史订单和老接口继续使用原字段，不需要一次性数据迁移。
5. 新增模式具备明确的确认方式、应收阶段、自动开票和原因要求，财务可读性高。
6. 停用、导入、覆盖和系统模式保护均有审计记录。

## 9. 验收标准

1. 财务用户可从前端新建模式，普通销售用户无权维护模式配置。
2. 新建模式默认未启用；启用前必须通过业务字段校验。
3. 启用后，草稿销售订单下拉框出现该模式；停用后不再出现在新订单中。
4. 已有订单的模式名称、出库、发票、结算和凭证逻辑不受影响。
5. JSON 导入显示新增、修改、停用和冲突预览，确认后才写入。
6. 删除被引用模式会被拒绝；停用被引用模式不会修改历史数据。
7. 旧中文值“直接确认应收”“对账结算后确认应收”仍能正常识别。
8. 没有实现应收/开票链路的新模式无法启用，并给出明确原因。

## 10. 实施顺序

1. 新增配置 DocType、权限和系统初始数据。
2. 实现兼容解析器，先替换服务端读取分支并补测试。
3. 改造销售订单下拉框为读取启用配置，验证旧订单和接口。
4. 增加 JSON 导入/导出及审计日志。
5. 最后开放财务前端入口，并在测试站点验证出库、开票、结算和凭证链路。

本方案只描述配置化改造，不在本阶段直接新增新的会计业务模式。任何新模式必须先定义完整的应收确认、开票、税务和凭证口径，再允许启用。
