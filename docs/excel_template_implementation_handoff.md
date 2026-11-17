# Excel 字段模板实施沉淀文档

## 1. 交付结论

本次实现把《Deeplinkerp Excel 字段模板实施方案》落到了现有 `client_akivision` 应用的导入向导中。Excel 字段不再被理解为“全部显示在列表的一组列”，而是登记为四类展示去向：

1. 列表字段：用于编码、名称、状态、日期等日常检索的关键字段。
2. 详情字段：进入客户、物料、订单等记录详情后查看的完整资料。
3. 子表/关联记录：订单明细、BOM 明细、核销分配、多联系人、收发货和库存流水等一对多数据。
4. 系统计算字段：订单金额、已交/未交、库存余额、账龄、供应商及时率等只读结果。

当前交付包含 23 张 Excel 工作表的注册配置、后端读取和审计接口、导入向导展示卡片、表单内弹窗导入、自动化测试及本文档。列表页日常导入使用弹窗完成上传、预览和启动；管理员仍可进入标准 Data Import 查看任务和日志。底层仍使用 Frappe 标准 Data Import，未修改 ERPNext/Frappe 官方核心代码。详细交互说明见 [`表单内弹窗导入实施沉淀.md`](./表单内弹窗导入实施沉淀.md)。

## 2. 代码变更

| 文件 | 作用 |
| --- | --- |
| `client_akivision/config/excel_record_presentation.json` | 23 张工作表的列表字段、详情分区、子表字段、关联记录、计算字段、搜索/筛选字段和字段归属注册表 |
| `client_akivision/utils/excel_record_presentation.py` | 加载注册表、返回展示配置、校验 DocType/字段/子表、检查每个默认导入字段都有展示去向 |
| `client_akivision/client_akivision/api/data_import.py` | 增加 `get_import_presentation` 和 `audit_import_presentation_config` 白名单接口 |
| `client_akivision/public/js/data_import.js` | 选择业务表后展示“导入后查看位置”说明卡，说明列表、详情、子表、关联和只读计算字段 |
| `client_akivision/public/js/inline_data_import.js` | 列表导入弹窗、业务模板选择、字段勾选、模板下载、文件预览和后台进度 |
| `client_akivision/utils/custom_field_schema.py` | 在 `after_migrate` 的字段同步末尾记录展示注册表审计问题，不自动改写页面配置 |
| `client_akivision/client_akivision/api/test_data_import.py` | 校验 23 张表配置完整，并确保计算字段没有进入可写导入字段 |

## 3. 数据流

### 3.1 下载模板

```text
管理员打开 Data Import
  -> 前端请求 get_import_modules / get_import_tables
  -> 选择模块和 Excel 工作表
  -> 后端 get_import_fields 返回 DocType 主表和子表字段
  -> 后端 get_import_presentation 返回展示去向
  -> 前端显示列表/详情/子表/关联/计算说明
  -> 用户选择字段并调用 validate_import_context
  -> Frappe 标准 download_template 生成 Excel 模板

用户在业务列表点击“导入”
  -> 列表入口打开表单内弹窗，不改变当前路由
  -> 上传文件后创建 Data Import 任务并调用标准预览
  -> 用户确认后启动后台任务，弹窗轮询 Data Import Log 并刷新当前列表
```

`excel_import_tables.json` 是可导入范围和默认字段的来源；`excel_record_presentation.json` 只描述导入后如何查找数据，不能绕过 DocType 权限，也不负责创建字段。

### 3.2 上传与保存

```text
用户上传填写后的模板
  -> Frappe Data Import 解析日期、数字、必填字段和 Link
  -> 关联字段按编码/名称规则校验目标记录
  -> 主表字段写入 Customer/Item/Order 等 DocType
  -> 子表行写入订单明细、BOM Item、Payment Entry Reference 等子表
  -> 提交单据后生成库存、应收、应付和状态结果
  -> 列表页显示关键列；详情页展示完整字段和关联记录
```

一张业务单据必须使用单头 + 明细模型。多条物料是多条明细行；采购表中的“交货 1-7”应在清洗阶段拆为交付计划/收货记录，不能继续扩展为主表列。计算字段不作为后续导入列，历史快照如确需留存必须单独标注为只读迁移数据。

### 3.3 展示配置审计流

```text
audit_import_presentation_config()
  -> 检查工作表是否存在
  -> 检查 DocType 是否存在
  -> 检查列表/详情字段是否存在
  -> 检查 child table 和子表字段是否存在
  -> 检查 field_placements 是否为 list/detail/child/related/computed
  -> 检查 excel_import_tables.default_fields 是否全部有展示去向
```

审计只读并返回问题数组，不自动修改 DocType、字段属性或用户保存的列表视图。这样可在迁移前发现新 Excel 列已存储但无法定位的情况。

## 4. 依赖清单

### 4.1 应用与运行时

