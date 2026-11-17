# 中国财务手工凭证全生命周期修复实施记录

## 1. 实施结论

已按 `61-china-manual-voucher-lifecycle-compliance-fix-plan.md` 落地第一、二阶段的代码基础和页面接入：

1. 新增可持久化的手工凭证草稿，未平衡、未填完整的录入不会写入 `Journal Entry`、`GL Entry` 或 `China Accounting Voucher`。
2. 新增凭证页面可选择凭证字、保存/恢复草稿、录入附件张数，并展示关闭/冻结期间预检状态。
3. 草稿提交后，把凭证字、附件张数和草稿来源链接固化到 `Journal Entry` 的新增中国财务元数据字段。
4. 正式凭证快照优先读取上述 `Journal Entry` 元数据，因此页面凭证字、来源凭证、正式快照和字号保持一致。
5. 已启用“强制制单审核分离”的公司必须先配置 `Journal Entry` Workflow；页面改为“提交审核”，不再伪造“待审核”文字。
6. 凭证流水号已依据 `sequence_reset` 使用“会计期间”或“会计年度”范围；旧月度范围键和既有凭证不被重排或重编号。

没有修改 ERPNext 原生 `Journal Entry`、`GL Entry`、`Accounting Period`、`Workflow` 或结账源码，也没有修改旧 `create_manual_voucher(company, posting_date, entries, remarks)` 的签名和返回结构。

## 2. 实际修改文件

| 文件 | 实际改动 | 预期效果 |
| --- | --- | --- |
| `china_finance/services/manual_voucher.py` | 保留旧即时记账接口；新增草稿保存、读取、列表、提交、取消、期间预检和草稿记账回写。 | 草稿与正式账务隔离；提交操作幂等。 |
| `china_finance/services/voucher.py` | 正式快照优先读取手工 Journal Entry 的凭证字、附件张数；新增流水号范围计算；Journal Entry 提交后回写草稿状态。 | 凭证字/附件数准确，期间/年度编号语义一致。 |
| `china_finance/setup/install.py` | 为 `Journal Entry` 增加 `custom_china_voucher_word`、`custom_china_attachment_count`、`custom_china_manual_voucher_draft`。 | 只增加只读审计元数据，不改变原生分录表。 |
| `china_finance/china_finance/doctype/china_manual_voucher_draft/*` | 新增草稿头 DocType。 | 保存公司、日期、凭证字、附件、状态、审核/记账信息、来源凭证。 |
| `china_finance/china_finance/doctype/china_manual_voucher_draft_entry/*` | 新增草稿分录子表。 | 保存摘要、科目、借贷金额。 |
| `china_finance/china_finance/page/china_new_voucher/china_new_voucher.js` | 页面接入凭证字 Select、草稿保存/恢复、提交审核和期间状态。 | 真实草稿替代原“只在当前页面”的提示。 |
| `china_finance/public/css/china_new_voucher.css` | 增加凭证字和期间状态样式。 | 页面清楚显示可记账/受阻状态。 |
| `china_finance/china_finance/doctype/china_finance_settings/china_finance_settings.py` | 开启制单审核分离时校验 Journal Entry Workflow。 | 避免设置已开启但业务无法提交。 |
| `china_finance/tests/test_manual_voucher.py` | 新增凭证字、附件数和流水号范围的单元测试。 | 覆盖不依赖业务数据的核心规则。 |
| `docs/playwright_china_manual_voucher_lifecycle.mjs` | 新增页面审计脚本。 | 默认无业务单据写入；可显式开启受控草稿写入测试。 |

## 3. 实际调用链

```text
新增凭证 Page
  -> save_manual_voucher_draft()
  -> China Manual Voucher Draft + Draft Entry
     （此时不创建 Journal Entry / GL Entry / 正式凭证）

提交审核 / 保存并记账
  -> submit_manual_voucher_draft()
  -> 校验至少两条、末级科目、借贷互斥、借贷平衡、启用日期
  -> Journal Entry（新增 custom_china_* 审计元数据）
     -> 未启用制审分离：立即 submit
     -> 启用制审分离：交给既有 Journal Entry Workflow
  -> ERPNext 原生关闭期间、冻结日期、权限、借贷平衡校验
  -> GL Entry
  -> create_voucher_from_source()
  -> China Accounting Voucher / Entry
  -> sync_manual_voucher_draft_posted()
```

## 4. 数据库迁移与部署

本次代码修改本身**没有执行迁移，也没有创建测试凭证或修改现有业务数据**。部署到测试站点后，由管理员执行：

```bash
docker exec -it -w /workspace/development/frappe-bench devcontainer-frappe-1 \
  bash -lc 'source env/bin/activate && bench --site aki_test.localhost migrate && bench --site aki_test.localhost clear-cache'
```

生产环境应先完成备份和测试站点验收，再将站点名替换为生产站点执行相同迁移。`after_migrate()` 会同步新增 Custom Fields；前端资源由开发服务器自动刷新，生产部署则再执行 `bench build` 并重启相应进程。

