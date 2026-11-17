---
title: 库存不足快捷发起采购申请体验优化方案
---

# 库存不足快捷发起采购申请体验优化方案

## 目标

库存不足时保留 Frappe 原生“库存不足”提示，在同一弹窗右下角增加“发起采购申请”入口。用户点击后打开一张未保存的 `Material Request` 草稿，申请类型为 `Purchase`，自动带入本次缺料信息；不自动保存、提交或修改库存校验逻辑。

## 用户流程与调用链

```text
Stock Entry 提交
  -> ERPNext 原生库存校验失败
  -> Frappe 显示“库存不足”消息弹窗
  -> mes_integration 全局 Desk 脚本识别当前 Stock Entry + 缺货文案
  -> 加宽原弹窗、显示底部操作区和“发起采购申请”
  -> 用户点击
  -> 创建未保存 Material Request（material_request_type = Purchase）
  -> 回填公司、缺料物料、缺口数量、单位、发料仓、日期、来源说明
  -> 路由到 Material Request 新建草稿
```

## 修改代码与文件

| 文件 | 修改内容 |
| --- | --- |
| `development/frappe-bench/apps/mes_integration/mes_integration/hooks.py` | 新增 `app_include_js`，确保 Desk 所有页面都加载弹窗增强脚本；使用版本参数规避静态资源缓存。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/public/js/stock_entry_shortage_dialog.js` | 新增全局监听分支：只对草稿 Stock Entry 的原生库存不足弹窗生效；注入右下角入口并创建采购申请草稿。 |
| `development/frappe-bench/apps/mes_integration/mes_integration/public/js/stock_entry.js` | 保留并同步已有 Stock Entry 页面兜底逻辑，入口统一为采购申请。 |
| `development/frappe-bench/apps/client_akivision/docs/playwright_stock_entry_shortage_purchase_order.mjs` | Playwright 验证真实全局脚本的弹窗、窄屏可见性、路由和字段回填。 |

## 字段映射

| 采购申请字段 | 来源 |
| --- | --- |
| `company` | 当前 Stock Entry `company` |
| `material_request_type` | 固定 `Purchase` |
| `transaction_date` / `schedule_date` | 当前日期 |
| `items[].item_code` | 原生错误文案匹配到的 Stock Entry 行 |
| `items[].qty` | 原生错误中的缺口数量 |
| `items[].uom` / `stock_uom` / `conversion_factor` | Stock Entry 行 |
| `items[].warehouse` | 缺料来源仓库 |
| `items[].description` | 标注来源 Stock Entry |

## 受影响模块

- `mes_integration` Desk 前端资源与 Stock Entry 客户端脚本。
- Frappe 原生消息弹窗展示样式。
- ERPNext `Material Request` 新建表单。

不改动 ERPNext 核心库存算法、Stock Entry 原有提交接口、库存错误接口或采购申请审批/提交规则。

## 预期效果

- 用户在库存不足弹窗中直接看到右下角“发起采购申请”。
- 弹窗宽度扩大，底部操作区固定可见；窄屏时按钮占满底部，避免左右滑动后找不到入口。
- 打开的是未保存采购申请草稿，缺料数量为“缺口数量”而非原申请总量。
- 关闭弹窗或不点击入口时，现有库存不足提示与业务行为不变。

## 小增量与回滚

采用新增全局前端分支，不替换旧接口、不修改 ERPNext 核心。回滚只需移除 `app_include_js` 对应资源或关闭该脚本加载；已经由用户保存的采购申请仍按正常业务流程处理。
