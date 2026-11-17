# 中国税务发票表单内识别与自动回填方案

## 1. 目标

将发票识别入口从独立的“识别任务”页面前移到“新建中国税务发票”表单中。财务人员打开新建发票页面后，在表单内上传发票电子原件并点击“识别发票”，系统将识别结果直接回填到当前表单的发票头和发票明细，用户核对后保存、提交。

核心体验：

```text
新建中国税务发票
  -> 上传电子原件
  -> 点击“识别发票”
  -> 当前表单自动填充发票信息和明细
  -> 财务核对/修正
  -> 保存并按原流程提交
```

## 2. 与现有实现的关系

当前系统已经有独立的 `China Tax Invoice Recognition` 识别任务、后台识别服务、Provider 适配器、重复预检和由识别任务生成税务发票草稿的能力。本次只新增“表单内调用和回填分支”，不删除独立任务页面，不改动原有 `create_recognition`、`recognize_invoice`、`run_invoice_recognition` 和 `create_tax_invoice_draft_from_recognition` 接口。

这样保留两种入口：

- **表单内识别（推荐）**：适合财务录入单张发票，识别后直接回填当前新建表单。
- **独立识别任务**：适合批量、异步处理、失败重试和审计追踪，原入口继续保留。

## 3. 交互方案

### 3.1 表单布局

在 `China Tax Invoice` 表单的“来源与电子原件”区域增加一个识别操作区，建议字段顺序：

1. 电子原件 `original_file`（现有字段）。
2. 识别状态（新增只读前端状态，不作为正式税务事实）。
3. “识别发票”按钮。
4. “清除识别回填”按钮（仅清除本次未保存的自动填充值，不删除附件）。
5. 识别提示：低置信度、重复发票、金额差异、无法映射字段。

不新增复杂弹窗。识别进度和结果提示直接显示在当前表单顶部或来源区域，避免财务人员在多个页面之间切换。

### 3.2 具体操作

1. 用户点击“添加中国税务发票”进入新建表单。
2. 选择公司和进销项，上传 PDF、PNG、JPG、JPEG 或 OFD 原件。
3. 点击“识别发票”。前端调用新增的表单内识别接口。
4. 后端复用现有文件安全校验、文件哈希和 Provider 识别逻辑；识别成功后返回标准化结果及警告。
5. 前端将结果写入当前 `frm.doc`：发票类型、号码、代码、日期、购销双方、币种、票据状态和 `items` 明细全部自动填充。
6. 前端提示“识别结果仅用于预填，请核对后保存”，并对有警告或低置信度的字段加醒目标记。
7. 用户修正字段后点击“保存”。系统走现有 `ChinaTaxInvoice.validate()`，重新计算金额、生成 `invoice_key`、校验红票/开票申请/分摊和文件哈希。
8. 用户按现有流程提交。提交后继续执行原有电子档案归档、进项抵扣和税务报表链路。

## 4. 后端接口设计

新增一个表单专用白名单接口，不改变现有接口：

```python
@frappe.whitelist()
def recognize_invoice_for_form(company, direction, source_file, current_invoice_number=None):
    """识别附件并返回可直接回填 China Tax Invoice 的标准化数据。"""
```

接口职责：

- 复用现有 `_validate_file()` 校验扩展名、文件头、大小和附件归属。
- 复用 `_get_settings()`、`get_provider()` 和 `normalize_recognition_result()`。
- 复用 `validate_recognized_data()` 做必填字段、类型、明细和币种预检。
- 返回 `recognized_data`、`warnings`、`duplicate_invoice`、`file_hash`、`provider_request_id`。
- 不创建正式 `China Tax Invoice`，不提交、不入账、不抵扣。
- 当用户点击保存时，将 `recognition_task` 或识别来源信息写回当前表单，便于追溯。

推荐返回结构：

```json
{
  "data": {
    "invoice_type": "增值税专用发票",
    "invoice_number": "12345678",
    "invoice_code": "",
    "invoice_date": "2026-09-04",
    "seller_name": "销售方名称",
    "seller_tax_id": "税号",
    "buyer_name": "购买方名称",
    "buyer_tax_id": "购买方税号",
    "currency": "CNY",
    "invoice_status": "蓝票",
    "items": []
  },
  "warnings": [],
  "duplicate_invoice": null,
  "file_hash": "sha256",
  "provider_request_id": "request-id"
}
```

