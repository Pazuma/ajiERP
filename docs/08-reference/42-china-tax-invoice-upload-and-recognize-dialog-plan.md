# 中国税务发票“上传并识别”一体化弹窗方案

## 1. 需求目标

将当前“先到表单底部上传电子原件，再回到顶部点击识别”的操作，调整为表单顶部的一体化入口：

```text
新建中国税务发票
  -> 发票操作 -> 识别发票
  -> 弹窗选择/上传发票文件
  -> 确认识别
  -> 自动识别并回填当前表单
  -> 财务核对
  -> 保存、提交
```

用户不需要在识别前保存空白税务发票，因此不会再因为发票号码、日期、购销双方和明细尚未识别而触发“必填字段信息缺失”。

## 2. 交互设计

### 2.1 入口位置

入口继续放在新建 `China Tax Invoice` 表单顶部：

`发票操作 -> 识别发票`

按钮只在 `docstatus = 0` 时显示。已提交或已取消发票不允许重新识别覆盖。

### 2.2 上传识别弹窗

点击“识别发票”后打开一个 Frappe Dialog，字段如下：

| 标签 | 字段名 | 类型 | 默认/规则 |
| --- | --- | --- | --- |
| 公司 | `company` | Link / Company | 默认取当前表单公司；必填。 |
| 进销项 | `direction` | Select | 默认取当前表单进销项；必填。 |
| 发票文件 | `source_file` | Attach | 必填；支持 PDF、PNG、JPG、JPEG、OFD。 |

弹窗主按钮名称为“上传并识别”。用户点击后：

1. 校验公司、进销项和附件均已填写。
2. 等待 Frappe Attach 控件完成文件上传并得到 `file_url`。
3. 调用现有表单识别接口 `recognize_invoice_for_form()`。
4. 请求期间禁用弹窗按钮并显示“正在识别发票”。
5. 成功后关闭弹窗，将识别结果自动回填当前发票表单。
6. 失败时保留弹窗和已上传文件，显示服务端错误，允许用户直接重试。

如果表单原来已上传 `original_file`，打开弹窗时将其作为默认文件；用户可以继续使用或重新上传。识别成功后，弹窗中的 `source_file` 回填到当前表单 `original_file`。

### 2.3 覆盖保护

识别前检查当前表单：

- 如果只有系统默认值（编号规则、公司、进销项、默认类型、蓝票、CNY），直接回填，不弹出无意义的覆盖确认。
- 如果存在用户手工填写的发票号码、日期、购销双方字段或有效明细，点击“上传并识别”后提示“识别结果将覆盖当前票面信息和明细”。
- 用户取消时不调用 Provider，不修改当前表单。
- 用户确认时只覆盖文档规定的识别字段，不覆盖业务分摊、开票申请、原蓝票、贷项发票、备注或税务状态。

## 3. 自动回填内容

识别成功后自动填入：

| 分类 | 表单字段 |
| --- | --- |
| 发票基本信息 | `invoice_type`、`invoice_number`、`invoice_code`、`invoice_date`、`invoice_status` |
| 购销双方 | `seller_name`、`seller_tax_id`、`buyer_name`、`buyer_tax_id` |
| 金额基础 | `currency` |
| 发票明细 | `items[].item_name`、`specification`、`unit`、`quantity`、`unit_price`、`net_amount`、`tax_rate`、`tax_amount`、`goods_service_code` |
| 原件与来源 | `original_file`、`recognition_task`、`source_system`、`source_id` |

`net_amount`、`tax_amount`、`gross_amount` 发票头合计仍由已有 `ChinaTaxInvoice.validate()` 根据明细重新计算，不将 OCR 总计直接作为最终账务数据。

不自动填入查验、抵扣、红冲关系、业务分摊和会计处理字段。

## 4. 文件上传与未保存表单

新建税务发票尚未保存时，Attach 控件产生的 `File` 可能暂时未绑定正式单据。后端继续允许识别以下附件：

- 未绑定附件；
- 已绑定 `China Tax Invoice` 的附件；
- 已绑定 `China Tax Invoice Recognition` 的附件。

识别成功后将 `file_url` 写入当前表单 `original_file`。用户保存税务发票后，使用 Frappe 标准附件机制建立单据关系；提交时继续由现有归档逻辑计算 SHA-256 并创建电子会计档案。

若识别失败，不创建空白税务发票；上传文件保留在 Frappe File 中供重试。是否定期清理长期未绑定文件沿用系统既有 File 清理策略，本次不新增删除逻辑。

## 5. 调用链路

```text
China Tax Invoice 新建表单
  -> 点击 发票操作 / 识别发票
  -> frappe.ui.Dialog（公司、进销项、发票文件）
  -> Attach 上传至 Frappe File
  -> 点击 上传并识别
  -> recognize_invoice_for_form(company, direction, source_file)
  -> _get_settings()
  -> _validate_file()
  -> get_provider().recognize()
  -> normalize_recognition_result()
  -> validate_recognized_data()
  -> find_duplicate_invoice()
  -> 创建/复用 China Tax Invoice Recognition 审计任务
  -> 返回 data / warnings / task / file_hash
  -> current frm.set_value(original_file)
  -> 显式回填发票头和 items
  -> 用户核对后保存
  -> 原有 ChinaTaxInvoice.validate / submit / archive
```

