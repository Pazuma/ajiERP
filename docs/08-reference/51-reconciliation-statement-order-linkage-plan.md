---
title: 新建对账单自动汇总已有订单打通方案
---

# 新建对账单自动汇总已有订单打通方案

状态：已完成首期代码实现；已通过 Python 语法检查，待在实际 Frappe 站点完成浏览器和真实业务数据验收。

实施原则：小增量改造，优先新增接口、按钮和数据分支；不改动现有导出接口签名，不改变现有销售订单、送货单、发票、收款和已提交对账单的行为。

## 1. 目标

打通“新建对账单”页面与已有销售业务单据：用户选择客户、对账起止日期后，系统自动读取期间内符合条件的销售订单和送货单，生成可核对的对账明细，保存后可导出 PDF 或 Excel 发送给客户。

本功能不会新建销售订单、送货单、发票或收款单，也不会修改原业务单据。

## 2. 建议业务流程

```text
新建对账单
  -> 选择对账类型 Customer
  -> 选择客户
  -> 选择起始日期和截止日期
  -> 点击“加载对账数据”
  -> 服务端读取已提交销售订单/送货单
  -> 返回汇总金额和明细预览
  -> 用户确认并保存对账单
  -> 点击“导出客户对账单”
  -> 下载 PDF/Excel 并发送客户
  -> 根据客户反馈更新确认状态或登记差异
```

页面上的“加载对账数据”应是显式操作，避免用户刚修改日期或客户时系统隐式覆盖已编辑的明细。

## 3. 数据来源和取数口径

### 3.1 客户

现有字段 `party` 为 Dynamic Link，`party_type` 在客户对账时自动设置为 `Customer`。页面应提供客户搜索选择，并保留新建客户档案入口；新建客户不等于新建订单。

### 3.2 业务单据

首期建议以已提交 `Delivery Note` 作为正式对账明细来源，因为它代表实际交付；通过 `against_sales_order` 关联销售订单。可同时读取销售订单信息用于展示订单号和订单日期。

可选增强：允许用户切换“实际交付口径”和“订单口径”。订单口径读取已提交 `Sales Order Item`，但必须在界面明确提示其中可能包含尚未交付数量。

### 3.3 筛选条件

- 公司：取对账单 `company`；
- 客户：取 `party`；
- 日期：按送货单 posting date（订单口径则按销售订单 transaction date）；
- 状态：仅纳入已提交单据，排除取消单据；
- 退货：按 ERPNext 退货标识和负数数量冲减，避免重复计算；
- 币种：同一张对账单只允许一种币种；
- 权限：服务端逐条执行用户对业务单据的读取权限校验。

## 4. 对账明细字段映射

`China Reconciliation Line` 应至少保存以下来源字段：

| 对账明细 | 来源 |
|---|---|
| 日期 | Delivery Note posting date |
| 订单号 | Delivery Note Item against_sales_order |
| 送货单号/凭证号 | Delivery Note name |
| 产品编码 | Delivery Note Item item_code |
| 产品名称 | Delivery Note Item item_name |
| 数量 | Delivery Note Item qty |
| 单价 | Delivery Note Item rate |
| 金额 | Delivery Note Item amount 或含税金额 |
| 币种 | Delivery Note currency |
| 备注 | 单据备注或行备注 |

明细还应保存来源单据类型和来源单据名，便于追溯、重新加载和防止同一单据重复加入。

## 5. 页面交互

新建页面建议调整为：

- `往来单位`：Customer Link，可搜索选择，支持新建客户；
- `起始日期`、`截止日期`：必填；
- `加载对账数据`：客户和日期完整后启用；
- 加载结果：显示单据数量、明细行数、币种、数量、金额合计；
- 明细表：允许查看和删除行，但默认不允许手工新增无来源行；
- `重新加载`：明确提示将替换当前未保存的自动生成明细；
- `导出客户对账单`：保存后可用，调用现有 PDF 导出能力。

“确认方式”建议保留为确认流程字段，但不参与取数：客户对账场景默认 `External Confirmation`，导出后由财务发送客户，收到盖章/邮件确认后上传附件并提交确认。

## 6. 服务端接口建议

新增只读预览接口：