如果需要完整异步体验，接口可先创建 `China Tax Invoice Recognition` 任务，再轮询任务状态；但表单回填必须只在任务完成或待核对状态下执行，不能把队列中的半成品写入表单。

## 5. 前端回填规则

新增 `China Tax Invoice` 表单脚本分支，建议文件：

`china_finance/public/js/china_tax_invoice_form_recognition.js`

回填采用显式字段映射，不使用整对象覆盖，避免覆盖用户已经录入的非识别字段：

| 识别字段 | 当前表单字段 | 规则 |
| --- | --- | --- |
| `invoice_type` | `invoice_type` | 仅回填系统已有选项，无法映射则保留空值并提示。 |
| `invoice_number`、`invoice_code`、`invoice_date` | 同名字段 | 识别值优先写入未保存的新单据；已有值被覆盖前必须二次确认。 |
| `seller_name`、`seller_tax_id`、`buyer_name`、`buyer_tax_id` | 同名字段 | 去除首尾空白，保留原识别文本。 |
| `currency`、`invoice_status` | 同名字段 | 仅写入允许选项；异常值转为待核对。 |
| `items[]` | `items` 子表 | 清空当前未保存明细后批量添加；如果已有手工明细，先弹出确认。 |
| `source_file` | `original_file` | 使用当前表单已上传文件，不重复复制附件。 |
| 识别任务名 | `recognition_task`、`source_id` | 仅在任务已创建时写入，保留追溯关系。 |

金额字段不直接写入 `net_amount`、`tax_amount`、`gross_amount` 总计作为最终事实；明细回填后由现有表单计算和后端 `validate()` 再次计算，减少头部金额与明细金额不一致的风险。

## 6. 修改代码与文件

| 文件 | 变更类型 | 内容 |
| --- | --- | --- |
| `china_finance/services/invoice_recognition.py` | 小增量 | 新增 `recognize_invoice_for_form()`，复用现有 Provider、文件校验、标准化和预检函数；不改变原有接口签名。 |
| `china_finance/public/js/china_tax_invoice_form_recognition.js` | 新增 | 在新建 `China Tax Invoice` 表单添加“识别发票”“清除识别回填”按钮、上传校验、接口调用、字段映射、明细回填和警告展示。 |
| `china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.js` | 小改 | 保留现有进项抵扣按钮，增加表单内识别脚本的调用入口或状态提示；不改提交流程。 |
| `china_finance/hooks.py` | 小改 | 将表单识别脚本以数组方式追加到 `China Tax Invoice` 的 `doctype_js`，保留已有脚本。 |
| `china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.json` | 小改 | 保留现有 `original_file` 和 `recognition_task`；如需要显示状态，可新增只读识别摘要字段，不改变必填规则。 |
| `china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.py` | 小改 | 继续执行现有唯一键、金额、红票、开票申请和归档校验；仅补充表单回填来源与识别任务一致性校验。 |
| `china_finance/tests/test_invoice_recognition.py` | 扩展 | 增加表单接口返回结构、公司/方向权限、重复发票、已有表单值保护和结果标准化测试。 |
| `docs/08-reference/41-china-tax-invoice-inline-recognition-implementation.md` | 实施后新增 | 记录最终文件、使用步骤、字段回填、调用链路、测试和已知限制。 |

## 6.1 中国财务设置字段

设置位置：`中国财务 -> 设置 -> 中国财务设置 -> 发票识别`。以下字段按公司分别保存，只有“启用发票识别”打开后，表单才允许调用外部识别服务。

| 页面标签 | 字段名 | 类型 | 默认值/选项 | 作用 |
| --- | --- | --- | --- | --- |
| 启用发票识别 | `invoice_recognition_enabled` | Check | 关闭 | 控制当前公司是否允许发起识别；关闭时不发送文件。 |
| 发票识别服务商 | `invoice_recognition_provider` | Select | `Disabled` / `Generic HTTP` | 选择默认禁用或通用 HTTP 适配器；后续厂商以新增适配器方式接入。 |
| 识别服务地址 | `invoice_recognition_endpoint` | Data/URL | 空 | `Generic HTTP` 服务的 POST 地址；仅服务端调用。 |
| 识别服务访问密钥 | `invoice_recognition_api_key` | Password | 空 | 服务端鉴权密钥；不在前端、日志或识别结果中回显。 |
| 识别超时（秒） | `invoice_recognition_timeout` | Int | 60 | 单次 Provider 请求的超时时间，避免页面长时间等待。 |
| 单文件最大大小（MB） | `invoice_recognition_max_file_size_mb` | Int | 10 | 服务端限制 PDF/图片/OFD 文件大小。 |

