# 中国财务发票识别与导入实施沉淀

## 1. 交付结果

已在中国财务的“发票管理”中增加发票识别任务。用户可以上传 PDF、PNG、JPG、JPEG 或 OFD 格式的增值税/数电票原件，调用已配置的识别服务，查看识别结果和重复提示，并生成一张未提交的 `China Tax Invoice` 草稿。

功能坚持“识别辅助录入，不替代财务审核”的原则：不会自动提交、入账、抵扣、验真或覆盖既有发票。财务人员必须在生成的税务发票草稿中核对并修正数据，再沿用原有提交流程。

## 2. 实际修改文件

| 文件 | 实施内容 |
| --- | --- |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.json` | 新增“中国发票识别任务”DocType，保存公司、进销项、原件、哈希、状态、服务商、识别结果、提示、错误与生成的税务发票。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.py` | 新增任务基础校验：原件 SHA-256 与任务/发票关联状态一致性。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.js` | 新增“开始识别”“生成税务发票草稿”按钮，并提示识别结果仅用于预填。 |
| `china_finance/china_finance/services/invoice_recognition.py` | 新增任务创建、异步识别、文件安全校验、结果规范化、缺失字段/重复预检和草稿创建服务。 |
| `china_finance/china_finance/services/invoice_recognition_provider.py` | 新增 Provider 抽象，实现默认禁用 Provider 及通用 HTTP Provider。 |
| `china_finance/china_finance/china_finance/doctype/china_finance_settings/china_finance_settings.json` | 为每家公司新增发票识别开关、服务商、地址、加密访问密钥、超时与文件大小配置。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.json` | 新增只读 `recognition_task` 链接，支持从正式发票追溯识别任务。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice.py` | 增加识别任务与税务发票公司、进销项和来源一致性校验。 |
| `china_finance/china_finance/china_finance/doctype/china_tax_invoice/china_tax_invoice_list.js` | 在税务发票列表 Actions 菜单增加“识别发票”。 |
| `china_finance/public/js/china_tax_invoice_list.js` | 通过 `doctype_list_js` 和全局 `app_include_js` 双重资源路径加载税务发票列表入口；在列表顶部“发票操作”菜单提供直接可见的“识别发票”按钮，保留抵扣批次操作。 |
| `china_finance/china_finance/setup/install.py` | 将识别任务加入发票管理导航及部署元数据检查。 |
| `china_finance/china_finance/tests/test_invoice_recognition.py` | 新增结果标准化和基础校验的单元测试。 |

## 3. 使用路径

### 3.1 管理员配置识别服务

1. 进入：`中国财务 -> 设置 -> 中国财务设置`。
2. 打开目标公司的设置记录，在“发票识别”区域启用“启用发票识别”。
3. 选择服务商：
   - `Disabled`：默认值，不能发起外部识别，适合尚未完成服务商选型时保持功能关闭。
   - `Generic HTTP`：对接符合本实施 JSON 合同的内部网关或第三方服务。
4. 选择 `Generic HTTP` 后填写“识别服务地址”“识别服务访问密钥”“识别超时（秒）”和“单文件最大大小（MB）”，保存。

访问密钥是 Password 字段，界面和任务日志不会回显。启用功能即表示允许将用户选择的发票原件发送到已配置的识别服务；应先完成服务商、数据安全和网络连通性确认。

### 3.2 财务人员识别并导入发票

1. 进入：`中国财务 -> 发票管理 -> 中国税务发票`。
2. 在列表右上角打开 `Actions -> 识别发票`。
3. 选择公司、进销项和发票电子原件后确认。支持 PDF、PNG、JPG、JPEG、OFD；文件大小受公司设置限制。
4. 系统跳转至“中国发票识别任务”，点击“开始识别”。状态会依次显示为 `Queued`、`Processing`，完成后显示 `Completed` 或 `Needs Review`。
5. 查看“识别结果（JSON）”“校验摘要”和“待核对提示”。其中 `Needs Review` 代表缺字段、无法映射类型、未识别到明细或发现重复等，需要格外核对。
6. 点击“生成税务发票草稿”。系统会创建并打开一张未提交的“中国税务发票”。
7. 在草稿中核对发票号码、开票日期、购销双方税号、金额、税率和每条明细，按原有流程补充业务分摊、关联单据后保存并提交。

提交后的电子原件仍由已有 `China Tax Invoice.on_submit()` 归档；进项票仍从“未查验/不适用”开始，必须通过既有抵扣流程处理。

## 4. 通用 HTTP Provider 合同

`Generic HTTP` 会向“识别服务地址”发起 `POST` 请求，使用 `Authorization: Bearer <访问密钥>`。请求体为：

```json
{
  "company": "公司名称",
  "direction": "进项",
  "file_name": "invoice.pdf",
  "file_base64": "..."
}
```

服务应返回 JSON。可将发票字段直接放在根对象，也可放在 `data` 中；推荐结构如下：

```json
{
  "request_id": "provider-request-id",
  "data": {
    "invoice_type": "增值税专用发票",
    "invoice_number": "12345678",
    "invoice_code": "",
    "invoice_date": "2026-09-04",
    "seller_name": "销售方名称",
    "seller_tax_id": "统一社会信用代码或税号",
    "buyer_name": "购买方名称",
    "buyer_tax_id": "统一社会信用代码或税号",
    "currency": "CNY",
    "invoice_status": "蓝票",
    "confidence_score": 96.5,
    "items": [
      {
        "item_name": "货物或服务名称",
        "specification": "规格型号",
        "unit": "项",
        "quantity": 1,
        "unit_price": 100,
        "net_amount": 100,
        "tax_rate": 6,
        "tax_amount": 6,
        "goods_service_code": ""
      }
    ]
  }
}
```

支持的发票类型为：`数电专用发票`、`数电普通发票`、`增值税专用发票`、`增值税普通发票`、`机动车销售统一发票`、`其他`。未能映射的类型会标为待核对，仍不能绕过税务发票原有校验。

## 5. 调用链路与兼容性

```text
中国税务发票列表
  -> Actions: 识别发票
  -> create_recognition(company, direction, source_file)
  -> China Tax Invoice Recognition
  -> recognize_invoice(name)
  -> frappe.enqueue(run_invoice_recognition)
  -> Provider (Disabled / Generic HTTP / 后续适配器)
  -> 识别结果、文件哈希和发票唯一键预检
  -> create_tax_invoice_draft_from_recognition(name)
  -> China Tax Invoice 草稿
  -> 既有 validate / submit / archive / deduction / reports
