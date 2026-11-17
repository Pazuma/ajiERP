# 本地 PaddleOCR + PP-Structure 发票识别方案

## 1. 目标

为中国财务发票管理接入完全本地部署的发票识别能力，使用 PaddleOCR + PP-Structure 识别中国增值税发票和数电发票，并将结果转换为现有 `Generic HTTP Provider` 所要求的标准 JSON，自动回填 `China Tax Invoice` 表单。

发票原件不发送到百度、腾讯、阿里等外部云服务。OCR 模型与 Frappe 分开部署，避免模型、OpenCV、PaddlePaddle 等大型依赖影响 ERPNext Web/Worker 容器。

首期支持：

- PDF、PNG、JPG、JPEG 发票；OFD 首期先通过可选转换组件转 PDF，转换不可用时给出明确提示。
- 数电专用发票、数电普通发票、增值税专用发票、增值税普通发票。
- 发票头、购销双方、金额和明细行结构化识别。
- CPU 部署；保留后续切换 GPU 推理的配置能力。

首期不实现：税局验真、自动抵扣、自动提交、自动创建客户/供应商/物料、机动车票及交通票据的全面适配。

## 2. 技术选型

采用两级识别策略：

```text
PDF/图片
  -> 文件安全校验
  -> PDF 是否存在可靠文本层？
       -> 是：PyMuPDF 提取文本、坐标和页面尺寸
       -> 否：PDF 转 200-300 DPI 图片
                -> PaddleOCR 文本检测与识别
                -> PP-Structure 表格/版面分析
  -> 发票版式分类
  -> 字段与明细解析
  -> 金额、税率、税号、日期勾稽
  -> 标准 JSON
  -> Frappe 表单自动回填
```

组件建议：

| 组件 | 用途 |
| --- | --- |
| PaddleOCR | 中文文字检测、方向分类和文字识别。 |
| PP-Structure / PP-StructureV3 | 表格、标题、文本块和版面区域分析。具体版本按选定 PaddleOCR 稳定版锁定。 |
| PyMuPDF | PDF 文本层、坐标提取和页面渲染。 |
| OpenCV | 图像旋转、去噪、透视矫正和增强。 |
| FastAPI + Uvicorn | 提供本地 HTTP 接口，与现有 Generic HTTP Provider 对接。 |
| Pydantic | 请求、响应和标准发票数据结构校验。 |

不在首期引入大语言模型。票面字段采用标签、空间坐标、正则、表格列和金额勾稽规则解析，结果更稳定、可解释，也避免财务数据被生成式模型改写。

## 3. 部署架构

新增独立 Docker 服务 `invoice-ocr`，与 Frappe 开发网络通信：

```text
Browser
  -> Frappe / China Finance
       -> Generic HTTP Provider
            -> http://invoice-ocr:8080/v1/invoices/recognize
                 -> PyMuPDF / PaddleOCR / PP-Structure
                 -> Invoice Parser
                 -> 标准 JSON
       -> China Tax Invoice 表单回填
```

建议约束：

- OCR 容器不挂载站点私有文件目录；Frappe 只通过请求体发送当前授权文件内容。
- 服务仅加入 Docker 内部网络，不向宿主机公网暴露端口。
- Frappe 与 OCR 服务使用固定 Bearer Token；Token 继续保存在“中国财务设置”的 Password 字段中。
- OCR 服务默认无状态，不保存原始发票文件；日志只记录请求编号、文件哈希、耗时、页数、识别结果状态和错误码。
- 模型目录使用只读 volume 或镜像层缓存，避免每次启动重新下载。

## 4. OCR HTTP 接口

继续兼容当前 `GenericHttpInvoiceRecognitionProvider`，不修改旧接口。

请求：

```http
POST /v1/invoices/recognize
Authorization: Bearer <internal-token>
Content-Type: application/json
```

```json
{
  "company": "test",
  "direction": "进项",
  "file_name": "invoice.pdf",
  "file_base64": "..."
}
```

成功响应：

