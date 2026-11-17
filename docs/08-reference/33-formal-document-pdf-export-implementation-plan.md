---
title: 三类正式业务单据 PDF 导出合并实施方案
---

# 三类正式业务单据 PDF 导出合并实施方案

状态：仅方案，未修改业务代码、单据数据或站点配置。

## 1. 目标与范围

将以下三个已确认的固定版式导出需求作为一个实施批次交付：

| 单据 | DocType / 入口 | 生成文件 | 使用目的 |
|---|---|---|---|
| 客户对账单 | `Sales Order`、`Delivery Note` 列表 | A4 横向 PDF | 直接发送客户核对、盖章确认 |
| 产品组装领料单 | `Work Order` 列表及详情 | A4 横向 PDF | 车间按工单领料、签字留档 |
| 采购申请单 | `Material Request` 列表及详情 | A4 纵向 PDF | 采购申请、审批和盖章 |

三类单据都采用“用户选择已有单据 -> 服务端只读取、校验并渲染 -> 浏览器下载”的新增分支。它们共用 PDF 基础设施，但分别维护数据组装、金额/数量口径和模板，不将销售回款、生产欠料、采购审批混入同一个业务接口。

本方案是三个 PDF 的统一实施依据；原 [系统业务单据导出能力建设方案](./30-system-wide-document-export-plan.md) 和 [正式客户对账单 PDF 生成方案](./32-customer-reconciliation-pdf-plan.md) 保留作为业务背景和细节来源。

## 2. 预期效果

1. 用户在对应列表勾选单据后，可从“操作”菜单生成对应正式 PDF；工单和采购申请详情页也可生成当前单据。
2. 对账单校验同一公司、客户和币种后生成一份 PDF；工单和采购申请多选时一单一份 PDF，打包为 ZIP，不混合明细与签字区。
3. 三份文件顶部均显示公司名称“阿基视觉科技（东莞）有限公司”和右上角 AKI VISION Logo；中文、长文本、多页表头和最后一页签字区正常打印。
4. 对账单包含业务明细、含税金额、已付款/未付款及收款信息；领料单包含 BOM 用量、累计领用和欠料；采购申请单包含申请、物料、金额/待询价、理由和批准区。
5. 生成前后不修改销售订单、送货单、发票、付款、工单、库存、采购申请、审批状态或单据 `modified`。
6. 现有 Excel 导出、采购订单/送货单对账 Excel、导入流程和 ERPNext 原生打印功能保持不变。

## 3. 统一设计与边界

### 3.1 共享能力

- 新增 `formal_pdf_export.py` 作为仅供三个导出模块调用的基础工具：名称解析、读取权限校验、状态校验辅助、HTML 转 PDF、单文件下载和多文件 ZIP 响应。
- 所有业务取数保持在各自模块中。共享模块不得查询销售发票、库存流水、BOM 或采购申请业务字段。
- Logo 仅复制一次至 `client_akivision/public/images/aki_vision_logo.png`，模板通过应用静态资源引用；不在运行时依赖仓库根目录 `/home/cst/frappe_docker/df8baa79f9b81863358a5464f8673abf.png`。
- 统一使用 Frappe 的二进制下载响应和 PDF 引擎；前端只传单据名称数组或受控筛选条件，不传 HTML、SQL、字段名或模板路径。

### 3.2 不改变的接口和行为

- 保持 `download_document_export` 与 `download_reconciliation_export` 的入参和 Excel 返回格式不变。
- 不修改 ERPNext 原生 `Sales Order`、`Delivery Note`、`Work Order`、`Material Request` 控制器、库存记账、付款分配、审批流和打印格式接口。
- 只在 `hooks.py` 增量挂载新脚本；现有 `sales_order`、`delivery_note`、`work_order`、`material_request` 脚本的行为保持。

## 4. 三个单据的业务规则

### 4.1 客户对账单

