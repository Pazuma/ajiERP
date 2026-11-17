---
title: 库存不足采购申请入口实现沉淀
---

# 库存不足采购申请入口实现沉淀

关联方案：[库存不足快捷发起采购申请体验优化方案](./10-stock-shortage-purchase-order-ux-plan)。

## 已实现效果

在草稿 `Stock Entry` 提交失败并显示原生“库存不足”消息时，弹窗会被增强为更宽的布局，底部右侧显示“发起采购申请”。点击后关闭提示并打开一张未保存的 `Material Request`：

- `material_request_type = Purchase`
- 回填 Stock Entry 公司
- 回填缺货物料、缺口数量、单位、换算率、来源仓库
- 回填当天的申请日期和明细计划日期
- 明细描述保留来源 Stock Entry 信息

该动作只创建浏览器内的新建草稿，用户仍需按 Material Request 标准校验保存和提交。

## 数据流

```text
Stock Entry 草稿
  -> 原生库存校验异常文案
  -> stock_entry_shortage_dialog.js 监听可见 msg_dialog
  -> 解析“仓库 / 物料 / 数量还缺”
  -> 匹配 Stock Entry items 补全单位、换算率
  -> frappe.model.get_new_doc("Material Request")
  -> frappe.model.add_child(material_request, "items")
  -> frappe.set_route("Form", "Material Request", 新草稿名)
```

解析不到原生异常中的明细时，脚本使用当前 Stock Entry 中带来源仓且数量大于零的行做安全兜底；因此入口不会因异常文案格式的细微变化而消失。

## 依赖清单

| 依赖 | 用途 |
| --- | --- |
| Frappe Desk `app_include_js` | 全局加载弹窗增强脚本，覆盖标准“提交”按钮触发的错误弹窗。 |
| Frappe `frappe.msg_dialog` | 复用原生库存不足弹窗，不新增第二层弹窗。 |
| Frappe `frappe.model` / `frappe.set_route` | 创建并打开未保存的 Material Request 草稿。 |
| ERPNext `Stock Entry` | 提供公司、物料行、来源仓库和库存校验错误。 |
| ERPNext `Material Request` | 承接采购申请草稿及后续标准权限、保存、审批流程。 |

## 修改文件

| 文件 | 作用 |
| --- | --- |
| `mes_integration/hooks.py` | 注册 `/assets/mes_integration/js/stock_entry_shortage_dialog.js?v=2026082702`。 |
| `mes_integration/public/js/stock_entry_shortage_dialog.js` | 原生弹窗监听、样式增强、采购申请草稿回填。 |
| `mes_integration/public/js/stock_entry.js` | 保留 Stock Entry 局部兜底逻辑，口径同步为采购申请。 |
| `client_akivision/docs/playwright_stock_entry_shortage_purchase_order.mjs` | 验证全局脚本的实际行为。 |

## 风险点与解决方案

| 风险 | 处理方式 |
| --- | --- |
| 浏览器继续命中旧静态资源 | `app_include_js` 使用版本参数；已清理站点缓存、网站缓存并重启 Frappe 容器。 |
| 标准提交流程未进入 doctype JS 回调 | 使用 Desk 全局脚本和 `MutationObserver` 监听原生消息弹窗。 |
| Frappe/ERPNext 错误文案调整 | 优先解析中文库存不足文案，失败后回退到当前 Stock Entry 行。 |
| 用户没有采购申请创建权限 | 点击后仍由 Material Request 标准权限控制；建议用无权限账号复测提示体验。 |
| 采购申请还有企业必填字段 | 仅打开未保存草稿，供应商、部门、审批等继续走现有标准规则。 |
| 多物料缺货 | 当前正则可收集多条“仓库/物料/缺口”信息；应在真实多行缺货单据复测。 |

## 需要复测的场景

- 单物料、单仓库存不足：入口显示，数量等于缺口。
- 多物料或多仓库存不足：每项均回填到采购申请明细。
- 中文及英文库存错误文案：入口可见，英文文案时走 Stock Entry 行兜底。
- 390px 窄屏：底部入口完整可点，不出现横向滚动依赖。
- 用户关闭弹窗、不点击入口：原有提示和 Stock Entry 提交结果保持不变。
- 无 Material Request 创建权限、采购申请存在企业自定义必填项：按标准权限和保存校验处理。

## 验证记录（2026-08-27）

已通过 Playwright 验证：

- 原生“库存不足”弹窗保留。
- 右下角“发起采购申请”按钮可见，窄屏下不被隐藏。
- 点击后路由为 `Form / Material Request / new-material-request`。
- 采购类型、公司、物料编码、缺口数量、单位、库存单位、仓库和日期均正确回填。

同时已执行 Frappe 缓存清理、网站缓存清理并重启 `devcontainer-frappe-1`。运行时 hooks 已确认加载版本 `stock_entry_shortage_dialog.js?v=2026082702`。