```

原有 `china_finance.services.tax_invoice.import_invoices(records)` 未改动。手工录入、JSON 导入、开票申请、红冲、进项抵扣、电子档案、税务报表和对账流程均继续通过原有接口运行。新功能只使用 `source_system = Invoice Recognition` 与 `source_id = 识别任务编号` 标记来源。

## 6. 校验、权限与限制

- 发起识别需要 `System Manager`、`Accounts Manager` 或 `China Tax User` 角色；生成草稿还使用已有税务发票创建权限。
- 服务端校验附件来源、扩展名、文件头和大小，不接受任意 URL 或可执行文件。
- 同一 SHA-256 原件只能存在一个活跃/完成识别任务；已有相同“进销项 + 销方税号 + 发票号码”的正式税务发票时，禁止生成重复草稿。
- 识别结果缺少必填字段、没有明细、币种非 CNY 或类型无法映射时显示待核对提示。系统不会自动提交。
- 本次未接入税局真伪查验；识别成功不等于查验通过。
- 目前通用 Provider 使用整文件 Base64 请求，适用于受控网关或服务商协议明确兼容的场景。接入具体厂商时应新增专用适配器，不应把厂商字段扩散到税务发票模型。

## 7. 验证记录

- 2026-09-04 根据浏览器 Console 定位并修复 `china_tax_invoice_list.js:12` 的多余右括号；修复后脚本括号配平，列表入口可正常初始化。
- 已执行 `git diff --check`，未发现空白或补丁格式问题。
- 已新增 Python 单元测试覆盖识别结果标准化与缺失字段/明细预检。
- 当前工作区的 Bench 虚拟环境 Python 软链接指向不存在的 `/home/frappe/.pyenv/versions/3.14.2/bin/python3`，系统 Python 又未安装 `frappe`；因此无法在本环境执行 Frappe 运行时测试或实际异步队列识别。部署后需执行 `bench --site <站点> migrate`，配置 Provider，并按第 3 节完成一张测试发票的端到端验收。
