# 发票上传识别 Playwright 验证记录

## 测试脚本

- 脚本：`docs/playwright_invoice_ocr_ui.mjs`
- 运行命令：
  `docker exec devcontainer-frappe-1 node /workspace/docs/playwright_invoice_ocr_ui.mjs`
- 测试站点：`http://127.0.0.1:8300`，站点 `aki_test.localhost`
- 测试账号：`Administrator / admin`

## 覆盖范围

脚本登录系统并打开新建 `China Tax Invoice` 表单，通过“发票操作 -> 识别发票”打开上传弹窗，上传示例 PDF，拦截并模拟 `recognize_invoice_for_form` 返回结果，验证以下行为：

1. 上传并识别弹窗可打开。
2. 发票号码、日期、销售方、购买方自动回填。
3. 原始发票附件自动回填。
4. 发票明细名称及金额自动回填。
5. 页面截图及浏览器 console error 被记录。

## 当前结果

本次未能执行浏览器断言。容器内没有系统 Chromium，Playwright 浏览器下载因容器无法访问下载源而未生成可执行文件，因此无法启动测试脚本。测试脚本和业务代码未因该环境问题修改。

## 重新执行

在可访问 Playwright 浏览器下载源的环境中执行：

```bash
docker exec devcontainer-frappe-1 bash -lc \
  'cd /workspace/development/erpnext.official && npx playwright install chromium'
docker exec devcontainer-frappe-1 node /workspace/docs/playwright_invoice_ocr_ui.mjs
```

成功后截图会生成到 `/workspace/docs/playwright_invoice_ocr_ui.png`，脚本会输出 JSON 格式的断言结果；当前接口响应是模拟数据，仅验证前端上传、调用和回填合同，不代表 PaddleOCR 实际推理结果。
