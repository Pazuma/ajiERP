# 中国财务发票识别与导入方案

## 1. 目标与边界

在“中国财务 -> 发票管理 -> 中国税务发票”中增加“识别发票”入口。财务人员上传或选择发票电子原件后，系统识别发票头和明细，生成一张待人工核对的 `China Tax Invoice` 草稿；核对无误后，仍由用户按现有流程保存、提交和归档。

首期范围限定为中国增值税发票及数电发票的电子文件：PDF、PNG、JPG、JPEG、OFD。输出覆盖现有税务发票模型已支持的字段：发票类型、代码/号码、开票日期、购销双方名称及税号、金额/税额/价税合计、税率和货物或服务明细。

本期不包含：

- 自动提交、自动入账、自动抵扣或自动税务验真；识别不是税务查验结果。
- 火车票、机票、通行费、定额票等非增值税发票版式。
- 以 OCR 结果自动新建客户、供应商、物料或税务科目。
- 对已提交的 `China Tax Invoice` 回写识别结果。
- 改造现有 `china_finance.services.tax_invoice.import_invoices` JSON 导入接口。

## 2. 现状与问题

现有 `China Tax Invoice` 已有完整的税务发票字段、发票明细、附件 `original_file`、文件哈希 `file_hash` 和按“进销项 + 销方税号 + 发票号码”生成的唯一键 `invoice_key`。提交时会归档电子原件；已有 `import_invoices(records)` 可接收外部整理好的 JSON 数组并按唯一键跳过重复记录。

但目前文件附件不能直接转为结构化数据。财务人员需要先阅读原件，再逐项录入发票头和明细，录入量大时容易出现号码、税号、金额、税率和明细遗漏。直接把识别结果调用既有 JSON 导入接口也不合适：该接口会立即创建记录，无法提供“原件、识别结果、校对差异、重复预警”这一人工确认环节。

## 3. 方案概览

采用“独立识别任务 + 草稿转换”的新增分支，保持现有发票手工录入、JSON 导入、提交、归档和报表链路不变。

1. 用户在税务发票列表点击“识别发票”，选择公司、进销项和一个文件。
2. 前端上传文件后创建 `China Tax Invoice Recognition`（中国发票识别任务）草稿，仅保存文件引用、上下文和任务状态。
3. 用户点击“开始识别”；后端校验文件类型和权限，计算文件 SHA-256 并将任务投递到后台队列。
4. 识别服务按可配置 Provider 调用适配器，适配器将厂商响应标准化为内部识别结果；任务保存原始响应摘要、置信度、警告和结构化结果。
5. 后端预检：必填字段、金额勾稽、文件哈希重复、发票唯一键重复。重复仅预警，不能覆盖已有发票。
6. 用户查看结果、低置信字段和预检提示后点击“生成税务发票草稿”。
7. 后端复用新增的映射与校验函数创建未提交 `China Tax Invoice`，写入 `original_file`，预填 `source_system = Invoice Recognition` 和识别任务 ID；随后在现有结构化税务发票表单中完成修正和核对。
8. 用户沿用现有保存、提交、抵扣、分摊、归档流程。提交后的附件归档、唯一键约束和金额校验继续由原有代码执行。

调用链路：

```text
China Tax Invoice List / Recognition Form
  -> 上传 File
  -> China Tax Invoice Recognition（草稿任务）
  -> recognize_invoice(name) [权限、文件、幂等、enqueue]
  -> run_invoice_recognition(name) [后台任务]
  -> InvoiceRecognitionProviderAdapter（新增接口）
  -> 标准化结果 + 金额/重复预检
  -> 人工核对
  -> create_tax_invoice_draft_from_recognition(name)
  -> China Tax Invoice（未提交）
  -> 既有 validate / on_submit / archive / tax reports
```

## 4. 拟修改与新增文件

以下为实施时预计的最小文件集合。实际实施后另建“实施沉淀”文档，逐项记录最终文件、函数签名、迁移和验证结果。