```json
{
  "request_id": "ocr-20260904-000001",
  "data": {
    "invoice_type": "数电专用发票",
    "invoice_number": "12345678901234567890",
    "invoice_code": "",
    "invoice_date": "2026-07-21",
    "seller_name": "销售方名称",
    "seller_tax_id": "91441900XXXXXXXXXX",
    "buyer_name": "悦为智能技术（东莞）有限公司",
    "buyer_tax_id": "91441900XXXXXXXXXX",
    "currency": "CNY",
    "invoice_status": "蓝票",
    "confidence_score": 96.5,
    "items": [
      {
        "item_name": "货物或服务名称",
        "specification": "规格型号",
        "unit": "个",
        "quantity": 1,
        "unit_price": 100,
        "net_amount": 100,
        "tax_rate": 13,
        "tax_amount": 13,
        "goods_service_code": ""
      }
    ]
  },
  "warnings": [],
  "meta": {
    "engine": "paddleocr",
    "used_pdf_text_layer": true,
    "page_count": 1,
    "elapsed_ms": 850
  }
}
```

错误响应使用标准 HTTP 状态码和稳定错误码：

```json
{
  "request_id": "ocr-20260904-000001",
  "error": {
    "code": "UNSUPPORTED_INVOICE_LAYOUT",
    "message": "当前发票版式尚未支持"
  }
}
```

典型状态码：`400` 文件/参数错误、`401` Token 错误、`413` 文件过大、`415` 格式不支持、`422` 无法解析、`500` 推理异常、`503` 模型未就绪。

## 5. 发票解析规则

### 5.1 发票头

按标签和附近坐标识别：

| 票面标签/规则 | 标准字段 | 处理 |
| --- | --- | --- |
| “发票号码”“数电票号码” | `invoice_number` | 去除空格；保留前导零；只做字符白名单，不转数字。 |
| “发票代码” | `invoice_code` | 传统增值税发票使用，数电票可为空。 |
| “开票日期” | `invoice_date` | 支持 `YYYY年MM月DD日`、`YYYY-MM-DD`，统一为 ISO 日期。 |
| 标题包含“专用发票/普通发票/电子发票” | `invoice_type` | 映射为系统现有发票类型。 |
| “购买方信息/销售方信息”区域 | 双方名称、税号 | 使用区域标题、标签和上下位置区分，避免名称串位。 |
| “价税合计（大写/小写）” | 校验值 | 不直接写正式总计，仅用于与明细合计勾稽。 |

### 5.2 明细表

PP-Structure 识别表格后，将同一行按表头映射为：

```text
项目名称 | 规格型号 | 单位 | 数量 | 单价 | 金额 | 税率/征收率 | 税额
```

对应系统字段：

```text
item_name | specification | unit | quantity | unit_price
net_amount | tax_rate | tax_amount
```

处理规则：

- 合并跨行品名，但不能把下一条明细并入上一条金额。
- `***` 包裹的税收分类简称保留在品名中；不凭简称自动生成税收分类编码。
- “免税”“不征税”“***”税率保留警告，不强行转为 `0%`，由财务核对。
- 数量、单价缺失但金额存在时允许返回空值；净额与税额必须保留。
- 负数红票允许识别，但原蓝票和贷项发票必须由现有业务流程关联。

### 5.3 勾稽与置信度

至少执行：

1. 明细未税金额合计与票面“金额合计”差额不超过 0.01。
2. 明细税额合计与票面“税额合计”差额不超过 0.01。
3. 未税金额 + 税额与价税合计差额不超过 0.01。
4. 税号字符符合统一社会信用代码/纳税人识别号基本格式。
5. 发票号码、日期、销方税号、购方名称和明细必须存在。
6. 字段置信度结合 OCR 置信度、标签匹配、区域位置和金额勾稽计算；关键字段低于阈值时返回 warning。

## 6. 代码与文件计划

### 6.1 新增本地 OCR 服务

建议新增独立目录：`services/invoice_ocr/`。

