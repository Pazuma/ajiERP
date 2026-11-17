# 中国税务发票表单内识别实施沉淀

## 1. 实施结果

已将发票识别入口接入“新建中国税务发票”表单。财务人员在当前表单上传电子原件后，通过“发票操作 -> 识别发票”触发识别，系统将标准化识别结果自动回填发票头和 `China Tax Invoice Item` 明细；用户核对、修正后保存，继续使用原有提交、归档、抵扣和报表流程。

独立的“中国发票识别任务”仍然保留，作为识别过程的审计记录和重复文件复用依据。原有 `create_recognition`、`recognize_invoice`、`run_invoice_recognition`、`create_tax_invoice_draft_from_recognition` 及 JSON 导入接口未修改签名。

## 2. 修改文件

| 文件 | 内容 |
| --- | --- |
| `china_finance/services/invoice_recognition.py` | 新增 `recognize_invoice_for_form(company, direction, source_file)`；复用文件校验、公司设置、Provider、结果标准化、重复发票预检；创建识别任务但不创建正式发票。 |
| `china_finance/public/js/china_tax_invoice_form_recognition.js` | 新增当前发票表单识别按钮、上传检查、接口调用、显式字段映射、明细回填、覆盖确认、警告提示；同时承载原有进项税操作按钮。 |
| `china_finance/hooks.py` | 将表单识别脚本注册到 `China Tax Invoice` 的 `doctype_js`；原有其他单据脚本不受影响。 |
| `china_finance/tests/test_invoice_recognition.py` | 增加标准化默认值测试。 |
| `docs/08-reference/40-china-tax-invoice-inline-recognition-plan.md` | 已补充设置字段和识别内容对应字段。 |
| `docs/08-reference/41-china-tax-invoice-inline-recognition-implementation.md` | 本实施文档。 |

已有的识别任务 DocType、Provider、设置字段、`recognition_task` 追溯字段和发票列表入口继续沿用，不重复创建。

## 3. 使用方法

### 3.1 首次配置

1. 进入 `中国财务 -> 设置 -> 中国财务设置`。
2. 打开对应公司的“发票识别”区域。
3. 开启“启用发票识别”。
4. 选择 `Generic HTTP`，填写识别服务地址、访问密钥、超时和最大文件大小。
5. 保存设置。Provider 为 `Disabled` 时，表单按钮会提示尚未配置服务，不会发送文件。

### 3.2 表单内识别

1. 进入 `中国财务 -> 发票管理 -> 中国税务发票`。
2. 点击右上角“添加中国税务发票”。
3. 先选择公司、进销项，并在“来源与电子原件”上传 PDF、PNG、JPG、JPEG 或 OFD 文件。
4. 点击表单顶部 `发票操作 -> 识别发票`。
5. 等待接口返回；识别完成后，发票类型、号码、代码、开票日期、购销双方、币种、票据状态和明细会自动填入当前表单。
6. 若当前表单已有头字段或明细，系统会先询问是否覆盖；确认后才替换。
7. 查看黄色提示，修正低置信度、缺失或重复风险字段。
8. 保存并按原流程补充业务分摊、开票申请关联或红票关联，然后提交。

## 4. 字段回填对应

| 识别字段 | 当前表单字段 | 说明 |
| --- | --- | --- |
| `invoice_type` | `invoice_type` | 仅写入系统已有发票类型选项。 |
| `invoice_number` / `invoice_code` / `invoice_date` | 同名字段 | 号码参与既有 `invoice_key` 防重复。 |
| `seller_name` / `seller_tax_id` | 同名字段 | 销售方名称和税号；税号参与重复判断。 |
| `buyer_name` / `buyer_tax_id` | 同名字段 | 购买方名称必填，购买方税号可为空。 |
| `currency` / `invoice_status` | 同名字段 | 默认 CNY / 蓝票；异常值提示核对。 |
| `items[]` | `items` 子表 | 显式回填品名、规格、单位、数量、单价、未税金额、税率、税额和分类编码。 |
| 当前上传附件 | `original_file` | 不复制附件；由用户上传的 File 保持不变。 |
| 识别任务编号 | `recognition_task` / `source_id` | 保存审计追溯关系；`source_system` 固定为 `Invoice Recognition`。 |

价税合计、未税金额和税额最终仍由现有后端 `ChinaTaxInvoice.validate()` 按明细重新计算。识别不自动填充查验状态、抵扣状态、红票关联、业务分摊或会计科目。

## 5. 调用链路

```text
China Tax Invoice 新建表单
  -> original_file 上传
  -> 发票操作 / 识别发票
  -> recognize_invoice_for_form()
  -> _get_settings() + _validate_file()
  -> get_provider().recognize()
  -> normalize_recognition_result()
  -> validate_recognized_data() + find_duplicate_invoice()
  -> 创建 China Tax Invoice Recognition 审计任务
  -> 返回 data / warnings / duplicate_invoice
  -> 前端显式回填 frm.doc
  -> 用户核对/修正
  -> ChinaTaxInvoice.validate()
  -> 既有 submit / archive / deduction / reports
```

## 6. 兼容与安全

- 表单识别只对未提交的新建单据显示；已提交发票不允许回填。
- 当前表单已有值时必须二次确认，避免静默覆盖手工输入。
- 同一附件优先复用已有识别任务结果；已有相同发票唯一键时仅提示风险，正式保存仍受后端唯一键控制。
- 所有文件扩展名、文件头、大小和附件归属均由服务端校验。
- Provider 密钥不进入浏览器脚本、识别结果 JSON 或普通日志。
- 识别成功不等于税务查验通过，不触发自动入账、抵扣或提交。

## 7. 验证记录

- Python 模块已通过 `python3 -m compileall`。
- DocType JSON 已通过 `python3 -m json.tool`。
- `git diff --check` 已通过。
- 当前环境无法执行 Frappe 浏览器端和站点运行时测试；部署后需重新构建资源并清理缓存：

```bash
bench --site <站点名> migrate
bench --site <站点名> clear-cache
bench build --app china_finance
```

