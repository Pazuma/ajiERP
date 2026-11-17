# BOM 展开表直接导入实施沉淀

## 1. 实施范围

本次按照《BOM子数据导入字段与模板调整方案.md》实现“BOM 展开表直接导入”模式。

目标是允许用户继续上传现有五列表：

```text
型号 | 层级 | 物料名称 | 图纸号 | 用量
```

系统在预览阶段解析为 1 个 BOM 主表和若干条 `BOM Item` 直接组件，完成主数据匹配、图纸核对和必填校验。未通过预览的文件不能启动导入。

本次没有自动导入现有 `BOM表.xlsx` 的业务数据；代码只提供导入功能和预览能力。

## 2. 已完成修改

### 2.1 后端

修改 [data_import.py](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/client_akivision/api/data_import.py)：

- 增加 `bom_flattened` 导入模式；
- 读取 CSV、XLS、XLSX 的首个工作表；
- 严格校验五列表头：`型号`、`层级`、`物料名称`、`图纸号`、`用量`；
- 强制识别且只能识别一个层级 `0` 顶层行；
- 将层级 `1` 行解析为 BOM 直接组件；
- 按 Item 编码、Item 名称、图纸号候选匹配现有启用物料；
- 自动带出组件 `stock_uom` 作为 BOM Item 单位；
- 校验数量、公司、Item、图纸号、重复 BOM 和层级；
- 预览阶段只读查询，不创建业务数据；
- 点击开始导入后，在一个事务中创建 BOM 和明细；
- 写入标准 `Data Import Log`，供弹窗状态统计；
- 匹配失败、图纸不一致或已有 BOM 时整批阻断，不自动创建 Item、UOM、Company 或工程图纸。

关键接口行为：

| 接口 | 行为 |
| --- | --- |
| `create_inline_import` | BOM 直接模式保存导入模式、公司、数量等任务选项 |
| `preview_inline_import` | 读取原五列表，返回 BOM 摘要、明细匹配结果和阻断警告 |
| `start_inline_import` | 直接模式执行整批 BOM 创建；标准模式继续走 Frappe Data Import |
| `get_inline_import_status` | 复用标准 Data Import 状态和日志统计 |

### 2.2 前端

修改 [inline_data_import.js](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/js/inline_data_import.js)：

- BOM 导入窗口增加“使用展开表直接导入”入口；
- 直接模式要求选择公司，可设置生产数量和默认 BOM；
- 预览表增加 Excel 行号、匹配物料编码、单位、匹配状态；
- 显示 BOM 型号、公司、生产数量、组件数量摘要；
- 有阻断问题时禁用“开始导入”；
- 标准 BOM 模板导入路径保持不变。

修改 [data_import.css](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/css/data_import.css)：

- 增加直接导入摘要样式；
- 预览表使用横向滚动，表头固定，避免移动端字段挤压或遮挡。

### 2.3 测试脚本和产物

新增 [playwright_flat_bom_import_ui.mjs](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_flat_bom_import_ui.mjs)，产物为：

- [playwright_flat_bom_import_ui_result.json](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_flat_bom_import_ui_result.json)
- [playwright_flat_bom_import_ui.png](/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_flat_bom_import_ui.png)

## 3. 数据流

```text
上传 BOM表.xlsx
  -> 创建 Data Import 任务（template_options.import_mode=bom_flattened）
  -> 读取首个工作表
  -> 校验表头和行级格式
  -> 识别层级 0 顶层型号
  -> 查询启用 Item 候选
  -> 查询组件 Item、库存单位和图纸快照
  -> 生成只读预览和阻断警告
  -> 用户处理公司/匹配/图纸问题
  -> 开始导入
  -> 内存组装 BOM + 40 条 BOM Item
  -> 标准 BOM validate / hooks / insert
  -> Data Import Log
  -> 弹窗轮询显示完成或失败
```

当前源文件的预期业务转换：

- 层级 `0`：识别为 `BOM.item`，不写入 `BOM Item`；
- 层级 `1`：写入 `BOM.items`，`custom_import_level=1`；
- `用量`：写入 `BOM Item.qty`；
- `单位`：从匹配 Item 的 `stock_uom` 自动带出；
- `图纸号`：与 Item 当前有效图纸号核对，不能覆盖只读快照；
- 公司：由导入窗口选择；
- 生产数量：默认 `1`，用户可在导入前调整。

## 4. 依赖清单

### 4.1 业务主数据依赖

- 顶层型号必须已存在且启用于 `Item`；
- 每个组件必须能唯一匹配启用 `Item`；
- 组件 Item 必须有有效 `stock_uom`；
- 公司必须存在于 `Company`；
- 若组件关联工程图纸，图纸必须处于 `Finalized`；
- 目标型号不能已有未取消 BOM，除非走更新/修订流程。

### 4.2 系统依赖

- Frappe `File` 能读取上传文件内容；
- Frappe `read_xlsx_file_from_attached_file`、`read_xls_file_from_attached_file`、CSV 读取器可用；
- `BOM` 允许导入且当前用户有导入权限；
- `BOM`、`BOM Item` 标准必填校验可用；
- Akivision BOM 命名、图纸快照和层级校验 hooks 已加载；
- Data Import Log DocType 可写入；
- 浏览器加载最新 `inline_data_import.js` 和 `data_import.css` 资源。

