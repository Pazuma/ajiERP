---
title: 统一出入库表单体验优化实施沉淀
---

# 实施结果

本次按[统一出入库表单体验优化方案](./14-unified-stock-entry-form-ux-plan.md)完成第一期表单降噪和业务联动，并补充了采购入库入口保护。新建 `Stock Entry` 的主流程现在是“出/入库方向 -> 出入库原因 -> 物料明细”，用户不再直接选择 ERPNext 内部库存类型，也不需要手填业务单号。

## 用户可见效果

- “出库类型”和“入库类型”统一为“出/入库方向”，候选值为“出库”“入库”。
- “出入库原因”按方向动态过滤：出库只显示领料、补料、外发、借用和其它领用；入库显示退料、生产入库和采购入库。
- 原因自动映射到既有 ERPNext `Stock Entry Type`，例如“生产领料”映射为“组装领料”，“生产入库”映射为“生产制造”。
- 新建手工单据显示“单号：保存后系统自动生成”；保存后继续使用 ERPNext 的 `Stock Entry.name`。
- 新建手工单据隐藏编号模板、底层库存类型和 Excel 历史导入字段；历史单据仍可按已有数据展示追溯信息。
- 选择“采购入库”时提示使用“采购收货单”，确认后进入 `Purchase Receipt` 新建页，保留供应商、采购订单和应付关联。
- 历史导入信息单独放入默认折叠的“历史导入信息”分区。
- 桌面端保持双列核心信息布局，390px 移动端无横向滚动。

## 修改文件

- [`client_akivision/config/excel_form_fields.json`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/config/excel_form_fields.json)
  - 为 `Stock Entry` 增加方向、原因、只读单号 HTML 和历史信息分区。
  - 保留全部 `custom_excel_*` 历史字段，不删除、不改字段名。
- [`client_akivision/public/js/stock_entry_labor.js`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/js/stock_entry_labor.js)
  - 实现方向/原因联动、原因到库存类型映射、采购收货跳转、单号展示和新建表单布局。
  - 在 ERPNext 原生库存类型刷新后重新应用隐藏规则，避免编号模板被联动逻辑重新显示。
- [`client_akivision/utils/stock_entry_types.py`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/utils/stock_entry_types.py)
  - 保存前校验方向与原因匹配，禁止采购入库直接保存为 `Stock Entry`，并确认底层库存类型存在。
  - 维护业务原因到 ERPNext `purpose` 对应库存类型的同步和校验。
- [`client_akivision/utils/custom_field_schema.py`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/utils/custom_field_schema.py)
  - 注册新增自定义字段及历史字段元数据。
- [`client_akivision/hooks.py`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/hooks.py)
  - 挂载 Stock Entry 前端脚本和保存前校验事件。
- [`client_akivision/utils/test_stock_entry_types.py`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/utils/test_stock_entry_types.py)
  - 增加方向/原因映射、错误方向、采购入库和库存类型存在性回归测试。
- [`client_akivision/docs/playwright_unified_stock_entry_form.mjs`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_unified_stock_entry_form.mjs)
  - 保存可重复执行的真实站点浏览器回归脚本。

## 数据流

```text
新建 Stock Entry
  -> 选择 custom_stock_direction（出库 / 入库）
  -> 前端过滤 custom_stock_reason
  -> 原因映射 STOCK_ENTRY_REASON_MAP
  -> 设置 stock_entry_type（ERPNext 原生库存类型）
  -> 填写物料、仓库、数量等明细
  -> 保存前 apply_stock_entry_reason 再次校验方向/原因/类型
  -> ERPNext 按既有 purpose 执行库存账务并生成 Stock Entry.name

采购入库分支：
  custom_stock_reason=采购入库
  -> 前端确认提示
  -> 新建 Purchase Receipt
  -> 供应商、采购订单、送货单和应付关系继续由 Purchase Receipt 维护
```

历史 Excel 数据不经过新的手工原因校验路径：导入仍可写入原有 `stock_entry_type` 和 `custom_excel_*` 字段；展示层只负责把这些字段移到追溯分区。

## 依赖清单

| 依赖 | 用途 |
| --- | --- |
| Frappe `Stock Entry` Form API | 字段监听、动态 options、显示/隐藏和新建路由 |
| ERPNext `Stock Entry Type` | 保存实际库存业务类型和 `purpose` |
| ERPNext `Purchase Receipt` | 承接采购入库，保留采购和应付关联 |
| `app_include_js` / `doctype_js` hooks | 发布客户端脚本和后端文档事件 |
| Custom Field schema + `bench migrate` | 创建方向、原因、单号 HTML 和历史分区字段 |
| ERPNext 命名系列 | 保存时自动生成 `Stock Entry.name`，前端不拼接编号 |
| Playwright + Chromium | 桌面、移动端、交互、截图和运行时错误检查 |

## 风险点与解决方案