- 列表入口：`Sales Order`、`Delivery Note` 的“生成客户对账单 PDF”；同时支持受控的“按筛选结果生成”。
- 预检与正式生成共用同一聚合函数，校验读取权限、状态、同公司、同客户、同币种及数量上限；混选时拒绝并提示拆分。
- 送货单入口按实际交付行生成；销售订单入口按订单行生成，并在 PDF 中标注数据来源。单价和金额使用原业务精度及税费口径。
- 已付款只依据关联销售发票和已提交付款凭证的有效分配金额在本次范围内计算。无法可靠关联时显示“以财务确认为准”，不得伪造精确分摊。
- A4 横向。多页重复抬头、标题和表头；收款账户及客户签字/盖章区只出现在最后一页。

### 4.2 产品组装领料单

- 列表和详情入口：`Work Order` 的“生成产品组装领料单 PDF”。取消工单不能生成。
- 读取工单、`required_items`、BOM/物料图纸字段，并汇总已提交生产领料 `Stock Entry` 的累计领用数量。
- 用量为 `required_qty / Work Order.qty`；工单数量为零时拒绝生成。欠料为 `max(需求数量 - 累计已领数量, 0)`，不得显示负数。
- 首期“领用数”固定表示“累计已领”，模板明确标注。以后若从具体 `Stock Entry` 生成“本次领料单”，新增分支实现，不改变本期口径。
- A4 横向。字段包括单号、项目、数量/套、日期、型号、图纸号、物料名称、用量、累计领用、欠料、备注及送料/收料签字区；欠料行黄色高亮且同步显示数量。
- 多选 ZIP 内一张工单一份 PDF；签字区仅在每份 PDF 最后一页。

### 4.3 采购申请单

- 列表和详情入口：`Material Request` 的“生成采购申请单 PDF”。仅允许 `material_request_type = Purchase` 且未取消的申请。
- 读取申请头、明细、申请人/员工、部门、项目和建议供应商。无员工映射时回退到用户全名。
- 单价和金额读取已有 `rate`、`amount`；无采购价格时显示“待询价”，不以 `0` 冒充价格。合计仅汇总有效金额行，并说明最终金额以采购订单为准。
- A4 纵向。字段包括申请单号、申请人、申请日期、部门、项目、物料、数量、单位、单价、总价、供应商、备注、采购理由、批准人/日期和版本号。
- 多选 ZIP 内一张申请一份 PDF；采购理由和批准区只出现在每份 PDF 最后一页。

## 5. 调用链路

```text
销售订单/送货单、生产工单、采购申请的列表勾选或详情页
  -> 独立前端脚本收集名称、调用对应预检或下载接口
  -> 对账单预检展示公司、客户、币种、期间、数量、金额摘要
  -> 对应服务端模块执行白名单、读取权限、状态与业务一致性校验
  -> 各模块独立读取并组装销售回款 / BOM领料 / 采购申请数据
  -> 共用 PDF 工具渲染指定 Jinja 模板及 CSS
  -> Frappe PDF 引擎生成 PDF
  -> 单张下载；领料单和采购申请多选时 ZIP 下载
```

全程不进入保存、提交、取消、库存更新、应收应付、会计凭证或审批写入链路。

## 6. 修改代码与文件