设置约束：

- `invoice_recognition_enabled = 0` 时，服务商、地址和密钥只作为配置保留，不会调用外部接口。
- 选择 `Generic HTTP` 时，必须填写服务地址和访问密钥；未填写则在识别时明确提示配置不完整。
- 密钥必须使用 Frappe Password 字段或站点密钥引用，不允许写入代码仓库、前端脚本、任务 JSON 或普通日志。
- 单文件大小必须为正整数；建议生产环境根据 Provider 限制设置为 5-20 MB。

## 6.2 识别结果与税务发票字段对应

识别服务返回的标准化 `data` 对象映射到当前 `China Tax Invoice` 表单。字段回填只发生在未提交的新建单据中；正式金额仍由明细和后端 `validate()` 重新计算。

### 发票头字段

| 识别内容 | 标准 JSON 字段 | 税务发票字段 | 表单标签 | 回填/校验规则 |
| --- | --- | --- | --- | --- |
| 发票类型 | `invoice_type` | `invoice_type` | 发票类型 | 只能写入系统已有六个选项；无法匹配时留空并提示人工选择。 |
| 发票号码 | `invoice_number` | `invoice_number` | 发票号码 | 必填；参与 `invoice_key` 防重复。 |
| 发票代码 | `invoice_code` | `invoice_code` | 发票代码 | 可选；数电票可能为空。 |
| 开票日期 | `invoice_date` | `invoice_date` | 开票日期 | 必须为有效日期；识别失败时禁止生成草稿。 |
| 进销项 | 表单上下文 `direction` | `direction` | 进销项 | 使用用户在表单中选择的值，不由 OCR 覆盖。 |
| 票据状态 | `invoice_status` | `invoice_status` | 票据状态 | 仅允许“蓝票/红票/作废”；红票仍需手工关联原蓝票。 |
| 公司 | 表单上下文 `company` | `company` | 公司 | 使用用户选择的公司，不由 OCR 推断。 |
| 币种 | `currency` | `currency` | 币种 | 首期默认/支持 CNY；其他币种显示待核对提示。 |

### 购销双方字段

| 识别内容 | 标准 JSON 字段 | 税务发票字段 | 表单标签 | 回填/校验规则 |
| --- | --- | --- | --- | --- |
| 销售方名称 | `seller_name` | `seller_name` | 销售方名称 | 必填，保留识别原文并去除首尾空格。 |
| 销售方税号 | `seller_tax_id` | `seller_tax_id` | 销售方税号 | 必填，参与 `invoice_key`；统一转为大写比较。 |
| 购买方名称 | `buyer_name` | `buyer_name` | 购买方名称 | 必填；识别为空时进入 `Needs Review`。 |
| 购买方税号 | `buyer_tax_id` | `buyer_tax_id` | 购买方税号 | 可选，识别到则回填；不强制覆盖手工值。 |

### 发票明细字段

| 识别内容 | 标准 JSON 字段 | 子表字段（`China Tax Invoice Item`） | 表单标签 | 回填/校验规则 |
| --- | --- | --- | --- | --- |
| 货物或服务名称 | `items[].item_name` | `item_name` | 货物或服务名称 | 明细必填；缺失时提示人工补录。 |
| 规格型号 | `items[].specification` | `specification` | 规格型号 | 可选，原样回填。 |
| 单位 | `items[].unit` | `unit` | 单位 | 可选，原样回填。 |
| 数量 | `items[].quantity` | `quantity` | 数量 | 转为数字；无法解析时留空。 |
| 单价 | `items[].unit_price` | `unit_price` | 单价 | 转为数字；不作为最终金额依据。 |
| 不含税金额 | `items[].net_amount` | `net_amount` | 不含税金额 | 保留两位小数；参与后端金额汇总。 |
| 税率 | `items[].tax_rate` | `tax_rate` | 税率 | 转为百分比数值；异常值提示人工核对。 |
| 税额 | `items[].tax_amount` | `tax_amount` | 税额 | 保留两位小数；参与后端金额汇总。 |
| 税收分类编码 | `items[].goods_service_code` | `goods_service_code` | 税收分类编码 | 可选，原样回填。 |
| 价税合计 | 由明细计算 | `gross_amount` | 价税合计 | 不直接信任 OCR 头部值，由现有 `validate()` 按明细重新计算。 |

### 来源与审计字段