```python
@frappe.whitelist()
def preview_customer_statement(company, customer, from_date, to_date):
    """Return validated delivery/order rows and summary without saving."""
```

接口返回：

- 客户、公司、日期范围和币种；
- 纳入的送货单/订单数量；
- 明细行列表；
- 数量、含税金额和币种汇总；
- 被排除单据及原因。

保存时服务端必须重新取数或校验来源单据版本，不能信任浏览器提交的金额。对账单保存后，明细作为当时的对账快照保留；原订单后续变化不应无提示地改变历史对账单。

## 7. 导出和客户确认

保存后的对账单提供：

1. PDF：使用现有客户对账单模板，显示客户、期间、订单/送货明细、金额合计和签章区；
2. Excel：保留明细数据，便于客户逐项核对；
3. 确认附件：客户回传盖章件或邮件凭证上传到 `confirmation_file`；
4. 差异处理：客户有异议时登记 `China Reconciliation Difference`，不直接修改原订单金额。

## 8. 校验和异常处理

- 未选择客户或日期不完整时禁止加载；
- 起始日期晚于截止日期时提示错误；
- 期间无已提交业务单据时提示“暂无可对账数据”，不生成空白对账单；
- 混合多个客户、公司或币种时拒绝生成；
- 已存在相同客户、公司和期间的有效对账单时提示新建版本或替代原单；
- 业务单据在预览后被取消或修改时，保存前重新校验并提示刷新；
- 已付款/未付款金额在付款分摊链路未经过财务样本验证前，显示“以财务确认为准”，不得伪造精确分摊。

## 9. 实施顺序

1. 确认 `China Reconciliation Line` 需要补充的来源单据字段；
2. 实现客户和日期条件下的服务端预览取数；
3. 在新建表单增加“加载对账数据”和预览汇总；
4. 保存时建立对账快照并增加重复/版本校验；
5. 接入现有 PDF/Excel 导出；
6. 完成客户确认附件和差异登记流程；
7. 用单客户、多送货单、退货、无数据、跨币种和改单场景验收。

## 10. 代码修改清单

以下是建议的最小改动范围。文件名以当前代码库为准，新增逻辑应尽量放在独立模块中。

### 10.1 新增文件

| 文件 | 类型 | 作用 |
|---|---|---|
| `china_finance/services/customer_reconciliation_statement.py` | 新增 | 客户对账预览、来源单据查询、明细转换、汇总和一致性校验；不复用会修改业务单据的写入逻辑 |
| `china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js` | 修改 | 在现有表单脚本中增量增加“加载对账数据/重新加载/导出”，保留差异、银行和采购逻辑 |
| `client_akivision/utils/customer_reconciliation_pdf.py` | 扩展独立分支 | 增加已保存 China Reconciliation Statement 快照 PDF 导出；不改变旧接口 |
| `china_finance/tests/test_customer_reconciliation_statement.py` | 待补充 | 后续补充站点级取数、权限、快照和异常场景测试 |

### 10.2 修改文件

| 文件 | 增量修改 |
|---|---|
| `china_reconciliation_statement.json` | 将 `party` 明确配置为可搜索 Customer 的选择体验；如明细表缺少追溯字段，仅新增来源单据类型、来源单据名、订单号、送货单号、币种等字段，不删除旧字段 |
| `china_reconciliation_statement.py` | 在 `validate`/保存前增加来源明细一致性校验和快照校验；保留现有确认、差异、银行和供应商校验逻辑 |
| `china_reconciliation_statement.js` | 增加“加载对账数据”和“导出客户对账单”按钮分支；现有差异登记、银行快照、采购豁免逻辑不改 |
| `china_reconciliation_line.json` | 仅在缺少来源追溯信息时增加字段；现有金额、数量和状态字段保持兼容 |
| `client_akivision/public/js/document_export_list.js` | 如需从销售订单/送货单进入新流程，仅增加“导入/生成对账单”菜单项，不删除现有 Excel/PDF 菜单 |
| `client_akivision/public/js/delivery_note_list.js` | 保留现有客户对账 PDF 入口；可增加跳转到新建对账单并预填客户/日期的入口 |
| `client_akivision/utils/customer_reconciliation_pdf.py` | 仅增加从已保存对账单快照读取明细的分支；保留原按销售订单/送货单直接生成 PDF 的参数和行为 |
| `client_akivision/hooks.py` | 只有在前端脚本未被现有 DocType 脚本覆盖时才增量挂载，不替换原有 `doctype_list_js` |