## 5. 已完成的静态验证

| 检查 | 结果 |
| --- | --- |
| 新增两个 DocType JSON 解析 | 通过 |
| `manual_voucher.py`、`voucher.py`、新增 DocType 控制器、设置控制器 Python 编译 | 通过 |
| `china_new_voucher.js` JavaScript 语法检查 | 通过（使用仓库内 Node） |
| Git diff 空白字符检查 | 通过 |

未在本次实施中运行迁移、提交 Journal Entry 或生成 GL Entry，因此下列端到端步骤仍需在迁移后的测试库执行。

## 6. 自动化测试方法

### 6.1 单元测试

迁移后执行：

```bash
docker exec -it -w /workspace/development/frappe-bench devcontainer-frappe-1 \
  bash -lc 'source env/bin/activate && bench --site aki_test.localhost run-tests --app china_finance --module china_finance.tests.test_manual_voucher'
```

覆盖内容：

- “统一记字”只能选择“记”；
- “收付转记”可选择收、付、转、记；
- 附件张数必须是 `0–999` 的整数；
- “会计期间”和“会计年度”两种流水号范围键正确生成。

### 6.2 Playwright 页面测试

默认只检查页面，不写业务单据：

```bash
docker exec -it -w /workspace \
  -e CF_BASE_URL=http://aki_test.localhost:8300 \
  -e CF_USER=Administrator \
  -e CF_PASSWORD='***' \
  devcontainer-frappe-1 \
  /workspace/development/erpnext.official/.tools/node/bin/node \
  /workspace/docs/playwright_china_manual_voucher_lifecycle.mjs
```

它检查凭证字控件、期间预检、草稿入口，并输出：

```text
docs/china-finance-test-evidence/manual-voucher-lifecycle.json
docs/china-finance-test-evidence/manual-voucher-lifecycle.png
```

若要测试草稿持久化，必须显式设置 `CF_ALLOW_DRAFT_WRITE=1`，并提供当前公司下两个末级科目 `CF_DEBIT_ACCOUNT`、`CF_CREDIT_ACCOUNT`。脚本只保存、读取、取消一个名称为 `CMVD-*` 的草稿；不会提交 Journal Entry，不会创建 GL Entry 或正式凭证。

## 7. 人工验收流程

1. 迁移后进入“中国财务 → 新增凭证”，确认顶部凭证字是下拉框：
   - 公司设置为“统一记字”时仅显示“记”；
   - 设置为“收付转记”时显示收、付、转、记。
2. 输入不平衡的一行或两行数据，点击“保存草稿”，刷新页面后从“我的草稿”恢复：
   - 公司、日期、凭证字、附件张数、摘要和每条分录均应恢复；
   - 不应出现 Journal Entry、GL Entry、China Accounting Voucher。
3. 点击“提交审核/保存并记账”：
   - 少于两条、父级科目、同一行借贷同时有金额、借贷不平衡、启用日前日期均必须被阻止；
   - 对于可记账的平衡凭证，未启用制审分离的公司应直接进入已提交 Journal Entry；
   - 启用制审分离的公司必须进入 Workflow，且制单人不能作为审核人或记账人。
4. 打开来源 Journal Entry，确认只读字段“凭证字”“附件张数”“手工凭证草稿”已写入。
5. 打开对应 China Accounting Voucher，确认：
   - 凭证字与页面选择一致；
   - 附件张数与页面输入一致；
   - 凭证字号按公司设置的期间/年度范围递增。
6. 将日期改到 `activation_date` 之前、已关闭 Accounting Period 或 `accounts_frozen_till_date` 之前：
   - 页面先显示受阻提示；
   - 即便绕过页面，最终 Journal Entry 提交仍必须被 ERPNext 原生机制阻止。
7. 取消已提交 Journal Entry，确认原正式凭证被标为 `Reversed`，生成关联冲销快照；草稿不允许恢复编辑。

## 8. 已知限制与后续建议

- 本次复用已有 Journal Entry Workflow，不自动创建或猜测任何公司的审批流、状态名称、审核角色；管理员必须按企业内控制度配置。
- 当前草稿列表只显示“当前用户”的可编辑草稿；财务经理仍可按草稿名称打开并处理，后续可按业务需要增加团队待审列表。
- 期间预检是体验层提示；不同角色的冻结期间豁免仍以 ERPNext 最终提交校验为准。
- “会计年度”重置范围上线前，应由财务负责人确认切换日期。已有凭证不会重编号，新范围会以同年度既有正式凭证的最大流水号作为起点。

## 9. 回滚

1. 先停止新增凭证页面调用新草稿接口，恢复旧 `create_manual_voucher()` 页面调用即可恢复旧直接记账路径。
2. 保留新增 Custom Fields 和草稿记录，不删除已产生的审计数据。
3. 已提交 Journal Entry 和 China Accounting Voucher 不允许物理删除；如需纠正，使用原生取消/冲销。
4. 如需停止年度重置，修改公司设置回“会计期间”；不会改写已有 `China Voucher Sequence` 或正式凭证字号。
