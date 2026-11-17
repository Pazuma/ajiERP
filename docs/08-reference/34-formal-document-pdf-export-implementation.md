---
title: 三类正式业务单据 PDF 导出实施沉淀
---

# 三类正式业务单据 PDF 导出实施沉淀

状态：已完成代码实现；尚未完成真实业务样本和 Playwright 浏览器验收。

## 1. 实施范围

本次按 [三类正式业务单据 PDF 导出合并实施方案](./33-formal-document-pdf-export-implementation-plan.md) 增加了三个只读 PDF 分支：

- 销售订单、送货单：客户对账单 PDF（送货单按实际交付行；销售订单按订单行）。
- 生产工单：产品组装领料单 PDF（显示单套用量、累计领用和欠料，欠料行黄色高亮）。
- 采购申请：采购申请单 PDF（仅 `Purchase` 类型，未维护单价显示“待询价”）。

生成单张直接下载 PDF，多选的工单和采购申请按“一单一 PDF”打包 ZIP。所有接口只读，不保存或提交任何业务单据。

## 2. 已修改代码和文件

### 后端

- `client_akivision/utils/formal_pdf_export.py`：统一名称解析、读取权限、Logo Data URI、A4 PDF 渲染、单文件/ZIP 下载。
- `client_akivision/utils/customer_reconciliation_pdf.py`：对账单预检和下载；校验同公司、客户、币种和已提交状态。
- `client_akivision/utils/work_order_material_pdf.py`：工单和 BOM 明细、累计领用、欠料计算及下载。
- `client_akivision/utils/material_request_pdf.py`：采购类型/状态校验、申请人部门映射、待询价处理及下载。

### 模板和资源

- `client_akivision/templates/customer_reconciliation_pdf.html`
- `client_akivision/templates/work_order_material_issue_pdf.html`
- `client_akivision/templates/material_request_purchase_pdf.html`
- `client_akivision/public/images/aki_vision_logo.png`：由方案确认的 Logo 源图复制，保持 RGBA 和原比例。

模板当前使用内嵌打印 CSS，避免新增静态 CSS 依赖；后续版式稳定后可拆为独立 CSS 文件，不改变接口。

### 前端入口

- `client_akivision/public/js/document_export_list.js`：在已有通用导出脚本中增量增加工单领料 PDF 和销售订单对账 PDF。
- `client_akivision/public/js/delivery_note_list.js`：保留原“导出已选对账明细”，新增客户对账 PDF 预检和下载。
- `client_akivision/public/js/material_request_list.js`、`material_request.js`：采购申请列表和详情入口。
- `client_akivision/public/js/work_order.js`：工单详情入口。

### 列表入口加载问题修复

首次验收发现销售订单列表只有 ERPNext 原生“导出”，没有新增操作项。原因是通用列表脚本在原生 `frappe.listview_settings` 尚未初始化时提前返回，导致“导出已选数据”和 PDF 操作均未挂载。现已改为在设置对象不存在时先创建对象，再由列表 `onload` 统一注册操作项；不改变原生“导出”窗口，也不增加 PDF 文件类型选项。

由于 Frappe 每个 DocType 的 `doctype_list_js` 只有一个生效脚本，本次没有新增重复 Hook，而是将按钮合并到已有脚本，避免覆盖原有 Excel 导出、采购对账和自定义业务逻辑。`hooks.py` 无需变更。

## 3. 调用链路

```text
列表勾选 / 表单详情
  -> 已挂载的列表或表单 JS 收集单据号
  -> 对账单先调用 preview_customer_reconciliation 预检
  -> 对应后端模块校验权限、状态、类型和一致性
  -> 独立组装销售 / 工单 / 采购申请数据
  -> formal_pdf_export.render_pdf 加载模板、Logo 并调用 Frappe get_pdf
  -> provide_binary_file 返回 PDF；多单据使用 ZIP
```

## 4. 受影响模块与风险边界

受影响模块为销售订单、送货单、生产工单、BOM、库存领料单、采购申请、员工/部门、客户/公司和打印下载。影响仅为新增操作菜单和只读查询，不进入库存记账、付款分配、采购下单、审批或会计流程。

对账单付款部分当前明确显示“已付款、未付款金额以财务确认为准”，因为送货行到发票行再到付款分配的可靠分摊需要真实财务样本确认，避免重复计算或伪造金额。

## 5. 验证结果

- 宿主机 Python 编译：通过。
- Frappe 容器 Python 编译：通过。
- `aki_test.localhost` 站点可读取应用 Logo（`logo_data_uri` 调用成功）。
- 宿主机未安装 `node`，未能执行 Node JavaScript 语法检查。
- 尚未完成真实单据 PDF 下载、字体/分页/Logo 视觉检查和 Playwright 验收；容器站点若需验证，应使用现有 `devcontainer-frappe-1`，不要启动未配置的 `pwd.yml` 环境。

## 6. 后续验收清单

1. 在 `aki_test.localhost:8300` 分别选择一张及多张销售订单、送货单、工单和采购申请，确认按钮可见且下载文件类型正确。
2. 用中文长物料名、多页明细和无权限/取消/非 Purchase 申请验证拒绝和分页。
3. 核对 Logo 不拉伸、中文不乱码、领料欠料高亮、采购待询价和对账金额合计。
4. 对账财务样本确认后，再决定是否实现精确已付款/未付款分摊。
