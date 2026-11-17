# 项目详情多 PDF 文件上传优化方案

## 1. 文档目的

本文沉淀“在具体项目中维护多个 PDF 文件”的小增量实现方案，供后续开发、评审、测试和验收使用。

本文阶段只定义方案，不修改业务代码、不执行数据库迁移。

> 实施调整（2026-09-20）：根据后续确认，页面不直接展示可编辑子表。最终交互为一个“添加文件”按钮和简洁文件列表；底层子表仅用于存储。列表提供查看、重命名和删除，添加、重命名、删除继续写入项目活动日志。

## 2. 已确认需求

- 文件属于某一条具体的 `Project`，用户必须进入该项目详情后查看。
- 一个项目可以上传多个文件。
- 当前只允许 PDF，不做文件分类。
- 具有项目读取权限的用户可以查看和下载。
- 具有项目写权限的用户可以上传、修改文件名称或备注、删除。
- 项目关闭或完成后不额外锁定文件，仍按项目写权限判断是否可维护。
- 文件默认保存为私有文件，不能通过公开 URL 绕过权限。
- 上传、删除、修改文件名称或备注必须在项目详情底部“活动”时间线留痕。
- 普通查看和下载暂不写入活动时间线，避免高频日志淹没业务变更记录。

## 3. 现状与约束

当前项目详情基于 ERPNext 标准 `Project` DocType，并由 `client_akivision` 扩展：

- `project_development_application.py` 使用 `PROJECT_FIELDS` 和 `ensure_schema()` 同步 Project 自定义字段。
- `hooks.py` 已在 `after_migrate` 中调用项目扩展同步，并为 Project 注册多个校验事件。
- Project 表单已加载成本核算、流程进度脚本。
- Frappe 已提供标准 `File`、私有文件下载、文档权限和时间线能力。

标准右侧“附件”虽然支持多文件，但入口不够明确、不能承载文件名称和备注，也无法按本需求输出稳定、清晰的操作日志。因此保留标准附件能力，不修改其接口；新增一个只服务于“项目文件”的分支。

## 4. 总体方案

在 Project 中新增独立的“项目文件”页签和一个子表字段。子表每行代表一个项目 PDF，文件本体继续使用 Frappe 标准私有 `File` 保存。

建议字段如下：

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| 文件名称 | Data | 必填；默认取上传文件名，可修改 |
| PDF 文件 | Attach | 必填；仅允许 `.pdf`，保存为私有文件 |
| 备注 | Small Text | 可选 |
| 上传人 | Link / User | 后端自动写入，只读 |
| 上传时间 | Datetime | 后端自动写入，只读 |

Project 新增字段：

| 字段名 | 类型 | 用途 |
| --- | --- | --- |
| `custom_project_files_tab` | Tab Break | “项目文件”独立页签 |
| `custom_project_files_section` | Section Break | 文件区域 |
| `custom_project_files` | Table | 指向 `Project File Item` 子 DocType |

### 4.1 设计原则

1. 不修改 ERPNext 标准 `Project`、`File` 源码。
2. 不覆盖标准上传、下载和 Project 保存接口。
3. 沿用现有 `after_migrate -> ensure_schema()` 扩展方式。
4. PDF 类型、私有属性、项目权限和审计均由后端兜底，前端只负责友好提示。
5. 新能力以独立字段、独立校验函数和独立表单脚本加入，尽量不影响成本、进度和项目申请功能。

## 5. 调用链路

### 5.1 安装或升级

```text
bench migrate
  -> hooks.after_migrate
  -> project_development_application.ensure_schema()
  -> reload Project File Item DocType
  -> create_custom_fields(Project 项目文件页签/子表)
  -> 更新 Project 元数据并清理缓存
```

### 5.2 上传并保存

