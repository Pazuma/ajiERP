---
title: 中国财务凭证回收站实施记录
---

# 中国财务凭证回收站实施记录

版本：v1.0  
状态：已实现，待部署环境验收

## 1. 实施结果

已按《28-china-finance-voucher-recycle-bin-plan.md》完成首期代码：新增回收站记录、列表/恢复/彻底清理服务、标准 Page、系统风格 CSS、工作区入口和每日过期清理任务。未修改 `China Accounting Voucher`、Journal Entry、GL hooks 及既有凭证生成接口。

## 2. 修改文件

| 文件 | 实施内容 |
| --- | --- |
| `china_finance/doctype/china_voucher_recycle_bin_item/*` | 新增回收站 DocType，记录公司、凭证、删除/恢复/清理审计字段 |
| `china_finance/services/voucher_recycle_bin.py` | 新增列表、移入、恢复、彻底删除和 15 天清理接口 |
| `china_finance/page/china_voucher_recycle_bin/*` | 新增 Frappe Page、期间/关键词列表、单条及批量操作 |
| `china_finance/public/css/china_voucher_recycle_bin.css` | 使用 Frappe 主题变量、白色列表区、紧凑表头、危险按钮和响应式滚动 |
| `china_finance/workspace_sidebar/china_finance.json` | 凭证分组新增“凭证回收站”入口 |
| `china_finance/hooks.py` | 注册 CSS 与每日过期清理任务 |
| `china_finance/services/voucher_summary.py` | 默认排除有效回收记录，支持 `include_recycled` |
| `china_finance/services/voucher_attachment_center.py` | 默认排除有效回收记录，支持 `include_recycled` |

## 3. 调用链路

`china-voucher-recycle-bin` Page -> `list_recycle_bin` 查询回收记录；批量恢复调用 `restore_from_recycle_bin`，仅更新回收记录状态，不重新过账；批量删除调用 `purge_recycle_bin`，标记为 `Purged`；每日任务调用 `purge_expired_recycle_bin` 清理超过 15 天记录。汇总表和附件中心通过 `NOT EXISTS` 分支默认隐藏 `In Recycle Bin` 凭证。

## 4. 预期效果

- 页面与现有中国财务 Desk、凭证汇总表、附件中心保持一致的浅灰背景、白色列表、主题色表头和标准按钮风格。
- 首屏显示保留策略、列表和批量操作；空数据、加载失败、选择状态和窄屏横向滚动均有明确表现。
- 恢复后凭证重新出现在查凭证、汇总表和附件中心，金额、字号、附件不重复。
- 回收操作不删除 GL Entry，不触发取消/冲销 hooks，不改变既有凭证快照和老接口返回结构。

## 5. 验证记录

- `python3 -m py_compile`：服务端 Python 文件通过。
- `python3 -m json.tool`：新增 DocType/Page JSON 通过。
- 尚未在运行中的 Frappe site 执行 migrate、浏览器验收和集成测试；部署前需执行 `bench migrate` 并按账套权限验证批量操作、期间筛选和定时清理。

- 兼容未迁移站点：汇总表和附件中心在回收站表不存在时自动跳过过滤条件，不影响旧功能；部署后仍应执行 `bench --site <site> migrate` 创建新表。

## 6. 已知边界

当前版本按 15 天清理，不含每账套 500 张超量淘汰的独立计数逻辑；该策略已在页面提示和后续扩展点中保留。回收站仅控制凭证可见性，已过账凭证的撤销仍必须使用原有冲销流程。