| 识别内容 | 写入字段 | 表单标签 | 作用 |
| --- | --- | --- | --- |
| 原始附件 | `original_file` | 电子原件 | 保留用户上传的 PDF/图片/OFD，不复制文件。 |
| 文件 SHA-256 | `file_hash` | SHA-256 | 用于原件完整性和重复识别判断。 |
| 识别任务 | `recognition_task` | 发票识别任务 | 关联 `China Tax Invoice Recognition`，支持审计追溯。 |
| 来源系统 | `source_system` | 来源系统 | 固定写入 `Invoice Recognition`，与手工录入、JSON 导入区分。 |
| 来源记录 ID | `source_id` | 来源记录 ID | 写入识别任务编号。 |
| 服务商请求编号 | `provider_request_id` | 服务商请求编号 | 仅保存在识别任务中，用于排查 Provider 调用，不进入正式发票金额事实。 |

### 不自动回填的字段

以下字段必须由业务或后续税务流程处理，不由 OCR 结果自动决定：

- 查验状态、查验人、查验时间。
- 抵扣状态、勾选人、抵扣期间和不得抵扣原因。
- 红票原蓝票、销售退货或贷项发票关联。
- 业务单据分摊、开票申请关联和会计科目。

这样可以明确区分“识别到的票面信息”和“财务审核、税务查验、会计处理结论”。

## 7. 调用链路

```text
China Tax Invoice 新建表单
  -> original_file 上传
  -> 点击“识别发票”
  -> recognize_invoice_for_form()
  -> _validate_file()
  -> _get_settings() / get_provider()
  -> Provider.recognize()
  -> normalize_recognition_result()
  -> validate_recognized_data() + find_duplicate_invoice()
  -> 返回标准化数据与 warnings
  -> 前端显式字段回填 frm.doc
  -> 用户核对/修正
  -> 现有 save
  -> ChinaTaxInvoice.validate()
  -> 现有 submit / archive / deduction / reports
```

## 8. 受影响模块与兼容策略

| 模块 | 影响 | 兼容策略 |
| --- | --- | --- |
| 中国税务发票新建表单 | 增加识别按钮和自动回填 | 仅对未提交表单生效，已提交单据不显示回填按钮。 |
| 发票识别任务 | 可作为表单识别的后台审计记录 | 原独立任务入口继续可用。 |
| 发票提交与归档 | 无流程变化 | 使用原有 `validate()`、`on_submit()` 和档案归档。 |
| 进项税抵扣 | 无自动抵扣 | 识别成功不等于查验通过。 |
| JSON 导入 | 无变化 | `import_invoices(records)` 保持原样。 |
| Provider 配置 | 无变化 | 继续使用公司级开关和服务商设置；未配置时按钮提示明确错误。 |

## 9. 预期效果

- 财务人员在一张新建发票表单内完成上传、识别、核对和保存，不再往返识别任务页面。
- 发票号码、税号、日期、金额、税率和明细自动填充，减少重复录入。
- 低置信度和重复风险在表单内可见，人工确认仍是保存/提交前的必要步骤。
- 既有发票校验、归档、抵扣、报表和 JSON 导入接口不受影响。
- 识别原件和任务仍可追溯，满足财务审计需要。

## 10. 验收场景

1. 新建税务发票，上传合法 PDF，点击识别后，发票头和明细自动填入当前表单。
2. 当前表单已有手工发票号码或明细时，识别操作先提示确认，不静默覆盖。
3. Provider 未启用时，点击识别显示配置提示，不能产生正式发票。
4. 识别到重复发票时，当前表单显示重复单据链接或警告，保存时仍由原有唯一键规则阻止重复。
5. 识别金额与明细不一致时，显示差异，保存/提交仍由后端重新计算和校验。
6. 识别生成的进项发票提交后，仍能进入原有查验、抵扣批次、档案和报表流程。

## 11. 待确认事项

1. 表单内识别是否必须同步等待结果，还是接受“提交后后台识别、自动回填”的异步体验。建议首期使用按钮触发并等待接口返回，流程更直观。
2. 已有手工录入内容被识别结果覆盖时，采用“整张明细替换”还是“仅填空字段”。建议：头字段覆盖需确认，明细有内容时需确认后替换。
3. 是否需要在表单中直接显示原件预览。建议首期复用 Frappe 附件预览，不新增 PDF/OFD 阅读器。
4. 是否允许识别红票。建议首期允许识别但仍要求手工关联原蓝票和贷项发票，不能自动完成红冲关联。