| 文件 | 类型 | 内容 |
| --- | --- | --- |
| `services/invoice_ocr/Dockerfile` | 新增 | 固定 Python、PaddlePaddle、PaddleOCR、OpenCV、PyMuPDF 等版本；CPU 基础镜像。 |
| `services/invoice_ocr/requirements.txt` | 新增 | 锁定运行依赖，避免上游版本变化导致模型 API 不兼容。 |
| `services/invoice_ocr/app/main.py` | 新增 | FastAPI 应用、健康检查、认证和识别接口。 |
| `services/invoice_ocr/app/schemas.py` | 新增 | 请求、标准发票结果、明细、warning、error 的 Pydantic 模型。 |
| `services/invoice_ocr/app/security.py` | 新增 | Bearer Token 常量时间比较、请求大小与 MIME 校验。 |
| `services/invoice_ocr/app/engine.py` | 新增 | PaddleOCR/PP-Structure 单例加载、文本层优先、图片预处理和推理。 |
| `services/invoice_ocr/app/pdf.py` | 新增 | PyMuPDF 文本层质量判断、页面渲染、页数/DPI/尺寸限制。 |
| `services/invoice_ocr/app/parser.py` | 新增 | 发票类型判断、发票头、购销双方和明细表解析入口。 |
| `services/invoice_ocr/app/parsers/digital_vat.py` | 新增 | 数电专票/普票版式规则。 |
| `services/invoice_ocr/app/parsers/classic_vat.py` | 新增 | 传统增值税专票/普票版式规则。 |
| `services/invoice_ocr/app/validation.py` | 新增 | 金额、日期、税率、税号、必填字段和置信度校验。 |
| `services/invoice_ocr/tests/` | 新增 | 解析、勾稽、安全、接口和样本回归测试。测试样本不得提交真实完整税号，使用脱敏副本。 |

### 6.2 Docker 编排

| 文件 | 类型 | 内容 |
| --- | --- | --- |
| 当前开发 Compose 配置 | 小改 | 新增 `invoice-ocr` 服务、内部网络、模型缓存 volume、健康检查、CPU/内存限制和 Token 环境变量。具体文件实施前按仓库现有 compose 结构确定。 |
| `.env.example` 或现有示例配置 | 小改 | 新增 `INVOICE_OCR_TOKEN`、模型目录、线程数、最大页数和最大文件大小示例，不提交真实 Token。 |

### 6.3 China Finance 接入

| 文件 | 类型 | 内容 |
| --- | --- | --- |
| `china_finance/services/invoice_recognition_provider.py` | 原则上不改 | 本地服务遵守现有 Generic HTTP 合同；若错误格式需要增强，只新增兼容分支。 |
| `china_finance/services/invoice_recognition.py` | 小改 | 合并 Provider 返回的 `warnings`，保留重复、必填和系统枚举校验。 |
| `china_finance/public/js/china_tax_invoice_form_recognition.js` | 按上一方案小改 | 实现“上传并识别”弹窗并回填表单。 |
| `china_finance/tests/test_invoice_recognition.py` | 扩展 | 验证 Provider 标准响应、warning 合并、字段回填合同和异常映射。 |
| `docs/08-reference/44-local-paddleocr-invoice-recognition-implementation.md` | 实施后新增 | 最终部署、配置、使用路径、版本、性能和验收沉淀。 |

## 7. 配置方式

OCR 容器环境变量示例：

```env
INVOICE_OCR_TOKEN=<随机长密钥>
INVOICE_OCR_MAX_FILE_MB=10
INVOICE_OCR_MAX_PAGES=3
INVOICE_OCR_RENDER_DPI=250
INVOICE_OCR_DEVICE=cpu
INVOICE_OCR_WORKERS=1
```

中国财务设置：

```text
启用发票识别：是
发票识别服务商：Generic HTTP
识别服务地址：http://invoice-ocr:8080/v1/invoices/recognize
识别服务访问密钥：与 INVOICE_OCR_TOKEN 相同
识别超时（秒）：建议 120（CPU 首次推理可能较慢）
单文件最大大小（MB）：10
```

## 8. 受影响模块

