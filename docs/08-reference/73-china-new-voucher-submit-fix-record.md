# 中国财务新增凭证提交无反馈修复记录

## 问题

在“中国财务 -> 凭证 -> 新增凭证”中，填写借贷平衡的分录后点击“保存并记账”，页面没有出现保存、生成凭证或失败提示。

## 原因

1. 浏览器请求实际已触发。站点日志记录了：

   ```text
   {'name': 'CMVD-00026', 'cmd': 'china_finance.services.manual_voucher.submit_manual_voucher_draft'}
   ```

2. 提交请求在服务端访问数据库时失败，原因是当前开发环境的数据库主机不可解析：

   ```text
   MySQLdb.OperationalError: (2005, "Unknown server host 'mariadb' (-3)")
   ```

3. 前端提交按钮没有返回异步 Promise，且提交期间只依赖全局请求遮罩；服务端失败时用户容易感知为“没有反应”。

## 修复

文件：`china_finance/china_finance/page/china_new_voucher/china_new_voucher.js`

- 顶部主按钮返回 `submit_draft()` Promise，使 Frappe 能正确管理按钮工作状态。
- 提交开始时，在页面期间状态栏显示“正在保存并提交凭证，请稍候…”。
- 提交成功时显示“凭证已保存并记账”或“凭证已提交审核”。
- 提交失败时，状态栏显示具体原因，并弹出“保存并记账失败”对话框。
- 请求结束后恢复提交按钮，避免失败后按钮永久禁用。

## 验证

- 使用 Bench 自带 Node 执行 JavaScript 语法检查通过。
- 日志确认点击事件进入 `submit_manual_voucher_draft`。
- 已重新启动开发环境中的 `mariadb`、`redis-cache`、`redis-queue`、`frappe` 服务。
- 已执行 `bench --site aki_test.localhost clear-cache`，并用 `frappe.db.get_database_size` 验证站点数据库连接恢复。
- 已检查用户失败提交时留下的草稿 `CMVD-00026`：
  - 状态仍为 `Draft`。
  - `source_journal_entry` 为空。
  - 没有关联的 `Journal Entry`，没有半创建记账凭证。
  - 草稿当前没有分录行，因此不能直接替用户完成记账；后端提交校验返回明确错误 `凭证至少需要两条分录`。

## 环境恢复后的验收

启动包含 MariaDB 的 Frappe 环境后，强制刷新页面，录入两条借贷平衡分录，点击“保存并记账”。预期页面依次显示处理中、成功提示，并跳转到对应 Journal Entry；数据库故障时应显示明确错误而不是无反馈。

## 后续优化：记账凭证上传附件

在已提交的 Journal Entry 页面，“中国财务”菜单新增“上传凭证附件”按钮。

- 用户可直接在当前记账凭证页面选择文件并填写备注。
- 文件以私有附件上传到当前 Journal Entry。
- 上传成功后，系统按 `Posting|Journal Entry|凭证编号` 定位对应的已提交中国会计凭证，并创建 `China Electronic Document` 归档记录。
- 若当前凭证尚未生成已提交的中国会计凭证，会提示不能归档附件，避免附件挂到错误对象上。

验证：

- `gl_source_snapshot.js` 通过 Node 语法检查。
- `voucher_attachment_center.py` 通过 Python 语法检查。
- Frappe 可解析新增白名单方法 `china_finance.services.voucher_attachment_center.archive_source_voucher_attachment`。
- 当前页面凭证 `ACC-JV-2026-00033` 已定位到中国会计凭证 `CNV-2026-00158`，凭证号 `记9`。

## 凭证附件中心筛选区布局调整

根据页面验收截图继续调整筛选工具栏：

- 搜索框宽度收窄至约 300-350px，避免占满工具栏剩余空间。
- 公司 Link 控件改为使用与期间、日期相同的标签字号、标签间距和 34px 输入高度。
- 移除公司控件的外层顶部偏移，使公司、期间、起始日期、截止日期和搜索按钮在同一基线对齐。
- 为附件中心主体增加 12px 左右内边距，使筛选区、表格和分页整体向内收并保留均衡留白。

调整文件：`china_finance/public/css/china_voucher_attachment_center.css`。