```text
用户进入 Project 详情
  -> “项目文件”页签新增一行
  -> Attach 控件调用 Frappe 标准上传能力
  -> File 以 private 文件保存并关联当前 Project
  -> 用户保存 Project
  -> Project validate
  -> validate_project_files()
       -> 检查用户对 Project 有 write 权限
       -> 检查扩展名和 File 元数据为 PDF
       -> 强制确认 File.is_private = 1
       -> 补齐上传人、上传时间、默认文件名称
  -> Project on_update
  -> log_project_file_changes()
       -> 对比保存前后的项目文件行
       -> 为新增/修改/删除写入 Project 的 Info Comment
  -> 时间线显示操作人、动作、文件名和时间
```

### 5.3 查看或下载

```text
用户进入 Project 详情
  -> Project read 权限校验
  -> 读取项目文件子表
  -> 点击 PDF
  -> Frappe 私有文件下载接口
  -> File 关联文档权限校验
  -> 返回 PDF
```

未获得该 Project 读取权限的用户，不应从表单、API 或私有文件地址读取文件。

### 5.4 删除

```text
用户从项目文件表删除一行并保存
  -> Project write 权限校验
  -> Project 更新成功
  -> 记录“删除了项目文件：xxx.pdf”到活动时间线
  -> 清理由该行引用且不再被其他业务引用的 File 记录和私有文件
```

物理文件清理必须采用“确认无其他引用后删除”的分支，不能按 URL 直接删除，避免误删共享文件。项目保存失败时不执行清理。

## 6. 预计修改文件

### 6.1 新增文件

| 文件 | 预计内容 |
| --- | --- |
| `client_akivision/client_akivision/doctype/project_file_item/__init__.py` | 子 DocType 包初始化 |
| `client_akivision/client_akivision/doctype/project_file_item/project_file_item.json` | 文件名称、附件、备注、上传人、上传时间字段 |
| `client_akivision/client_akivision/doctype/project_file_item/project_file_item.py` | 子表模型，保持轻量，不提供独立接口 |
| `client_akivision/utils/project_files.py` | PDF 校验、私有文件校验、权限检查、变更对比、时间线日志和安全清理 |
| `client_akivision/public/js/project_files.js` | 上传控件限制、默认文件名、错误提示和页签交互 |
| `client_akivision/utils/test_project_files.py` | 后端权限、格式、日志和删除回归测试 |
| `client_akivision/docs/playwright_project_files.mjs` | 项目详情端到端验收脚本 |

### 6.2 修改文件

| 文件 | 预计改动 |
| --- | --- |
| `client_akivision/utils/project_development_application.py` | 在 `PROJECT_FIELDS` 末尾新增项目文件页签、区块和 Table 字段；`ensure_schema()` 先 reload 子 DocType |
| `client_akivision/utils/custom_field_schema.py` | 将三个 Project 自定义字段加入 `REQUIRED_FIELDS["Project"]` 自检范围 |
| `client_akivision/hooks.py` | Project 表单脚本追加 `project_files.js`；Project 事件追加文件校验和更新后日志；必要时加入事务成功后的文件清理任务 |
| `client_akivision/translations/zh.csv` | 如界面存在英文源标签，补充对应中文翻译 |
| `client_akivision/patches.txt` | 仅当现有 `after_migrate` 不能完整覆盖数据修复时新增一次性补丁；正常情况下不增加 |

不修改 ERPNext、Frappe 核心文件，不改变标准 `upload_file`、`download_file`、Project 保存接口的参数与返回值。

## 7. 预计核心代码

以下为后续实现方向，最终代码以开发和测试结果为准。

### 7.1 Project 字段

```python
PROJECT_FILE_FIELDS = [
    {
        "fieldname": "custom_project_files_tab",
        "label": "项目文件",
        "fieldtype": "Tab Break",
        "insert_after": "actual_end_date",
    },
    {
        "fieldname": "custom_project_files_section",
        "label": "项目文件",
        "fieldtype": "Section Break",
        "insert_after": "custom_project_files_tab",
    },
    {
        "fieldname": "custom_project_files",
        "label": "项目文件",
        "fieldtype": "Table",
        "options": "Project File Item",
        "insert_after": "custom_project_files_section",
    },
]
```

`actual_end_date` 是标准“详细信息”页签中紧邻“成本核算”页签之前的字段。以它作为锚点，可让新增页签只包含项目文件表格，不挪动已有“详细信息、成本核算、流程进度、更多信息、关联”。