### 10.3 不修改的接口和模块

- 不修改现有 `download_reconciliation_export` 和 `download_document_export` 的参数、返回格式和调用方；
- 不修改销售订单、送货单、销售发票、付款凭证的提交和记账逻辑；
- 不改变现有银行对账快照、采购齐套校验、差异登记和确认提交规则；
- 不通过新流程自动创建订单、送货单、发票、收款或会计凭证。

## 11. 新增接口和调用链路

新增接口建议放在 `china_finance.services.customer_reconciliation_statement`：

```python
@frappe.whitelist()
def preview_customer_reconciliation_statement(company, customer, from_date, to_date):
    """Read submitted delivery/order data and return preview rows and totals."""

@frappe.whitelist()
def load_customer_reconciliation_lines(statement_name):
    """Reload validated rows into an unsaved/new statement context."""

@frappe.whitelist()
def export_customer_reconciliation_statement(statement_name, file_type="pdf"):
    """Export a saved reconciliation snapshot without changing old exports."""
```

调用链路：

```text
China Reconciliation Statement 新建页
  -> china_reconciliation_statement.js 校验客户/日期
  -> preview_customer_reconciliation_statement
  -> customer_reconciliation_statement.py 查询已提交 Delivery Note
  -> 关联 Sales Order，过滤客户/公司/币种/日期/取消单/退货
  -> 返回明细、汇总、排除原因
  -> 前端填充 China Reconciliation Line（未保存）
  -> 用户点击保存
  -> china_reconciliation_statement.py 重新校验来源单据并保存快照
  -> 导出按钮调用新增 export_customer_reconciliation_statement
  -> 复用 customer_reconciliation_pdf 模板/渲染工具生成 PDF 或 Excel
```

预览接口只读；保存阶段必须重新校验，防止预览后原单据取消、修改或权限变化。导出读取已保存快照，确保发送给客户的文件与当时确认的对账内容一致。

## 12. 受影响模块

| 模块 | 影响 | 处理方式 |
|---|---|---|
| 中国财务/对账单 | 新增自动加载和快照保存 | 在现有表单上增加按钮和校验分支 |
| 客户主数据 | 作为往来单位选择来源 | 使用现有 Customer Link，不复制客户数据 |
| 销售订单 | 提供订单号和订单日期关联信息 | 只读查询 |
| 送货单 | 提供正式对账数量和金额 | 只读查询，首期作为主取数来源 |
| 销售发票/付款 | 后续用于付款状态展示 | 首期不改变现有付款分摊；金额不确定时显示财务确认提示 |
| PDF/Excel 导出 | 增加已保存对账单导出分支 | 复用现有模板和渲染工具，保留旧入口 |
| 差异管理 | 客户反馈差异后登记事项 | 复用 `China Reconciliation Difference`，不修改原订单 |
| 权限/审计 | 控制跨公司、跨客户和无权限读取 | 服务端逐单校验并记录来源 |

## 13. 预期效果

完成后，用户在“新建对账单”页面只需选择客户和日期并点击“加载对账数据”，系统即可显示期间内已有送货/订单明细及金额汇总；保存后可直接导出正式 PDF 或 Excel 发送客户。

预期结果包括：

- 不再手工逐行录入对账明细；
- 不会因为新建对账单而产生新订单或重复业务单据；
- 明细可追溯到原销售订单和送货单；
- 导出文件与已保存对账快照一致；
- 原有销售订单、送货单、银行对账、采购对账和旧导出功能保持可用；
- 客户有异议时只登记差异，不直接改动历史业务数据；
- 对账单后续可扩展客户确认附件、版本替代和重新导出。

## 14. 数据流

```text
Customer 主数据
      |
      v
China Reconciliation Statement.party + company + from_date/to_date
      |
      v
preview_customer_reconciliation_statement
      |
      v
已提交 Delivery Note（按公司、客户、日期、非取消、非退货过滤）
      |
      +--> Delivery Note Item（产品、数量、单价、金额、against_sales_order）
      |
      v
前端生成 China Reconciliation Line（来源快照）
      |
      v
保存时 ChinaReconciliationStatement.validate 再校验
      |
      v
已保存对账单快照
      |
      +--> download_saved_customer_reconciliation_statement
                |
                v
        customer_reconciliation_pdf.html
                |
                v
             PDF 下载
```

