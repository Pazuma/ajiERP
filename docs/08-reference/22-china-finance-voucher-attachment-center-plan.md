# 中国财务“凭证附件中心”方案

> 状态：方案沉淀，暂不修改业务代码  
> 版本：v0.1  
> 目标站点：`aki_test.localhost`

## 1. 目标与边界

在中国财务的“凭证”分类新增“凭证附件中心”，集中检索、上传、预览、下载、归档和恢复凭证附件，界面参考众马会计截图。本阶段只输出方案文档，不创建页面、不变更数据、不执行迁移。

- 小增量：以现有 `China Electronic Document` 和 Frappe `File` 为唯一归档与文件来源，新建页面及服务分支。
- 兼容优先：不修改 `China Accounting Voucher`、`China Accounting Voucher Entry`、凭证快照生成服务或现有 `archive.py` 白名单接口。
- 先关联后归档：上传时必须关联一张已有 `China Accounting Voucher`；不把附件中心设计成脱离凭证的网盘。
- 审计可追溯：保留文件哈希、归档人、归档时间、保管期限和操作日志；不以物理删除替代归档状态流转。

## 2. 参考图样式与交互

页面标题“凭证附件中心”，布局分为三部分：

1. 顶部：文件名搜索框、`上传文件`、`批量操作` 下拉、`备份恢复`；可显示当前公司和会计期间。
2. 中部：浅灰页面背景中的白色文件表格，采用当前系统的浅灰表头。列为文件名称、文件大小、文件类型、关联凭证、上传日期、文件路径、操作；支持排序、分页和空状态。
3. 原参考图右侧的空间用量、文件夹树和期间辅助栏不纳入最终实现；附件列表使用全宽单列布局。

### 2.1 与当前系统协调的视觉规范

- 页面使用标准 `frappe.ui.make_app_page`，保留 Desk 顶栏、面包屑、页面标题和现有中国财务侧边栏，不额外制作一套应用导航。
- 内容宽度、左右留白和控件高度沿用当前 China Finance 页面；主区域使用白色背景、细边框和轻量阴影，不做大面积深蓝背景。
- 筛选区使用 Frappe 标准 `Link`、`Date`、`Data` 控件。主操作使用系统 `btn-primary`，预览、下载、批量操作等使用 `btn-default` 与图标按钮。
- 表头采用当前系统的浅灰中性样式和清晰分隔线，不使用参考图的整行高饱和蓝色；选中、链接和进度状态使用系统主题变量。
- 页面采用全宽单列表格布局，不设置右侧辅助栏；期间由顶部筛选统一表达。
- 文件表格保持紧凑，行高约 40 至 44px；长文件名和路径单行省略并提供 tooltip，金额/容量右对齐，操作列固定宽度，避免动态内容导致布局跳动。
- 空间用量以细进度条和文字呈现；没有服务端配额时明确显示“已使用”，不虚构总容量。
- 状态使用现有绿色、橙色、红色和文本弱化色，不另建单一蓝色视觉体系。
- 卡片仅用于空间统计或重复文件项，不把筛选区、主表和右侧栏层层包成卡片。

## 3. 一期功能

1. 选择公司与期间（月），或改用自定义上传日期范围。
2. 文件名、凭证字号、摘要模糊搜索；按上传日期、文件类型、关联凭证筛选。
3. 展示 `China Electronic Document` 中 `document_category = Accounting Voucher` 且关联 `China Accounting Voucher` 的档案。
4. 单文件上传：先选凭证，再使用 Frappe 标准上传器上传私有文件，创建归档记录；服务端复用哈希去重。
5. 表格操作：预览/下载、打开关联凭证、验真；批量下载和批量归档包导出作为一期后半段。
6. 页面不展示空间统计、配额进度或文件夹树；服务端可保留已有统计返回字段以兼容旧调用。
7. “备份恢复”：一期只提供受控的归档包下载入口和恢复方案入口，不允许覆盖已有档案；完整导入恢复、冲突处理列为二期。

## 4. 现有数据模型和来源

```text
浏览器上传
  -> Frappe File（私有文件、file_url、file_name）
  -> create_archive_record(..., "Accounting Voucher", file_url)
  -> China Electronic Document
       company / reference_doctype / reference_name
       file / file_name / mime_type / file_size / sha256
       archived_on / archived_by / retention_until / status
  -> China Accounting Voucher（关联凭证与凭证字号）
```

现有 `China Electronic Document` 已在提交时经 `populate_archive_metadata` 补齐文件元数据、SHA-256、归档人和保管期限；`create_archive_record` 已以公司、关联对象和哈希实现并发防重。附件中心只读取或调用这些能力，不复制哈希和文件存储逻辑。

注意：`China Accounting Voucher.attachment_count` 当前是只读快照字段，方案一期不自动回写。是否将电子档案数同步到该字段，需作为独立变更评审，避免改变既有凭证审计快照口径。

## 5. 计划新增/最小修改文件