| 文件 | 变更类型 | 计划内容 |
| --- | --- | --- |
| `china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.json` | 新增 | 识别任务 DocType：公司、方向、原始文件、状态、Provider、请求/响应摘要、识别结果 JSON、置信度、警告、生成的税务发票链接和失败信息。 |
| `china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.py` | 新增 | 任务状态迁移、文件与公司校验、权限检查及只允许从完成状态生成草稿的领域校验。 |
| `china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.js` | 新增 | “开始识别”“生成税务发票草稿”“重新识别”按钮；展示状态、警告和待核对结果，不在浏览器中处理密钥或直接调用厂商接口。字段修正留在现有税务发票草稿表单中完成。 |
| `china_finance/china_finance/services/invoice_recognition.py` | 新增 | 白名单入口、后台任务、幂等锁、文件格式校验、结果标准化、金额勾稽、重复预检、由识别结果创建税务发票草稿。 |
| `china_finance/china_finance/services/invoice_recognition_provider.py` | 新增 | Provider 抽象和默认禁用适配器。后续接入 OCR/数电票解析厂商时仅新增适配器，不改变任务或税务发票接口。 |
| `china_finance/china_finance/china_finance/doctype/china_finance_settings/china_finance_settings.json` | 小改 | 新增受权限控制的识别开关、Provider、超时、最大文件大小、密钥引用字段；密钥采用 Password 字段或站点配置引用，不记录明文。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.json` | 小改 | 仅新增只读链接 `recognition_task`（识别任务），用于审计追溯；不改变已有字段含义和必填规则。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.py` | 小改 | 在现有 `before_validate` 中保留既有唯一键和哈希逻辑；最多增加识别任务一致性校验，不改变提交、红冲、抵扣和归档行为。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice_list.js` | 小改 | 在列表 Actions 菜单新增“识别发票”，创建任务后跳转识别表单；保留现有新建与导入入口。 |
| `china_finance/china_finance/setup/install.py` | 小改 | 将识别任务加入“发票管理”导航与标准字段审计；不修改现有导航对象和既有权限。 |
| `china_finance/china_finance/tests/test_invoice_recognition.py` | 新增 | 覆盖格式、权限、状态、字段映射、金额勾稽、同文件重复、同发票重复、草稿创建和失败重试。 |
| `docs/08-reference/39-china-tax-invoice-recognition-implementation.md` | 新增（实施后） | 记录最终代码、调用链路、迁移步骤、兼容性、验证结果和已知限制。 |

如界面需要更直观的低置信度高亮，可额外新增 `public/js/china_tax_invoice_recognition.js` 与 `public/css/china_tax_invoice_recognition.css`；仅通过该新 DocType 的表单脚本加载，不向全局 Desk 注入脚本。

## 5. 数据模型和字段映射

### 5.1 识别任务的核心字段

`China Tax Invoice Recognition` 不承载正式税务事实，只承载识别过程与可追溯证据。

| 字段 | 用途 |
| --- | --- |
| `company`、`direction` | 用户输入的业务上下文；方向默认可由任务带入，不以 OCR 猜测覆盖。 |
| `source_file`、`file_hash` | 被识别电子原件与 SHA-256；用于同文件幂等控制。 |
| `status` | Draft、Queued、Processing、Completed、Needs Review、Failed、Converted。 |
| `provider`、`provider_request_id` | 所用适配器与厂商请求追溯信息。 |
| `recognized_data` | 标准化 JSON；包含发票头、明细、字段置信度和识别原值。 |
| `warnings`、`validation_summary` | 格式、缺失字段、金额不平、低置信、重复风险等可读提示。 |
| `tax_invoice` | 生成后关联的 `China Tax Invoice`，防止重复转换。 |

任务状态写入采用单向控制：`Draft -> Queued -> Processing -> Completed/Needs Review/Failed -> Converted`。重试只允许 Failed 或 Needs Review 重新发起；Converted 不允许再创建第二张税务发票。

### 5.2 到现有税务发票的映射

| 识别标准字段 | 写入目标 | 处理规则 |
| --- | --- | --- |
| `invoice_type` | `China Tax Invoice.invoice_type` | 仅映射系统已有选项；无法映射则填“其他”并加警告。 |
| `invoice_number`、`invoice_code`、`invoice_date` | 同名字段 | 无号码、日期或销方税号时禁止生成草稿。 |
| `seller_*`、`buyer_*` | 同名字段 | 去除空白并保留原识别值供核对。 |
| `currency` | `currency` | 首期仅支持 CNY；其他币种提示人工处理。 |
| `net_amount`、`tax_amount`、`gross_amount` | 发票明细汇总后由现有 `validate()` 计算 | 不直接信任头部总计，按已确认明细计算。 |
| `items[]` | `China Tax Invoice Item` | 映射品名、规格、单位、数量、单价、未税金额、税率、税额、分类编码。 |
| `source_file` | `original_file` | 原件只引用同一个 File，不复制文件。 |
| 固定来源 | `source_system = Invoice Recognition`、`source_id = 识别任务名` | 新增来源分支，不影响 Manual 和现有外部 JSON 导入。 |
| `recognition_task` | 新增只读 Link | 从正式发票反查识别过程。 |

识别任务只自动预填草稿。`China Tax Invoice.validate()` 仍计算金额、构建 `invoice_key`，并在唯一键冲突时拒绝保存；因此不能以识别结果绕过已有防重与金额规则。

## 6. Provider 与安全设计

识别能力采用接口而非写死某一家服务：

```python
class InvoiceRecognitionProviderAdapter:
    def recognize(self, file_url, context) -> dict:
        """返回标准化发票数据、字段置信度、警告和可脱敏的请求追踪号。"""