| 模块 | 影响 | 兼容策略 |
| --- | --- | --- |
| Docker 开发/部署环境 | 新增 OCR 服务和模型缓存 | 独立容器，Frappe 不安装 Paddle 依赖。 |
| 中国财务设置 | 使用现有 Generic HTTP 配置 | 不新增服务商专属密钥字段。 |
| 税务发票表单 | 识别结果自动回填 | 不自动保存或提交，仍需人工核对。 |
| 发票识别任务 | 记录本地服务结果和请求号 | 现有任务字段不变。 |
| Frappe Worker/Web | 增加内部 HTTP 调用 | 设置超时；OCR 推理不占用 Frappe 进程。 |
| 文件与电子档案 | 原件仍由 Frappe 保存和归档 | OCR 服务无状态，不另存副本。 |
| 税务查验/抵扣 | 无直接影响 | OCR 成功不改变查验、抵扣状态。 |

## 9. 资源与性能预期

CPU 首期建议最低 4 核、8 GB 内存，并只启动 1 个 OCR Worker，避免每个 Worker 重复加载模型。首次请求包含模型初始化，可能明显慢于后续请求；容器启动时应预热模型。

性能目标以一页清晰发票为基准：

- 有可靠 PDF 文本层：通常应在 1-3 秒内完成解析。
- 需要 CPU OCR：目标 5-20 秒，取决于硬件、分辨率和模型版本。
- 最大 3 页，超出则拒绝或后续转异步任务。
- 同一文件通过 SHA-256 复用已有识别结果，避免重复推理。

以上是工程目标，不作为未经目标机器实测的性能承诺。

## 10. 安全与合规

- 服务只监听 Docker 内部网络，禁止直接暴露公网。
- 请求使用 Bearer Token，生产 Token 至少 32 字节随机值并定期轮换。
- Base64 解码后再次校验文件头、大小、页数、像素尺寸和压缩炸弹风险。
- 禁止记录完整 Base64、原始 OCR 全文、税号、购销双方和金额到普通日志。
- 临时文件使用独立临时目录，请求完成即删除；异常路径同样清理。
- 模型版本和解析规则版本写入响应 `meta`，便于财务结果追溯和回归。

## 11. 测试与验收

### 自动测试

- PDF 文本层质量判断与 OCR 回退。
- 数电票、传统增值税发票头字段解析。
- 多行、空数量/单价、不同税率和红字明细解析。
- 金额勾稽、税号、日期、低置信度 warning。
- Token 错误、伪扩展名、超大文件、超页数和无效 Base64。
- OCR 引擎异常、超时和不支持版式的标准错误响应。
- Frappe Generic HTTP Provider 到标准回填数据的合同测试。

### 业务验收

使用已提供文件：

`/home/cst/frappe_docker/悦为智能技术（东莞）有限公司_20260721150445.pdf`

验收标准：

1. 文件不离开本地 Docker 网络。
2. 能识别发票类型、号码、日期、购销双方名称/税号。
3. 能识别所有票面明细以及金额、税率和税额。
4. 明细合计与票面合计差异不超过 0.01，否则明确警告。
5. “上传并识别”后自动回填当前未保存表单，不触发必填保存错误。
6. 财务核对后可保存；提交后沿用现有归档与税务流程。

真实发票只能用于本地验收，不提交到 Git。若需要纳入回归测试，必须制作脱敏副本并更换公司名称、税号、号码和金额。

## 12. 分阶段实施

1. **基础服务**：搭建 FastAPI、认证、文件校验、健康检查和标准响应。
2. **文本层解析**：优先支持数电 PDF，完成头字段和明细解析。
3. **OCR 回退**：接入 PaddleOCR、PP-Structure、图像预处理和表格恢复。
4. **Frappe 接入**：复用 Generic HTTP Provider，合并 warning，实现上传识别弹窗。
5. **样本回归**：使用真实样本本地验收，新增脱敏样本测试。
6. **性能与安全**：模型预热、资源限制、日志脱敏、超时和异常清理。

## 13. 实施前确认

- 目标部署机器为 CPU 还是 NVIDIA GPU；本方案默认 CPU。
- Docker 服务可用内存和可接受的单张识别时延。
- 是否首期必须支持 OFD；建议先保证 PDF/图片，OFD 作为第二阶段。
- PaddleOCR/PP-Structure 的最终稳定版本需在构建镜像时验证并锁定，不能使用浮动 `latest`。
- 真实发票的使用、访问权限和脱敏测试样本应由财务负责人确认。