| 文件 | 计划变更 | 用途 |
|---|---|---|
| `china_finance/page/china_voucher_attachment_center/china_voucher_attachment_center.json` | 新增 | Page 元数据和角色权限 |
| `china_finance/page/china_voucher_attachment_center/china_voucher_attachment_center.js` | 新增 | 搜索、筛选、上传器、表格、批量动作、右侧期间栏 |
| `china_finance/public/css/china_voucher_attachment_center.css` | 新增 | 页面局部布局与表格样式，复用 Frappe CSS 变量与当前 China Finance 间距 |
| `china_finance/services/voucher_attachment_center.py` | 新增 | 列表、统计、凭证选择、受控上传归档、批量导出/恢复分支 |
| `china_finance/tests/test_voucher_attachment_center.py` | 新增 | 权限、公司隔离、重复文件、筛选与恢复校验 |
| `china_finance/china_finance/workspace/china_finance/china_finance.json` | 最小修改 | 增加“凭证附件中心” Page 入口 |
| `china_finance/china_finance/workspace_sidebar/china_finance.json` | 最小修改（若侧边栏启用） | 在“凭证”或“审计与归档”分类增加入口 |
| `china_finance/hooks.py` | 最小修改 | 仅将新页面 CSS 加入资源清单；页面 JS 按路由加载 |

不修改：`services/archive.py` 现有 `create_archive_package` 与 `export_archive_package`、`China Electronic Document` DocType 字段、凭证生成/冲销链路、既有“电子会计档案”DocType 列表。

## 6. 建议新增接口

- `get_voucher_attachments(filters)`：返回表格行、分页、空间统计、已应用时间范围。
- `get_voucher_attachment_context(company, period)`：返回用户可见凭证及默认期间。
- `archive_voucher_attachment(company, voucher_name, file_url, notes)`：校验文件和凭证权限后调用现有 `create_archive_record`。
- `verify_voucher_attachment(name)`：委托现有 `verify_archive` 或提取共享只读方法，不修改旧接口。
- `create_voucher_attachment_export(filters)`：新增独立导出分支；权限和文件范围与列表一致。
- `validate_attachment_restore(package_file)` / `restore_voucher_attachments(...)`：一期仅校验和预览，二期才允许受控导入。

所有接口使用参数绑定、服务端公司权限校验和文件归属校验。页面不得直接通过 File API 绑定任意凭证。

## 7. 调用链路

```text
打开“凭证附件中心”
  -> Page 初始化公司、期间、搜索和右侧统计
  -> get_voucher_attachments(filters)
  -> China Electronic Document + China Accounting Voucher + File 查询
  -> 返回文件行、分页和空间用量

上传文件
  -> Frappe FileUploader 上传私有 File
  -> archive_voucher_attachment(company, voucher, file_url)
  -> archive.create_archive_record(..., "Accounting Voucher", file_url)
  -> China Electronic Document（哈希防重）
  -> 刷新列表
```

## 8. 权限、安全与数据规则

- 浏览：`China Archive User`、`China Finance Auditor`、`Accounts Manager`、`China Finance Manager`、`System Manager`；最终以 China Electronic Document 和凭证读取权限交集为准。
- 上传/归档：仅具备归档创建权限且可读取目标凭证的用户；禁止 `ignore_permissions` 直接暴露到页面接口。
- 文件：默认私有；下载和预览每次验证档案、公司和关联凭证权限。
- 删除：一期不提供物理删除。允许的“删除”只能变更为 `Superseded` 并记录替代文件，具体流程放二期。
- 恢复：不覆盖同哈希或同关联凭证已有档案；先预览冲突，再以新增档案方式导入。

## 9. 受影响模块

- 中国财务凭证：新增附件入口和凭证关联选择，不改变凭证金额、状态或快照。
- 电子会计档案：作为唯一索引与审计记录，被新增页面只读/新增调用。
- Frappe File：作为实际私有文件存储和预览下载来源。
- 中国财务设置：复用现有归档保管年限；容量配额不在一期写入设置。
- 工作区/侧边栏：仅新增导航项，既有“电子会计档案”入口继续保留。

## 10. 实施阶段、验收与回滚

阶段一：Page、列表查询、公司/月份/日期筛选、单文件上传归档、预览下载、验真和空间统计。  
阶段二：批量下载、档案包导出、分类目录与按月归档视图。  
阶段三：恢复导入、配额控制、替换/作废流转和附件数同步评审。

验收包括：公司隔离、无权限拦截、月份和日期边界、同文件同凭证防重、哈希验真、私有文件访问、空状态、分页、上传后可查询及不影响现有归档包导出。视觉验收覆盖 `1440px`、`1024px` 和移动端宽度，确保工具栏换行、表格滚动、右侧栏折叠、长文件名和操作按钮无重叠。回滚只移除新增 Page、服务、样式、测试和导航链接；不涉及表结构迁移，不删除 File 或电子档案历史数据。

## 11. 预期效果

用户可以在凭证分类中使用与当前 China Finance 风格一致的文件中心，按时间、文件名或凭证检索附件，将文件安全归档到指定凭证，并完成预览、下载和验真。页面保留参考图清晰的文件管理结构，但整体视觉自然融入现有 Desk；既有电子会计档案、凭证快照与归档接口保持兼容，功能可独立上线和回滚。