## 6. 拟修改代码与文件

| 文件 | 变更类型 | 计划修改 |
| --- | --- | --- |
| `china_finance/public/js/china_tax_invoice_form_recognition.js` | 主要小改 | 将当前“缺附件则提示”的按钮逻辑改为打开上传识别 Dialog；增加 Attach 字段、上传等待、确认按钮、覆盖判断、loading/失败恢复，并将文件回填 `original_file`。 |
| `china_finance/services/invoice_recognition.py` | 小改 | 保留 `recognize_invoice_for_form()` 签名；完善未绑定附件、重复任务复用和错误返回，不要求先保存税务发票。 |
| `china_finance/tests/test_invoice_recognition.py` | 扩展 | 增加未绑定 File、表单同步识别结果、重复文件复用、禁用 Provider、非法文件和不创建空白发票测试。 |
| `china_finance/hooks.py` | 原则上不改 | 继续使用已有 `China Tax Invoice -> china_tax_invoice_form_recognition.js` 注册；仅当构建验证发现路径问题时调整。 |
| `china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.json` | 不改 | 复用已有 `original_file`、`recognition_task`、`source_system` 和 `source_id` 字段。 |
| `china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.py` | 不改或极小校验 | 保留现有必填、金额、唯一键、红冲、分摊和归档规则；识别阶段不触发保存。 |
| `docs/08-reference/43-china-tax-invoice-upload-and-recognize-dialog-implementation.md` | 实施后新增 | 记录最终代码、使用路径、调用链路、验证结果和限制。 |

## 7. 老接口兼容策略

以下接口和流程保持不变：

- `create_recognition()`：独立任务入口继续使用。
- `recognize_invoice()` / `run_invoice_recognition()`：独立任务异步识别继续使用。
- `create_tax_invoice_draft_from_recognition()`：从独立任务生成草稿继续使用。
- `recognize_invoice_for_form()`：保留参数和返回结构，前端只改变调用时机与附件来源。
- `tax_invoice.import_invoices(records)`：JSON 批量导入不变。
- `ChinaTaxInvoice.validate()` / `on_submit()`：保存、提交和归档逻辑不变。

本次优先新增弹窗交互分支，不通过降低必填要求解决问题。发票号码等字段继续保持必填，只是在识别完成并自动填入后再保存。

## 8. 受影响模块

| 模块 | 影响 | 风险控制 |
| --- | --- | --- |
| 中国税务发票表单 | 识别按钮直接包含文件上传 | 仅未提交表单显示，显式字段映射。 |
| Frappe File | 新建表单可先产生未绑定附件 | 使用标准 Attach 控件，不接受服务器任意路径。 |
| 发票识别任务 | 保存识别审计记录 | 复用现有 DocType 和防重逻辑。 |
| Provider | 调用方式不变 | 公司未启用或配置不完整时弹窗保留并显示错误。 |
| 发票保存与提交 | 无接口变化 | 不降低必填规则，不自动保存或提交。 |
| 档案、抵扣、报表 | 无直接变化 | 仅用户正式提交后进入原链路。 |

## 9. 预期效果

- 用户无需滚动到“来源与电子原件”区域提前上传。
- 用户无需为了上传或识别而保存字段不完整的空白发票。
- 一次弹窗完成选择公司、进销项、上传和确认识别。
- 识别完成后附件、票面字段和明细同时出现在当前表单。
- 识别失败时不产生空白税务发票，也不丢失用户已上传文件和手工数据。
- 财务必填、重复控制、金额计算、提交与归档规则全部保留。

## 10. 验收场景

1. 打开全新的税务发票，未填写发票号码等必填项，点击“识别发票”能直接打开上传弹窗，不触发保存校验。
2. 上传 `/home/cst/frappe_docker/悦为智能技术（东莞）有限公司_20260721150445.pdf` 对应的本机文件并确认后，系统调用 Provider 并回填当前表单。
3. 识别成功后 `original_file` 显示上传文件，发票头和所有有效明细自动填入，表单处于“未保存”状态。
4. 当前已有手工业务数据时，系统先确认再覆盖；取消后数据不变。
5. Provider 未配置、超时或返回错误时，弹窗保留文件并显示错误，不创建税务发票。
6. 重复附件或重复发票能显示已有任务/发票提示，不能绕过现有唯一键校验。
7. 用户核对后保存成功；缺少 Provider 未返回的必填字段时，仍由原有校验提示补充。

## 11. 实施注意事项

- `Attach` 上传是异步行为，主按钮必须在取得有效 `file_url` 后才能调用后端。
- 不能通过浏览器直接使用 `/home/cst/...pdf` 服务端路径；用户仍需在上传控件选择本机文件。
- 当前 `Generic HTTP` 只是标准适配器，启用开关不等于已经具备 OCR 能力；必须同时配置可用服务地址和访问密钥。
- 若实际 Provider 返回字段与标准 JSON 不一致，应新增厂商适配器或网关转换，不能在表单脚本中写厂商字段判断。