| 文件 | 变更类型 | 内容 |
|---|---|---|
| `client_akivision/utils/formal_pdf_export.py` | 新增 | 三类 PDF 共用的安全名称解析、下载/ZIP 响应、渲染和 PDF 生成辅助。 |
| `client_akivision/utils/customer_reconciliation_pdf.py` | 新增 | 对账预检、权限/同客户校验、订单/送货/发票/付款聚合与下载接口。 |
| `client_akivision/utils/work_order_material_pdf.py` | 新增 | 工单、BOM、累计领料、欠料计算及单张/批量下载。 |
| `client_akivision/utils/material_request_pdf.py` | 新增 | 采购申请权限、类型校验、申请头/明细/人员数据组装及单张/批量下载。 |
| `client_akivision/templates/customer_reconciliation_pdf.html` | 新增 | 客户对账单固定模板。 |
| `client_akivision/templates/work_order_material_issue_pdf.html` | 新增 | 产品组装领料单固定模板。 |
| `client_akivision/templates/material_request_purchase_pdf.html` | 新增 | 采购申请单固定模板。 |
| `client_akivision/public/css/customer_reconciliation_pdf.css` | 新增 | 对账单 A4 横向、合计和签章区样式。 |
| `client_akivision/public/css/work_order_material_issue_pdf.css` | 新增 | 领料单 A4 横向、分页、欠料高亮和签字区样式。 |
| `client_akivision/public/css/material_request_purchase_pdf.css` | 新增 | 采购申请 A4 纵向、分页和审批区样式。 |
| `client_akivision/public/images/aki_vision_logo.png` | 新增 | 由已确认的公司 Logo 源图复制出的应用静态资源。 |
| `client_akivision/public/js/customer_reconciliation_export.js` | 新增 | 销售订单/送货单列表入口、预检确认、下载。 |
| `client_akivision/public/js/work_order_material_pdf.js` | 新增 | 工单列表/详情入口及下载。 |
| `client_akivision/public/js/material_request_pdf.js` | 新增 | 采购申请列表/详情入口及下载。 |
| `client_akivision/hooks.py` | 修改 | 仅增加上述 JS 的挂载，不删除或覆盖旧 Hook。 |
| `client_akivision/utils/test_formal_pdf_export.py` | 新增 | 共用下载、ZIP、权限、文件名和异常响应测试。 |
| `client_akivision/utils/test_customer_reconciliation_pdf.py` | 新增 | 对账同客户/币种、金额、付款、退货、分页测试。 |
| `client_akivision/utils/test_work_order_material_pdf.py` | 新增 | BOM 用量、累计领用、欠料、多页与 ZIP 测试。 |
| `client_akivision/utils/test_material_request_pdf.py` | 新增 | 采购类型、待询价、合计、多页与 ZIP 测试。 |

## 7. 受影响模块

| 模块 | 影响 | 是否写入 |
|---|---|---|
| 销售订单、送货单、客户、联系人 | 新增对账 PDF 读取与列表入口 | 否 |
| 销售发票、付款凭证、公司、银行账户 | 仅用于对账金额和抬头账户读取 | 否 |
| 生产工单、BOM、物料、生产领料库存单 | 新增领料 PDF 读取与入口 | 否 |
| 采购申请、员工、部门、项目、供应商 | 新增采购申请 PDF 读取与入口 | 否 |
| 打印/PDF、静态资源、权限 | 新增模板、Logo、下载和权限校验 | 否 |
| 现有 Excel 导出、导入、库存、财务、审批 | 不改变既有行为 | 否 |

## 8. 实施顺序与验收

1. 新增共用 PDF/ZIP 工具、Logo 静态资源和单元测试基础，验证不影响已有 Excel 下载。
2. 实现采购申请单和生产领料单，它们只依赖单据/BOM/库存读取，先验证单张、多选、无权限、取消、长中文和多页。
3. 实现客户对账预检与 PDF，先以送货单作为实际交付入口，再接入销售订单；由财务使用预付款、部分付款、合并开票、退货样本确认付款口径。
4. 在 `aki_test.localhost` 执行构建、清缓存，并用 Playwright 验证三个列表入口、确认弹窗和下载行为；同时人工核对 PDF 页眉、Logo、分页、中文、金额和签字区。
5. 验收通过后再考虑保存 PDF 历史、编号、审批、电子盖章或从具体 `Stock Entry` 生成“本次领料单”，这些均不属于本期。

验收底线：每份 PDF 的数据与来源单据一致；越权、取消或不符合类型的单据无法生成；生成操作没有任何业务写入；已有 Excel 导出仍可用。