| 风险 | 解决方案 / 当前状态 |
| --- | --- |
| 方向与原因不一致导致错误库存方向 | 前端切换方向时清空不兼容原因；后端保存前再次拒绝不匹配组合。 |
| 采购入库误建为 Stock Entry | 前端确认后跳转 Purchase Receipt；后端禁止 `采购入库` 原因保存为 Stock Entry。 |
| ERPNext 原生刷新重新显示编号模板或库存类型 | 在 `stock_entry_type` 更新完成后重新执行表单布局规则；Playwright 已覆盖。 |
| 历史导入字段被删除或报表失效 | 只调整展示条件和分区，不删除字段、不改字段名、不改旧导入口径。 |
| 新增原因映射到不存在的库存类型 | migrate 同步类型；保存前检查 `Stock Entry Type` 存在性；Python 回归测试覆盖。 |
| 前端静态资源缓存旧版本 | 已执行 `bench build --app client_akivision` 和 `bench --site aji_test.localhost clear-cache`。 |
| 已有站点资源噪声影响控制台 | Playwright 记录到既有 `custom_filters/public/js/naming_series_i18n.js` 404 和 `Cannot read properties of null (reading 'join')`；未发现本次表单新增异常。建议单独修正 `custom_filters/hooks.py` 的资源路径为已构建的 `/assets/custom_filters/js/naming_series_i18n.js`，并排查其 `join` 空值来源。 |
| 保存/提交仍受 ERPNext 物料、仓库、批次等标准规则影响 | 本次只增加方向/原因规则；保存和提交应继续走 ERPNext 原生校验。 |

## 已发现问题及处理

1. 初次 Playwright 使用 `127.0.0.1:8200`，返回站点 404 登录壳，无法找到登录字段。改用 `http://aji_test.localhost:8200` 后恢复真实站点测试。
2. 采购确认框本地化按钮为“否/是”而非“取消/确认”，脚本已按实际按钮文案处理，并验证点击“是”进入 `Purchase Receipt`。
3. 原生库存类型联动会短暂恢复编号模板显示。增加 `stock_entry_type` 事件和异步回调重新应用布局，复测通过。
4. 浏览器存在自动播放提示音报错；该错误与表单无关，已作为已知自动化环境噪声记录。
5. 测试期间发现右下角外部通知浮层遮挡截图，脚本在截图前清理 toast/alert，最终证据截图无浮层遮挡。

## Playwright 验证记录

站点：`http://aji_test.localhost:8200`，Chromium，桌面 `1440x1000`，移动端 `390x844`。

结果文件：[`playwright_unified_stock_entry_form_result.json`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_unified_stock_entry_form_result.json)

截图：

- [`playwright_unified_stock_entry_form_desktop.png`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_unified_stock_entry_form_desktop.png)
- [`playwright_unified_stock_entry_form_mobile.png`](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_unified_stock_entry_form_mobile.png)

已通过的断言：

- 首屏公司、方向、原因、单号、日期和时间字段完整。
- 出库/入库原因联动正确，生产领料 -> 组装领料、生产入库 -> 生产制造映射正确。
- 切换方向会清空不兼容原因。
- 采购入库提示正确，确认后进入 Purchase Receipt 新建页。
- 新建页隐藏底层库存类型、编号模板和历史导入字段。
- 桌面端无横向溢出，移动端无横向溢出。
- 未发现本次功能新增的未处理网络或页面异常。

Playwright 运行时仍记录到站点既有问题：`custom_filters/public/js/naming_series_i18n.js` 请求失败、`Cannot read properties of null (reading 'join')`。这些问题在本次修改前已存在，已从新增功能断言中单独分离。

## 需要复测的场景

1. 每个出库原因分别创建草稿并保存，确认库存方向、源仓库和 `purpose` 正确。
2. 生产退料、生产入库关联真实工单后保存/提交，确认生产模块既有校验不变。
3. 采购入库从统一入口进入 Purchase Receipt，补齐供应商、采购订单、送货单、质检和应付关联后保存/提交。
4. 旧 Excel 导入单据打开后，历史导入信息分区可展开，原始单号、来源行、供应商和说明仍可查询。
5. 已保存单据重新打开，单号显示真实 `Stock Entry.name`，底层库存类型和历史字段按数据条件显示。
6. 空原因、方向与原因不匹配、采购入库误保存等错误提示，在无权限账号和不同语言环境下均清晰可见。
7. 物料明细的源库位/目标库位、批次、序列号、数量精度和库存不足校验按 ERPNext 标准流程复测。
8. 390px、768px 和 1440px 视口下检查表单、弹窗、明细表和保存按钮，不出现遮挡或横向滚动。
9. 独立修复 `custom_filters` 资源路径和 `join` 空值问题后，重新执行全量 Desk Playwright 回归，确认控制台无遗留错误。

## 验证命令

```bash
docker exec devcontainer-frappe-1 bash -lc \
  'cd /workspace/development/frappe-bench && bench build --app client_akivision'

docker exec devcontainer-frappe-1 bash -lc \
  'cd /workspace/development/frappe-bench && bench --site aji_test.localhost clear-cache'

development/erpnext.official/.tools/node/bin/node \
  development/frappe-bench/apps/client_akivision/docs/playwright_unified_stock_entry_form.mjs
```

Python 回归测试文件已添加并在此前迁移验证中通过 4/4；当前站点 `allow_tests=false`，再次执行 `bench run-tests` 会被站点策略阻止，未为浏览器验收临时修改该配置。