## 5. 风险点清单与处理方式

| 风险 | 影响 | 当前处理/解决方案 |
| --- | --- | --- |
| 图纸号同时被业务当作物料编码 | 自动匹配错误 | 预览同时展示匹配编码和名称；不能唯一匹配则阻断，不自动创建物料 |
| 同名物料多个编码 | 组件归属不确定 | 候选数量不是 1 时阻断，要求维护编码或人工确认 |
| 图纸号与 Item 当前定稿图纸不一致 | BOM 快照错误 | 预览报错，保存前再次由图纸 hook 校验 |
| 文件缺少公司 | BOM 主表无法保存 | 直接模式强制导入窗口选择公司 |
| 文件有多个层级 0 | 可能生成多个 BOM | 只允许一个层级 0 行 |
| 层级大于 1 | 把展开结果误写到顶层 BOM | 阻断并要求拆分子 BOM、使用 `bom_no` 关联 |
| 型号已有 BOM | 覆盖生产依据或历史记录 | 预览阻断，不静默更新 |
| 组件单位缺失 | BOM Item 无法保存 | 从 Item.stock_uom 带出，缺失时阻断 |
| 41 行平铺数据重复型号 | 被错误解析为 41 张 BOM | 自定义解析器只按唯一层级 0 创建 1 张 BOM |
| 文件表头被改名/多列 | 错误映射 | 严格表头校验，预览直接给出修复提示 |
| 解析成功但后台创建失败 | 用户误以为部分成功 | 整批事务处理，失败回滚并显示 Data Import 状态 |
| 标准导入和直接导入逻辑相互影响 | 其他表单回归 | 仅 `BOM + bom_flattened` 分流，其他 DocType 继续走标准 Importer |

## 6. 需要复测的场景

### 6.1 必测成功场景

1. 当前五列表、一个层级 0、40 个层级 1，所有组件可唯一匹配；
2. CSV、XLS、XLSX 三种文件格式；
3. 设置公司、生产数量为 1、默认 BOM 开关；
4. 导入完成后 BOM 明细数量、单位、图纸快照和展开结构一致；
5. 标准 BOM 模板导入仍可正常预览和导入；
6. 移动端预览表横向滚动，字段不重叠。

### 6.2 必测阻断场景

1. 表头缺失或顺序错误；
2. 没有层级 0 或有多个层级 0；
3. 出现层级 2；
4. 型号不存在、组件不存在、组件名称重复；
5. 图纸号与 Item 当前定稿图纸不一致；
6. 公司为空或不存在；
7. 用量为空、非数字或小于等于 0；
8. 型号已有 BOM；
9. 组件没有库存单位；
10. 上传文件不是 CSV/XLS/XLSX 或文件损坏。

### 6.3 权限和并发场景

1. 无 BOM 导入权限的用户不能打开或启动导入；
2. 非任务所有者不能读取或启动任务；
3. 两个用户同时导入同一型号，只有一个能成功，另一个应得到重复 BOM 提示；
4. 导入过程中刷新页面，Data Import 状态仍可查询；
5. 预览后物料或 BOM 被其他用户修改，正式开始导入时必须再次校验。

## 7. Playwright 验证记录

### 已通过

执行：

```bash
development/erpnext.official/.tools/node/bin/node development/frappe-bench/apps/client_akivision/docs/playwright_flat_bom_import_ui.mjs
```

结果：

- 五列表 BOM 直接导入预览：通过；
- 识别 1 张 BOM、40 条组件：通过；
- 显示匹配物料编码、单位、匹配状态：通过；
- 直接导入启动反馈：通过；
- 移动端横向滚动：通过。

已有回归脚本也通过：

- `playwright_inline_data_import_ui.mjs`：导入弹窗、模板下载、标准预览、后台状态通过；
- `playwright_bom_ui.mjs`：BOM 详情字段、展开结构、移动端布局、模板字段配置通过。

### 环境限制

本次未完成真实站点数据库端到端导入：当前主机的 `bench` 命令不可用，直接导入 Frappe Python 模块还缺少 `orjson` 依赖。因此 Playwright 验证使用了本地模拟 API，验证的是前端交互和数据展示，不等同于真实数据库写入验证。

## 8. 后续解决方案

在真实站点复测前应：

1. 恢复 bench 运行环境并安装完整依赖，至少补齐 `orjson`；
2. 使用测试站点和测试公司，不使用生产公司/生产 BOM；
3. 先维护顶层 Item、40 个组件 Item、库存单位和工程图纸；
4. 先上传原五列表预览，逐行处理匹配和图纸警告；
5. 确认预览无阻断后再点击开始导入；
6. 导入后核对 BOM 头、40 条明细、单位、图纸快照、展开层级和 Data Import Log；
7. 发生异常时保留原文件、任务名、预览警告和错误日志，禁止直接重复导入覆盖。

## 9. 结论

代码已支持原五列表的 BOM 直接导入工作流，标准导入路径未改变，前端预览和移动端体验已通过 Playwright 检查。真实数据库导入仍需在依赖完整的 Frappe bench 环境中完成一次测试站点复测；在该复测完成前，不应把功能标记为生产数据导入已验证。
