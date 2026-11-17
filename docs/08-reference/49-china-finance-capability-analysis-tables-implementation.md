# 四项能力分析表实施沉淀

## 实施内容

已新增统一“财务能力分析” Page，提供偿债能力、运营能力、盈利能力、发展能力四个分析分支；新增只读服务 `china_finance.services.capability_analysis.get_capability_analysis`，按公司和日期聚合 GL Entry，并返回统一指标结构。新增局部 CSS，挂载到 China Finance 财务分析导航。

### 列表页风格调整（本轮方案）

已将后续 UI 调整口径沉淀为参考“税务科目映射”列表页：沿用中国财务左侧导航、顶部标签栏和面包屑；筛选区采用浅灰列表筛选控件；结果区采用浅灰表头、紧凑行高、细分隔线和蓝色状态徽标；保留刷新、更多、下载、打印等列表工具操作。样式只允许作用于 `.cf-capability-analysis`，不影响其他财务页面。

本轮已按方案完成页面风格调整：新增列表页工具栏区域、只读分析状态徽标、过滤条件按钮，并将结果表头调整为 Frappe 列表页浅灰风格；后端接口和分析计算分支保持不变。

## 修改文件

- `china_finance/services/capability_analysis.py`
- `china_finance/china_finance/page/china_capability_analysis/`
- `china_finance/public/css/china_capability_analysis.css`
- `china_finance/hooks.py`
- `china_finance/setup/install.py`

未修改中国财务报表、总账、日账簿、税费计算表及原有接口。

## 检验步骤

1. Python：`python3 -m compileall -q china_finance/services/capability_analysis.py`。
2. JavaScript：使用 Node.js `node --check china_finance/china_finance/page/china_capability_analysis/china_capability_analysis.js`。
3. JSON：校验 Page 元数据可由 Frappe migrate 同步。
4. 静态资源：执行 `bench build --app china_finance`。
5. 数据库：执行 `bench --site aki_test.localhost migrate` 和 `clear-cache`。
5. 接口：以有效公司、期间分别调用 `SOLVENCY`、`OPERATION`、`PROFITABILITY`、`DEVELOPMENT`，确认返回 `rows/status/warnings`。
6. 页面：打开 `/app/china-capability-analysis`，切换四个页签，检查筛选、刷新、下载、打印和窄屏横向滚动。
7. 回归：确认 China Financial Statements、China Daily Ledger、China Tax Calculation Sheet 路由和接口仍可使用。

## 检验范围

- 功能：四类指标表、统一返回合同、缺失数据和分母为零状态。
- 权限：Accounts Manager、China Finance Manager、China Finance Auditor、System Manager；公司权限继续生效。
- 样式：Frappe 主题色、表头、行式表格、响应式布局和打印/导出。
- 数据：仅读取 GL Entry，不写入凭证、结账、税务申报或历史账务。
- 性能：单公司、指定期间聚合查询；未引入全量明细加载。
- 风格：与截图所示列表页的导航层级、工具栏、筛选控件、表头、行密度、状态徽标和空状态保持一致；验证 1440px、1280px、768px、390px 视口无重叠。

本次执行结果：`git diff --check` 通过；当前执行环境未提供 `node` 和 `bench` 命令，构建、迁移、缓存清理及浏览器视口验证需在 Frappe bench 环境执行。

## 已知边界

流动资产/负债、存货、费用等细分指标需要科目映射或法定报表模板支持，当前显示“需补充数据”；参考值为辅助信息，不作为法定标准。后续可在新增计算器分支中补齐，不改变现有服务入口和旧接口。