### 7.2 后端校验

```python
def validate_project_files(doc, method=None):
    if not doc.has_permission("write"):
        frappe.throw(_("没有维护该项目文件的权限。"), frappe.PermissionError)

    for row in doc.get("custom_project_files") or []:
        validate_pdf_file(row.pdf_file)
        ensure_private_project_file(doc, row)
        row.file_name = row.file_name or get_file_name(row.pdf_file)
        row.uploaded_by = row.uploaded_by or frappe.session.user
        row.uploaded_on = row.uploaded_on or frappe.utils.now()
```

校验不能只判断文件名后缀，还应读取对应 `File` 记录，核对 `file_name`、`file_url`、私有属性以及可用的 MIME 信息。文件内容签名可检查 `%PDF-`，用于阻止仅修改扩展名的伪 PDF。

### 7.3 活动时间线日志

```python
def log_project_file_changes(doc, method=None):
    before = get_before_save_rows(doc)
    after = get_current_rows(doc)

    for change in compare_rows(before, after):
        doc.add_comment("Info", build_project_file_message(change))
```

预期日志文本：

```text
张三上传了项目文件：需求说明书.pdf
李四修改了项目文件名称或备注：验收报告.pdf
王五删除了项目文件：旧版方案.pdf
```

日志内容必须转义文件名和备注，防止 HTML 注入。日志在 Project 更新成功后生成；需通过幂等判断避免同一次保存重复写入。

### 7.4 前端限制

```javascript
frappe.ui.form.on("Project File Item", {
    pdf_file(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.pdf_file && !row.pdf_file.toLowerCase().endsWith(".pdf")) {
            frappe.model.set_value(cdt, cdn, "pdf_file", "");
            frappe.throw(__("项目文件仅支持 PDF。"));
        }
    },
});
```

前端校验只改善体验，不作为安全边界。最终有效性始终由后端确认。

## 8. 权限与安全

| 操作 | 权限要求 | 处理方式 |
| --- | --- | --- |
| 查看文件列表 | Project read | 继承项目读取权限 |
| 下载 PDF | Project read + 私有 File 权限 | 使用 Frappe 私有文件接口 |
| 上传 | Project write | Project 保存前后端校验 |
| 修改名称/备注 | Project write | Project 保存权限 + 活动日志 |
| 删除 | Project write | 保存成功后安全清理 + 活动日志 |

额外约束：

- 禁止把项目文件保存为公开文件。
- 禁止外部 URL 作为项目 PDF 值。
- 文件大小沿用站点和 Nginx 现有上传上限，不在本增量中修改全局限制。
- 文件名、备注和日志内容统一转义。
- 后端拒绝非 PDF，即使请求绕过浏览器脚本。
- 不扩大 Project 现有用户权限，不为项目文件单独授予更宽权限。

## 9. 审计口径

本次必须记录：

- 新增文件；
- 删除文件；
- 修改文件名称；
- 修改备注。

每条记录至少包含操作者、动作、文件名和系统时间。Frappe Comment 自带 `owner`、`creation`，活动区可以展示操作者和时间。

本次暂不记录：

- 打开项目文件页签；
- 普通预览；
- 普通下载。

原因是查看、下载频率高，写入 Project 时间线会降低业务日志可读性。若后续有合规审计要求，应新增独立的访问审计 DocType 或日志表，不建议把所有下载记录堆入 Project 活动时间线。

## 10. 受影响模块

| 模块 | 影响 |
| --- | --- |
| Project 详情表单 | 新增“项目文件”页签和文件子表 |
| Project 保存流程 | 增加 PDF、私有属性和元数据校验 |
| Project 活动时间线 | 新增文件操作 Info Comment |
| File 私有文件 | 新增 Project 文件关联和安全删除路径 |
| 权限系统 | 复用 Project read/write，不新增角色 |
| 数据库迁移 | 新增一个子 DocType及三个 Project Custom Field |
| 备份恢复 | 私有 PDF 随现有 private files 备份恢复 |
| 项目导出/打印 | 默认不把 PDF 内容并入现有项目 PDF 导出，仅保留项目文件数据 |

