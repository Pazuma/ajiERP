# 中国发票识别任务列表与新建页测试记录

## 1. 测试目标

验证 `China Tax Invoice Recognition` 的列表页和新建页是否能正常打开，并记录当前可见按钮、字段和页面错误。

本轮只做页面检查，不提交识别任务，不调用外部识别服务，不修改代码。

## 2. 测试环境

| 项目 | 值 |
| --- | --- |
| 站点 | `aki_test.localhost` |
| 时间 | `2026-09-07` |
| 用户 | `Administrator / admin` |
| 浏览器 | Playwright Chromium |

## 3. 执行结果

### 3.1 列表页

打开地址：

`/desk/china-tax-invoice-recognition`

可见标题：

- `China Tax Invoice Recognition`

可见按钮中与本页相关的内容包括：

- `添加China Tax Invoice Recognition`
- `新建 China Tax Invoice Recognition`
- `新建`
- `操作`

### 3.2 新建页

打开地址：

`/desk/china-tax-invoice-recognition/new-...`

可见主要按钮：

- `保存`
- `操作`

可见字段前部包括：

- `naming_series`
- `company`
- `direction`
- `status`
- `source_file`
- `file_hash`
- `provider`
- `provider_request_id`

## 4. 问题记录

### 4.1 页面控制台错误

稳定复现：

- `Cannot read properties of null (reading 'join')`

### 4.2 资源 404

稳定复现：

- `http://127.0.0.1:8300/custom_filters/public/js/naming_series_i18n.js`
- `http://127.0.0.1:8300/undefined`

## 5. 结论

识别任务列表和新建页可打开，入口存在；但页面仍带有前端运行时错误和资源缺失问题，后续做识别任务实际提交前需要继续确认上传控件和识别动作是否可用。

