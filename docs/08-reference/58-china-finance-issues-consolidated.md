# 中国财务模块问题汇总

## 1. 目的

把当前测试过程中发现的问题集中到一份文档，作为统一问题清单、后续修复对照和复测入口。

## 2. 问题总览

| 编号 | 问题 | 对应线路 | 当前状态 |
| --- | --- | --- | --- |
| P-01 | 页面反复报 `Cannot read properties of null (reading 'join')` | `China Tax Invoice`、`China Tax Invoice Recognition` 页面刷新/表单脚本初始化 | 待定位 |
| P-02 | 404 `custom_filters/public/js/naming_series_i18n.js` | 列表页、表单页、编号规则相关静态资源加载 | 待定位 |
| P-03 | 404 `/undefined` | 页面渲染期间的错误 URL 拼接分支 | 待定位 |
| P-04 | `China Tax Invoice` 手工录单可提交，但页面仍有前端错误 | `China Tax Invoice` 新建 -> 保存 -> 提交 -> 详情回看 | 已验证，待修 |
| P-05 | `China Tax Invoice Recognition` 列表/新建页可打开，但仍有前端错误 | `China Tax Invoice Recognition` 列表页、`new-...` 新建页 | 已验证，待修 |
| P-06 | 识别入口旧脚本与当前控件不一致 | `China Tax Invoice` 表单顶部“发票操作 -> 识别发票” | 已修复入口，但旧脚本需更新 |
| P-07 | 现金流量指定正式业务测试被配置阻塞 | `Journal Entry -> China Cash Flow Assignment -> China Cash Flow Assignment Item` | 配置阻塞 |
| P-08 | 新公司初始化曾缺少 `All Departments` 根部门 | 公司初始化 / `Company.create_default_departments()` 前置链路 | 已记录，待继续确认 |
| P-09 | `160201 机器设备累计折旧` 早前曾被映射出多个现金流建议 | `classify_account_number` / 现金流建议 / 初始化模板映射链路 | 已修复后待继续验证 |
| P-10 | 页面审计中存在较多 HTTP/浏览器错误事件 | Playwright 页面审计脚本、各 DocType/Report 访问链路 | 已分类，待逐项修复 |

## 3. 详细问题

### P-01 页面运行时错误 `join`

现象：

- 页面控制台稳定出现 `Cannot read properties of null (reading 'join')`

已观察到的页面：

- `China Tax Invoice`
- `China Tax Invoice Recognition`

判断：

- 属于前端脚本空值处理问题。
- 不是单据保存失败本身，但会污染页面加载体验。
- 可能发生在表单/列表初始化时对空数组或空字段调用 `join` 的分支。

### P-02 资源 404 `custom_filters/public/js/naming_series_i18n.js`

现象：

- 多个页面加载时请求该资源返回 404。

判断：

- 属于静态资源路径或引用配置问题。
- 可能影响编号规则、页面初始化或国际化脚本加载。
- 主要出现在 `naming_series` 相关页面资源装载期间。

### P-03 资源 404 `/undefined`

现象：

- 页面请求了一个明显异常的 URL `/undefined`。

判断：

- 多半是前端拼接链接时某个变量为空。
- 需要定位发起请求的页面脚本。
- 更像是某条页面/按钮/资源路径生成分支把未定义值直接拼进了 URL。

### P-04 `China Tax Invoice` 可提交但存在页面错误

已确认：

- 手工新建、保存、提交可完成。
- 单据 `CTI-2026-00001` 成功提交。
- 子表 `China Tax Invoice Item` 正常落库。

问题：

- 页面层仍有前端错误和 404。
- 线路为 `China Tax Invoice` 新建页、保存提交页和详情回看页。

### P-05 `China Tax Invoice Recognition` 列表/新建页可打开但仍报错

已确认：

- 列表页可打开。
- 新建页可打开。
- 主要字段可见。

问题：

- 同样存在 `join` 错误和 404 资源。
- 线路为 `China Tax Invoice Recognition` 列表页与新建页。

### P-06 识别入口旧脚本与当前控件不一致

现象：

- 旧 Playwright 脚本找不到当前上传控件。

当前状态：

- 已改成以当前表单逻辑为准，入口可以打开。
- 线路为 `China Tax Invoice` 表单顶部操作菜单和上传识别弹窗分支。

后续：

- 旧脚本仍需按实际页面结构维护。

### P-07 现金流量指定测试被配置阻塞

现象：

- 目标公司现金流量直接指定启用日期为空。

判断：

- 这是配置问题，不是流程失败。
- 正式现金流指定链路不能继续推进，直到配置补齐。
- 线路为 `Journal Entry` 过账后到 `China Cash Flow Assignment` 的自动生成/确认链路。

### P-08 新公司初始化曾缺少 `All Departments`

现象：

- 新公司初始化日志出现缺少 `All Departments` 根部门的问题。

判断：

- 属于初始化前置条件不足。
- 线路为 `Company` 初始化后创建默认 `Department` 根节点的分支。

### P-09 `160201 机器设备累计折旧` 曾产生错误现金流建议

现象：

- 早前测试里，非现金科目被错误纳入现金流建议。

状态：

- 已做小增量修正，但后续仍要继续验证该分支。
- 线路为会计科目模板、现金流建议、现金流指定生成逻辑。

### P-10 页面审计存在大量错误事件

现象：

- 审计里有较多 HTTP / 浏览器错误事件。

判断：

- 一部分是重复事件，不一定都是独立缺陷。
- 仍需按 URL 分类逐项清理。
- 线路为 Playwright 审计脚本采集的页面访问、接口响应、console error 和 pageerror。

## 4. 已形成的测试记录

| 文档 | 内容 |
| --- | --- |
| [55-china-finance-voucher-flow-test-record.md](./55-china-finance-voucher-flow-test-record.md) | 凭证链路和现金流配置阻塞 |
| [56-china-tax-invoice-manual-flow-test-record.md](./56-china-tax-invoice-manual-flow-test-record.md) | 税务发票手工录单与提交回看 |
| [57-china-tax-invoice-recognition-list-form-test-record.md](./57-china-tax-invoice-recognition-list-form-test-record.md) | 发票识别任务列表/新建页 |

## 5. 已验证线路

| 线路 | 结果 | 备注 |
| --- | --- | --- |
| `China Tax Invoice -> 列表页 -> 发票操作 -> 创建进项税抵扣批次` | 入口可打开 | 仍伴随同一组前端运行时错误和 404 |
| `China Input Tax Deduction Batch -> 列表页` | 可打开 | 页面可见，但尚未做确认/抵扣写操作 |
| `China Tax Invoice Recognition -> 列表页 / 新建页` | 可打开 | 仍伴随同一组前端运行时错误和 404 |
| `China Tax Invoice -> 新建 / 保存 / 提交 / 回看` | 可通过 | 单据 `CTI-2026-00001` 已生成 |

## 6. 下一步建议

优先顺序建议：

1. 继续补 `join` 错误和 404 的定位。
2. 继续测税务发票后续链路，例如查验、抵扣、分摊。
3. 在现金流配置补齐前，不把指定单链路判为业务通过。
