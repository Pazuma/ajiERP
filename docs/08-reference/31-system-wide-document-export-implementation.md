---
title: 系统业务单据导出实施沉淀
---

# 系统业务单据导出实施沉淀

状态：已完成首版代码落地；库存流水报表筛选导出仍需按实际报表页面单独接入。

## 已实现

- 新增 `client_akivision.utils.document_export.download_document_export` 只读下载接口。
- 支持勾选记录导出和受控筛选结果导出；筛选导出由服务端重新查询，不受列表分页影响。
- 固定字段白名单、单据名称去重、最多 500 条记录、最多 10000 行明细。
- 服务端执行读取权限校验，取消记录和无权限记录进入“导出说明”。
- Excel 生成“数据明细”和“导出说明”工作表。
- 新增通用列表脚本并接入生产领料、盘点、工单、采购收货、物料、项目、销售订单、价目表、固定资产、BOM、工时记录等列表。
- 原采购订单对账导出接口和前端入口保持不变。

## 修改文件

| 文件 | 说明 |
|---|---|
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/document_export.py` | 统一导出服务与 DocType 白名单 |
| `development/frappe-bench/apps/client_akivision/client_akivision/public/js/document_export_list.js` | 列表勾选/筛选结果导出入口 |
| `development/frappe-bench/apps/client_akivision/client_akivision/hooks.py` | 注册目标列表脚本 |
| `development/frappe-bench/apps/client_akivision/client_akivision/utils/test_document_export.py` | 后续补充完整集成测试（首版未启用站点测试） |

## 调用链路

列表操作 -> 收集勾选名称或白名单筛选条件 -> POST 下载接口 -> 权限/状态/数量校验 -> 查询明细 -> XLSX 响应。

## 验证与限制

已完成 Python 语法检查、模块加载验证、前端资源构建和站点缓存刷新。`aki_test.localhost` 当前禁用 `allow_tests`，因此未运行 Frappe 自动化测试。库存出入记录属于报表型数据，需要在对应报表 JS 中复用筛选器后追加导出入口，避免将 Stock Ledger Entry 当成普通可勾选 DocType 处理。