```

首期提供 `DisabledProvider`：未配置或未启用时明确返回“尚未配置发票识别服务”，不尝试将文件发送到外部。选定供应商后，新增独立适配器（例如 `xxx_invoice_recognition_provider.py`），实现鉴权、上传、轮询或回调、响应标准化；任务服务、界面和税务发票模型无需改动。

外部调用必须满足：

- Provider 密钥仅存入 Frappe Password 字段或站点密钥配置；日志、任务 JSON、异常和浏览器响应均不得记录密钥、完整 Authorization 头或未脱敏厂商响应。
- 仅允许 `China Tax User`、`Accounts Manager`、`System Manager` 发起识别；查看任务遵循 DocType 权限，生成草稿还要校验 `China Tax Invoice` 的 create 权限。
- 文件扩展名、MIME、实际文件头、大小和页数均在服务端校验；拒绝可执行文件和超限文件。
- 原件通过受控 File URL 读取；不接受任意 URL 作为识别来源。
- 调用采用后台队列、有限超时和可审计错误码；失败不影响原文件，不产生正式发票。

## 7. 重复、校验与人工确认

识别完成后先完成以下预检，并在界面清晰标出：

| 检查 | 结果 | 系统动作 |
| --- | --- | --- |
| 同一文件 SHA-256 已有识别任务 | 文件重复 | 复用/跳转已有任务，不重复调用 Provider。 |
| 已有相同 `invoice_key` 的税务发票 | 发票重复风险 | 阻止生成草稿，展示已存在单据链接。 |
| 缺发票号码、开票日期、销方名称或销方税号 | 信息不完整 | 状态为 Needs Review，提示重新识别或手工新建，禁止生成缺少必填信息的草稿。 |
| 明细未税金额 + 税额与价税合计差额超过 0.01 | 金额不平 | 状态为 Needs Review；不可自动提交。 |
| 税率、发票类型不在本系统选项中 | 枚举无法映射 | 保留原值与警告，要求人工选择/修正。 |
| 某关键字段置信度低于配置阈值 | 识别可信度不足 | 高亮字段并要求人工确认，不直接视为失败。 |

“生成税务发票草稿”应采用同一事务内的锁和二次唯一键检查，避免两个用户同时将同一任务或同一张发票转换。草稿创建成功后立即回写 `tax_invoice` 和 `Converted` 状态；若创建失败，任务保留可复核状态和错误摘要。

## 8. 受影响模块

| 模块 | 影响 | 兼容策略 |
| --- | --- | --- |
| 发票管理 / `China Tax Invoice` | 新增识别入口与识别来源追溯 | 手工新建、编辑、提交、红冲、分摊流程不改。 |
| 电子会计档案 | 识别原件在发票提交后继续进入既有归档 | 不新增第二套档案或复制附件。 |
| 进项税抵扣 | 识别生成的进项票与手工票一样从“未查验/不适用”开始 | 不把 OCR 识别误当作查验或勾选。 |
| 销项开票申请与税务接口 | 不自动关联、不自动反馈开票申请 | 现有开票申请金额和分摊一致性校验保持不变。 |
| 税务报表、对账、业务单据链 | 仅在发票被用户提交后自然纳入 | 草稿识别任务和未提交发票不参与报表。 |
| 设置与权限 | 新增 Provider 配置与识别任务权限 | 默认关闭，未配置不会改变现有操作。 |
| JSON 导入 | 无代码行为变化 | `import_invoices` 保持为外部结构化数据导入通道。 |

## 9. 预期效果与验收

上线后，财务人员可从发票管理上传原件，获得一张带原件引用、明细、金额校验和重复提示的未提交税务发票草稿。人工在既有结构化发票表单中核对、修正并提交；不会因为 OCR 误识别而自动入账、抵扣或影响税表。

验收场景：

1. 上传一张清晰的增值税专票 PDF，识别后可得到发票头、至少一条明细、金额汇总和原件链接；确认后生成未提交税务发票。
2. 上传同一文件两次，系统跳转或复用既有识别任务，Provider 不会重复调用。
3. 上传与已存在税务发票相同销方税号和发票号码的文件，生成草稿被阻止并能打开重复单据。
4. 识别金额和明细合计不一致时，界面显示差异，且不允许自动提交。
5. Provider 未配置、文件格式非法、远端超时和识别字段缺失时，任务显示可理解错误；原文件和既有发票均不受影响。
6. 将识别生成的进项票提交后，验证仍能进入原有抵扣、电子档案和税务报表流程。

## 10. 实施顺序与待确认事项

建议按以下顺序实施：先建立任务模型、文件安全校验、默认禁用 Provider、标准化结果和草稿转换；然后补界面与测试；最后在确认服务商、数据出境策略、成本和验真要求后接入具体 Provider。这样即使外部服务尚未选定，内部流程和接口边界也能先稳定下来。

实施前需业务方确认：

1. 首期是否按本方案只覆盖增值税/数电票，其他票据另立需求。
2. 选择的 OCR/发票解析服务商、密钥保管责任、网络连通性和文件是否允许发送到该服务。
3. 是否需要税局真伪查验。若需要，应作为独立“查验”能力接入，不能与“识别”共用成功状态。
4. 识别任务保留期限、原始厂商响应是否仅保存脱敏摘要，以及低置信度阈值由谁维护。