- Frappe Framework：Data Import、DocType 元数据、权限、标准模板下载。
- ERPNext：Customer、Supplier、Item、BOM、Sales/Purchase Order、Delivery/Purchase Receipt、Payment Entry、Stock Entry、Asset、Timesheet 等标准 DocType。
- `client_akivision`：Excel 配置、客户关联预检、样品借出/借入、成品状态及自定义字段。
- 站点已执行 `after_migrate`，使 `excel_form_fields.json` 和应用补丁创建的自定义字段可被元数据审计识别。

### 4.2 配置依赖

- `config/excel_import_tables.json`：工作表、DocType、模块、默认导入字段、是否可导入。
- `config/excel_form_fields.json`：Excel 所需的自定义字段及列表/筛选属性。
- `config/excel_record_presentation.json`：字段展示注册表。
- 关联主数据：客户、供应商、物料、仓库、单位、项目、销售人员、付款条件、银行账户等必须先建立。

### 4.3 权限依赖

用户必须同时具备：

- 对目标 DocType 的 `import` 权限；
- 对目标 DocType、Link 目标 DocType 和相关仓库/公司数据的读取权限；
- 提交业务单据、库存过账、收付款核销所需的标准角色权限。

展示配置接口不授予任何业务权限；没有导入权限的工作表仍会在服务端过滤为不可导入。

## 5. 风险点清单

| 风险 | 影响 | 控制措施 |
| --- | --- | --- |
| Excel 只填名称、不填稳定编码 | 关联到错误客户/物料，后续单据无法追溯 | 模板优先使用客户编号、供应商编号、物料编码；导入前预检 Link；名称仅作为辅助检索 |
| 标准/自定义字段未完成迁移 | 审计失败或模板缺列 | 迁移后执行展示审计；先执行 `after_migrate`，再开放业务导入 |
| 子表被压平成“交货1-7”等列 | 明细不可追溯，订单进度和库存错误 | 使用主表 + 明细表；交付、收款核销、BOM、批次/SN 均使用子表或关联单据 |
| 把订单金额、库存余额、账龄等结果回填 | 系统计算结果与手工值冲突 | 注册表把结果登记为 `computed_fields`；前端标记只读；导入字段接口只返回可写字段 |
| Link 目标记录不存在或名称重复 | 导入失败或错误关联 | 先导入主数据；编码唯一；客户清单使用关联预检和确认流程 |
| 历史单据直接导入并提交 | 触发库存、会计、审批副作用 | 先导入草稿/历史迁移批次，抽样核对后再按权限提交；禁止直接写状态字段 |
| 同一 Excel 行混合多个业务单据 | 单据聚合错误、重复金额 | 以业务单号作为单头聚合键；明细行单独记录；重复导入使用 Update Existing Records 并保留外部单号 |
| 批号、序列号、库位缺失 | 库存无法盘点或成品状态无法下钻 | 导入前补齐仓库、库位、批次/SN；期初库存只导入盘点确认的数量和估值 |
| 大批量导入造成超时或锁表 | 任务失败、重复提交 | 分模块、分期间、小批量导入；每批记录导入批次和失败行；避免业务高峰操作 |
| 用户个性化列表视图被覆盖 | 日常查询体验变化 | 注册表只作说明和审计，不自动强制设置所有 `in_list_view`；列表默认列控制在关键字段范围 |
| 计算口径变更导致历史报表不一致 | 对账和看板差异 | 记录公式、统计期间、过滤条件；历史快照明确标记口径和来源，不覆盖实时计算 |

## 6. 需要复测的场景

### 6.1 配置与权限

1. Administrator 打开 Data Import，确认 23 张工作表按模块显示；实时库存、供应商回顾、汇总计算和看板只读且不可下载导入模板。
2. 无目标 DocType `import` 权限的用户访问导入向导，确认服务端不返回可导入目标。
3. 修改 `excel_import_tables.json` 增加字段后执行 `audit_import_presentation_config`，确认未配置展示去向时返回 `field_unplaced`。
4. 缺少可选自定义 DocType 的测试站点执行审计，确认返回问题数组而不是阻断整个 Desk。

### 6.2 模板与字段展示

1. 客户清单下载模板，确认客户编号、名称等关键字段在列表说明中，联系人、电话、地址在详情说明中。
2. 产品清单下载模板，导入后从物料列表按编码/名称进入详情，确认备注、状态、说明可见；当前库存、在途量只读并可下钻库存流水。
3. BOM、销售订单、采购订单、付款单分别下载模板，确认主表和子表字段分组存在，多个明细不会被合并为一个单元格。
4. 订单导入后核对列表金额/状态与详情明细、送货、发票和收款关联；订单金额、已交量、未交量不能在导入字段选择中出现。

### 6.3 数据校验与关联