金额口径：首期使用送货单行 `amount`，正数进入借方/余额，负数进入贷方/余额；付款金额仍显示“以财务确认为准”，不在本次增量中重新分摊。

## 15. 测试流程

### 15.1 静态检查

```bash
python3 -m compileall -q \
  development/frappe-bench/apps/china_finance/china_finance/china_finance/services/customer_reconciliation_statement.py \
  development/frappe-bench/apps/china_finance/china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.py \
  development/frappe-bench/apps/client_akivision/client_akivision/utils/customer_reconciliation_pdf.py
```

检查结果：通过。前端脚本需在 Frappe 站点加载后通过浏览器控制台和表单操作验证；宿主机没有单独执行 Node 语法检查。

### 15.2 测试数据准备

准备同一公司、同一客户、同一币种的两张已提交送货单，至少包含两条明细和一个 `against_sales_order`；另准备一张取消送货单、一张退货单、一个无业务记录客户，以及跨币种或跨客户单据。

### 15.3 浏览器功能流程

部署测试前执行 `bench --site <site> migrate` 和 `bench build --app china_finance --app client_akivision`，然后清理缓存并刷新浏览器资源。

1. 进入“中国财务 -> 对账单 -> 新建对账单”。
2. 选择对账类型“客户”，确认往来类型自动为 `Customer`。
3. 选择公司、客户、起始日期和截止日期。
4. 点击“加载对账数据”，确认只出现期间内已提交、非取消、非退货送货单明细。
5. 核对明细中的送货单号、销售订单号、产品、数量、单价、金额和币种。
6. 保存对账单，确认保存成功且没有创建新订单、送货单、发票或收款单。
7. 点击“导出客户对账单 PDF”，确认下载文件、客户、期间、明细和合计与保存快照一致。
8. 客户反馈后，上传确认附件或使用“登记对账差异”；确认旧差异流程仍可用。

### 15.4 异常流程

- 不选客户、日期不完整：加载接口应阻止并提示必填；
- 起始日期晚于截止日期：提示日期错误；
- 期间无数据：提示暂无可对账数据，不生成空白明细；
- 多币种：拒绝加载并提示拆分；
- 重新加载已有未保存明细：出现替换确认；
- 手工把非送货单来源写入客户对账明细：保存校验拒绝；
- 无权限读取送货单：排除并返回原因，不泄露明细；
- 已保存非客户对账单：不显示客户 PDF 导出或接口拒绝。

### 15.5 回归测试

确认以下旧功能不受影响：

- `preview_customer_reconciliation`、`download_customer_reconciliation_pdf` 的销售订单/送货单直接导出；
- `download_reconciliation_export` 和 `download_document_export`；
- 供应商对账采购齐套校验和豁免；
- 银行对账快照、确认附件、差异登记和提交确认。

## 16. 验收标准

- 选择客户和日期后可自动列出期间内已提交送货明细；
- 明细中的订单号、送货单号、产品、数量和金额可追溯到原单据；
- 保存对账单不会创建或修改任何销售业务单据；
- 导出的 PDF 可直接发送客户，且与页面汇总一致；
- 客户有异议时可以登记差异，不需要改动原订单；
- 取消单、跨客户、跨公司、跨币种和无权限数据不会进入对账单；
- 已保存对账单作为历史快照，后续业务单据变化不会静默改变其明细。

## 17. 实际修改文件

- `development/frappe-bench/apps/china_finance/china_finance/china_finance/services/customer_reconciliation_statement.py`
- `development/frappe-bench/apps/china_finance/china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.py`
- `development/frappe-bench/apps/china_finance/china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.js`
- `development/frappe-bench/apps/china_finance/china_finance/china_finance/doctype/china_reconciliation_statement/china_reconciliation_statement.json`
- `development/frappe-bench/apps/china_finance/china_finance/china_finance/doctype/china_reconciliation_line/china_reconciliation_line.json`
- `development/frappe-bench/apps/client_akivision/client_akivision/utils/customer_reconciliation_pdf.py`
