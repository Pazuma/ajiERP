# 本地 PaddleOCR 发票识别实施沉淀

## 1. 实施结果

已新增独立的 `invoice-ocr` Docker 服务，采用 PyMuPDF 文本层优先、PaddleOCR 扫描件回退的策略，将本地发票解析为 China Finance 现有 Generic HTTP Provider 标准 JSON。同时将税务发票表单操作改为“上传并识别”弹窗，用户无需先保存字段不完整的发票。

OCR 服务仅在 Docker 内部网络提供 `8080` 端口，不向宿主机公开。发票原件由 Frappe 通过带 Bearer Token 的内部请求发送，OCR 服务不持久保存文件。

## 2. 修改文件

| 文件 | 内容 |
| --- | --- |
| `services/invoice_ocr/Dockerfile` | CPU OCR 服务镜像、非 root 用户、模型目录与健康检查。 |
| `services/invoice_ocr/requirements.txt` | 锁定 FastAPI、PyMuPDF、OpenCV、PaddlePaddle、PaddleOCR 版本。 |
| `services/invoice_ocr/.env.example` | Token、文件大小、页数和渲染 DPI 示例。 |
| `services/invoice_ocr/app/main.py` | 健康检查和 `/v1/invoices/recognize` 接口。 |
| `services/invoice_ocr/app/security.py` | Bearer Token、Base64、扩展名、文件头和大小校验。 |
| `services/invoice_ocr/app/pdf.py` | PDF 文本层质量判断、页数限制和图片渲染。 |
| `services/invoice_ocr/app/engine.py` | PP-StructureV3 版面/表格优先、PaddleOCR 回退、模型延迟加载和统一文字/坐标结果。 |
| `services/invoice_ocr/app/parser.py` | 发票类型、号码、代码、日期、购销双方和明细解析。 |
| `services/invoice_ocr/app/validation.py` | 必填、税号和置信度预检。 |
| `services/invoice_ocr/app/schemas.py` | 请求与标准响应模型。 |
| `services/invoice_ocr/tests/` | 解析规则与文件安全测试。 |
| `compose.invoice-ocr.yaml` | 新增可跟随仓库交付的 OCR Compose 覆盖：内部服务、模型缓存和内存上限。当前开发环境的 `.devcontainer/docker-compose.yml` 也已接入，但该目录被仓库忽略。 |
| `china_finance/services/invoice_recognition.py` | 表单接口合并本地 OCR warning、统一哈希并支持直接写入完成态审计任务。 |
| `china_finance/china_finance/doctype/china_tax_invoice_recognition/china_tax_invoice_recognition.py` | 允许受控服务分支创建已完成识别任务，普通新建仍必须从 Draft 开始。 |
| `china_finance/public/js/china_tax_invoice_form_recognition.js` | 新增“上传并识别”Dialog，自动回填附件、票面字段与明细。 |
| `china_finance/tests/test_invoice_recognition.py` | 扩展标准响应隔离测试。 |

## 3. 部署与配置

在仓库根目录创建 `.env` 或在启动 Compose 前设置强随机 Token：

```env
INVOICE_OCR_TOKEN=请替换为至少32字节的随机值
```

重新创建开发容器服务：

```bash
docker compose -p devcontainer -f .devcontainer/docker-compose.yml -f compose.invoice-ocr.yaml build invoice-ocr
docker compose -p devcontainer -f .devcontainer/docker-compose.yml -f compose.invoice-ocr.yaml up -d invoice-ocr
docker compose -p devcontainer -f .devcontainer/docker-compose.yml -f compose.invoice-ocr.yaml restart frappe
```

首次构建需下载 Paddle 运行依赖；首次扫描件识别还会下载/初始化模型，因此耗时较长。模型缓存保存在 `invoice-ocr-models` volume。

进入 `中国财务 -> 设置 -> 中国财务设置 -> 发票识别`，填写：

```text
启用发票识别：是
发票识别服务商：Generic HTTP
识别服务地址：http://invoice-ocr:8080/v1/invoices/recognize
识别服务访问密钥：与 INVOICE_OCR_TOKEN 完全一致
识别超时（秒）：120
单文件最大大小（MB）：10
```

然后执行资源构建：

```bash
bench --site aki_test.localhost migrate
bench --site aki_test.localhost clear-cache
bench build --app china_finance
```

## 4. 使用方法

1. 进入 `中国财务 -> 发票管理 -> 中国税务发票`。
2. 点击“添加中国税务发票”。
3. 点击 `发票操作 -> 识别发票`。
4. 在弹窗中确认公司和进销项，选择 PDF、PNG、JPG 或 JPEG。
5. 点击“上传并识别”。不需要提前保存税务发票。
6. 识别结果和发票明细自动回填当前表单；黄色提示代表需要人工核对。
7. 补齐无法识别的必填字段和业务分摊，再保存、提交。

## 5. 调用链路

```text
税务发票新建表单 -> 上传并识别 Dialog -> Frappe File
  -> recognize_invoice_for_form()
  -> Generic HTTP Provider
  -> invoice-ocr:8080/v1/invoices/recognize
  -> PDF 文本层 / PaddleOCR
  -> parser + validation
  -> 标准 JSON + warnings
  -> China Tax Invoice Recognition 审计任务
  -> 当前表单字段和 items 回填
  -> 原有 validate / submit / archive / deduction / reports
```

## 6. 兼容性与限制

- 原 JSON 导入、独立识别任务、提交、红冲、抵扣和归档接口未改变。
- OCR 成功只代表票面解析完成，不代表税局验真通过。
- 当前解析器优先覆盖数电票和常见增值税票；复杂多行明细、免税/不征税、旋转或低清扫描件可能产生人工核对提示。
- OFD 尚未进入本地 OCR 服务，Frappe 现有文件校验虽允许 OFD，但本地服务会明确返回格式不支持。
- 当前真实样本 PDF 无可靠文本层，将走 PaddleOCR 回退；最终准确率必须在镜像启动后用该文件完成端到端验收。

## 7. 验证记录

- Python 文件已完成静态编译检查。
- Compose 文件已通过 `docker compose config --quiet` 检查。
- 宿主机无 Node，且当前执行环境无 Docker Socket 权限，暂未能在开发容器执行 JavaScript 语法检查。
- 宿主机未安装 pytest；OCR 单元测试需在新镜像安装完成后执行。
- 发票解析核心已使用合成的数电专票文本完成 smoke test，发票类型、号码、日期、购销双方和明细税率解析通过。
- 已尝试构建 `invoice-ocr`；Docker Hub 连接超时，无法拉取 `python:3.10-slim`，因此本轮未完成 Paddle 依赖安装、模型下载、健康检查和真实发票端到端推理。网络恢复后必须继续执行第 3 节构建及验收，不能把静态检查视为 OCR 已运行。
- 真实发票只用于本地验收，不进入 Git 或文档内容。