1. 使用不存在的客户、供应商、物料编码导入，确认 Link 校验失败并定位到行和字段。
2. 客户清单执行关联预检，分别测试新建联系人、复用已有联系人、跳过和冲突确认。
3. 测试 Excel 日期序列值、空日期、金额小数、税率百分数和负数库存，确认格式校验和异常行处理符合方案。
4. 同一采购单包含多条物料和多次收货，确认一张采购订单、多条明细和多张收货单的关联链路完整。

### 6.4 库存、样品和财务

1. 期初库存导入后只生成期初/调整事务，实时库存和库存金额由库存总账计算。
2. 采购收货、销售送货、库存调拨、生产领料/完工、退货分别测试，确认库存流水来源单据可反查。
3. 收款/付款带多条核销分配行时，确认已收/未收、已付/未付和账龄随核销自动更新。
4. 客户借出样品、供应商借入样品、归还和转销售分别测试，确认样品状态、序列号和库存去向一致。
5. 成品序列号在生产入库、借出、归还、送货后，确认详情页状态流转和来源单据完整。

### 6.5 并发、重复和回滚

1. 两个用户同时保存同一 Data Import 任务，确认修改检测提示刷新，不覆盖另一用户的选择。
2. 同一文件重复导入，确认唯一编码/外部单号阻止重复或按更新模式更新，并可查询导入批次。
3. 导入中途失败或任务超时，确认失败行可重试，已成功行不会被重复创建。
4. 对已提交单据执行取消/更正流程，确认库存和财务反向分录正确，不直接修改计算结果字段。

## 7. 部署与验证

在 bench 目录执行：

```bash
cd /home/cst/frappe_docker/development/frappe-bench
./env/bin/python -m py_compile \
  apps/client_akivision/client_akivision/utils/excel_record_presentation.py \
  apps/client_akivision/client_akivision/client_akivision/api/data_import.py
python3 -m json.tool apps/client_akivision/client_akivision/config/excel_record_presentation.json >/dev/null
```

站点具备 bench 命令时，再执行：

```bash
bench --site <site> migrate
bench --site <site> run-tests --app client_akivision \
  --module client_akivision.client_akivision.api.test_data_import
```

迁移后用 Administrator 调用 `client_akivision.client_akivision.api.data_import.audit_import_presentation_config`，结果应为空数组。若结果非空，先处理 DocType/字段/子表缺失，再开放批量导入。

本次工作区验证结果：展示注册表和现有导入配置均通过 JSON 解析；新增/修改的 Python 文件通过 `py_compile`。未能执行站点级 bench 测试：当前 `env/bin/python` 是指向不存在 `/home/frappe/.pyenv/versions/3.14.2/bin/python3` 的断开链接，系统 Python 直接加载 Frappe 时还缺少 `orjson`。部署到完整 bench 环境后必须补跑上面的站点测试和人工复测场景。

### 7.1 Playwright 前端交互测试记录

由于本工作区没有运行中的 Frappe HTTP 服务（`8200/8000` 端口不可连接），本次采用受控 API mock 验证真实前端脚本 `public/js/data_import.js` 和 `public/css/data_import.css` 的浏览器交互。测试脚本和证据文件如下：

- 测试脚本：[playwright_excel_import_ui.mjs](./playwright_excel_import_ui.mjs)
- 测试结果：[playwright_excel_import_result.json](./playwright_excel_import_result.json)
- 销售订单截图：[playwright_excel_import_sales_order.png](./playwright_excel_import_sales_order.png)

执行命令：

```bash
/home/cst/frappe_docker/development/erpnext.official/.tools/node/bin/node \
  /home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_excel_import_ui.mjs
```

测试时间：2026-08-22；浏览器：Chromium 151；结果：3/3 通过。

| 场景 | 验证内容 | 结果 |
| --- | --- | --- |
| 只读报表不可导入 | “实时库存”选项存在但被禁用 | 通过 |
| 产品清单展示去向 | 列表字段、详情字段、系统计算字段说明卡正确显示 | 通过 |
| 销售订单计算字段与明细 | 订单明细数量可选；订单金额、未送货量、收款状态只在只读说明中出现，不出现在可写字段选择器 | 通过 |

该测试证明前端渲染、工作表切换和字段选择边界正常；它没有验证登录、真实权限、真实 API、Excel 上传解析、数据库写入、库存过账或财务核销。完整 bench 和站点可用后，必须再执行真实站点 Playwright 验收。

## 8. 当前边界与后续建议

- 本次实现登记了展示去向和校验，不自动生成所有详情页 Tab、关联列表或新的业务单据；这些页面继续使用 ERPNext 和现有自定义 DocType 的标准详情页。
- 统计报表和看板只登记指标与下钻来源，不把汇总结果变成可编辑主数据。
- 采购多次交货、样品归还/转销售、收付款核销的历史数据仍需按业务单据清洗后导入，不能直接把原 Excel 汇总列映射到结果字段。
- 后续可以在详情页统一渲染注册表中的 `detail_sections` 和 `related_records`，并在导入结果页提供每条记录的系统链接；该扩展不应改变当前标准导入的权限和提交语义。