不应受影响：成本核算、流程进度、项目编号、项目开发申请 PDF、列表页、标准右侧附件、其他业务 DocType。

## 11. 关联调整

1. `ensure_schema()` 必须先 reload `Project File Item`，再创建 Project Table 字段，保证新站点迁移顺序稳定。
2. `custom_field_schema.REQUIRED_FIELDS` 增加 Project 文件字段，部署自检能发现漏迁移。
3. Project 的 `doctype_js` 使用数组追加脚本，保留现有成本和进度脚本，不覆盖。
4. Project 的 `doc_events` 在现有列表中追加 handler，不替换项目编号、成本、申请和进度逻辑。
5. 删除行后的物理文件清理必须识别其他引用，不能影响标准附件或其他单据。
6. 现有备份文档已经包含私有附件备份流程，无需新增备份机制，但验收时要加入恢复检查。
7. 若项目复制功能会复制子表，实施时应确认是否清空文件行；默认建议不复制项目文件，避免新项目继承旧项目资料。

## 12. 兼容与发布策略

- 数据库变更均为新增，不删除、不重命名旧字段。
- 现有 Project 记录无需回填，项目文件表默认为空。
- 现有标准附件继续可用，不迁移、不隐藏。
- 不改变现有 API；新逻辑挂在 Project 生命周期事件上。
- 校验函数应只处理 `custom_project_files`，不限制 Project 右侧标准附件的文件类型。
- 若上线后需要回退，可先隐藏新增页签并停止事件处理；已有 File 和子表数据保留，避免破坏性回滚。
- 建议先在测试站点执行 migrate 和回归测试，通过后再部署生产站点。

## 13. 测试与验收

### 13.1 后端自动测试

- 有 Project write 权限可新增、修改、删除文件行。
- 只有 Project read 权限时不能新增、修改或删除。
- 无 Project read 权限不能读取项目文件或下载私有 PDF。
- `.exe`、图片、伪装后缀及非 PDF 内容被拒绝。
- 公有 File 被拒绝或安全转为私有文件。
- 上传人和上传时间由后端填写，前端伪造值无效。
- 每次新增、修改、删除只生成一条对应日志。
- 保存失败不写成功日志、不删除物理文件。
- 删除仍被其他记录引用的文件时不物理删除。
- 原有项目成本、项目进度和开发申请测试全部通过。

### 13.2 页面验收

1. 打开具体项目，可看到“项目文件”页签。
2. 可连续上传多个 PDF，列表稳定显示名称、上传人、时间和备注。
3. 上传非 PDF 时前端立即提示，绕过前端后后端仍拒绝。
4. 保存后刷新页面，文件仍存在且可打开。
5. 只读用户能查看和下载，但不能新增、编辑或删除。
6. 编辑用户上传、改名、改备注、删除后，底部“活动”显示对应记录。
7. 关闭或完成的项目只要仍可编辑，就仍能维护文件。
8. 复制项目时不带入旧项目文件。
9. 标准右侧附件和既有项目页签行为不变。

## 14. 预期效果

实施后，用户进入某个具体项目即可在独立“项目文件”页签集中维护多个 PDF，无需离开项目或进入公共文件列表。文件与项目明确绑定，不做额外分类，界面保持简单。

有读取权限的用户可以查看和下载；有编辑权限的用户可以维护。所有文件均为私有文件，直接访问仍受项目权限保护。上传、删除、名称或备注修改会像现有“创建了本单据、修订了本单据”一样出现在项目底部活动时间线，并明确显示操作人与文件名。

该方案只新增子 DocType、Project 自定义字段、独立校验与脚本分支，不改 ERPNext 标准代码，不改变老接口，不触碰现有成本核算和流程进度主链路，适合按小增量方式发布和回退。

## 15. 本期不做

- 文件分类、标签、版本树和审批流程。
- Word、Excel、图片、压缩包等非 PDF 文件。
- 在项目列表直接查看或下载文件。
- 全量记录预览和下载行为。
- 将历史标准附件自动迁移到项目文件子表。
- 改造全局上传大小限制。
