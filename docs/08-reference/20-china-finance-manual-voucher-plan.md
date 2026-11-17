---
title: 中国财务新增凭证模块方案
---

# 中国财务新增凭证模块方案

版本：v1.1  
状态：方案沉淀，暂不作为上线实现依据  
目标：在中国财务工作区增加“凭证 > 新增凭证”，界面参考众马会计的记账凭证录入形式，同时保持现有中国财务表、ERPNext 总账接口和审计快照链路不变。

## 1. 设计原则

1. 小增量：只增加一个录入页面和一个手工凭证服务，不重构既有凭证快照、报表、结账和税务模块。
2. 先新增分支：新增凭证走独立的 `manual_voucher` 服务；既有来源单据捕获、凭证账簿、冲销和补建接口继续保留。
3. 不直接写快照：`China Accounting Voucher` 是不可变审计快照，不能作为手工录入单据直接保存。新增凭证必须先创建 ERPNext `Journal Entry`，提交后由既有 hooks 生成中国凭证快照。
4. 保持老接口：不修改 `create_voucher_from_source`、`on_gl_source_submit`、`GL_SOURCE_DOCTYPES` 和现有报表接口；必要时只新增白名单方法。
5. 数据可追溯：手工凭证的正式来源为 `Journal Entry`，中国凭证的 `source_doctype` 为 `Journal Entry`，`source_event` 为 `Posting`，可继续进入总账、报表、现金流、对账和结账检查。

## 2. 预期用户效果

用户进入“中国财务 > 凭证 > 新增凭证”，看到与参考图一致的纸质记账凭证仿真录入页，而不是普通 ERP 表单：

- Desk 顶部继续使用 Frappe 全局导航；页面内部居中显示白色凭证纸，背景为浅灰色；
- 标题居中为“记账凭证”，右侧预留凭证浏览、大小切换和更多凭证操作；未实现的操作首期应隐藏或禁用；
- 抬头横向排列凭证字、字号、日期、备注/附件和附单据张数；
- 分录区默认固定显示 5 行，列顺序为行次、摘要、会计科目、借方金额、贷方金额；
- 借贷金额采用 9 位金额格，按“百、十、万、千、百、十、元、角、分”显示，元位和角分区域使用参考图中的蓝/红定位线；
- 金额格只是表示层，提交时合成为标准 Decimal 值，不新增逐位金额数据库字段；
- 合计行与借贷金额列对齐，同时显示中文大写金额，例如“合计：壹仟元整”；
- 底部显示制单人、审核人，右侧显示模板、保存、保存并新增、保存并打印和草稿/记账操作；
- 支持新增/删除分录、清空草稿、保存草稿和保存并记账；
- 记账成功后进入对应的 ERPNext `Journal Entry`，并显示生成的中国凭证字号；
- 查看凭证、凭证账簿、报表和结账时仍使用现有中国财务数据链路。

本期不承诺实现：凭证审核工作流、模板后台维护、批量复制凭证、自动生成摘要、科目常用项、打印格式重做和凭证回收站。对应按钮在功能完成前不得伪装成可用功能。

### 2.1 视觉与交互验收基线

| 区域 | 参考图特征 | 首期要求 |
| --- | --- | --- |
| 凭证纸 | 居中白底、细灰边框、浅灰背景 | 凭证纸作为唯一显式边框容器，不叠加卡片。 |
| 抬头 | 凭证字、编号、日期、附件横向排列 | 使用稳定栅格，窄屏时换行或在纸内滚动，禁止重叠。 |
| 分录 | 默认 5 行可见，行号独立 | 行高稳定，增加分录后向下扩展。 |
| 金额 | 借贷各 9 位金额格 | 固定格宽；元位及角分定位线颜色和列对齐正确。 |
| 合计 | 借贷列底部对齐 | 显示逐位合计和中文大写金额。 |
| 底部 | 制单、审核在左，命令在右 | 移动端允许换行，但不能覆盖签名信息。 |

### 2.2 金额格与分录行为

参考样式中的金额栏是会计人员快速核对位数的视觉表格，不是九个独立的业务字段。正式实现应遵循以下规则：

| 项目 | 规则 |
| --- | --- |
| 金额列 | 借方、贷方各由 9 个等宽格组成，格头依次为百、十、万、千、百、十、元、角、分；不足位数从右向左对齐并留空。 |
| 输入方式 | 用户可直接在该行借方或贷方金额区域键入普通数字金额（含小数点）；组件解析为 Decimal 后只在金额格中逐位呈现。支持退格、全选替换和粘贴标准金额。 |
| 输入限制 | 每行借贷互斥；输入借方时清空该行贷方，反之亦然。拒绝负数、超过两位小数、零金额和超过 9 位可表示范围的金额。 |
| 视觉定位 | 元位使用蓝色定位线，角/分区域使用红色定位线；颜色仅辅助读数，不能作为借贷方向或金额有效性的判断依据。 |
| 合计 | 合计金额按同样的 9 位格右对齐显示；同时将借贷总额转换为中文大写。借方总额与贷方总额不一致时，合计区显示差额提示，禁止正式记账。 |
| 默认行 | 初始固定渲染 5 条空分录，行次从 1 至 5。空行不保存为 `Journal Entry Account`。 |
| 扩展行 | 第 5 行已有内容并继续新增时，在表格底部追加第 6 行及后续行；删除中间行后重新连续编号，不收缩低于 5 条可见行。 |
| 键盘流转 | Enter 或向下键进入下一可编辑单元；在最后一条已填写行继续向下时追加新行。Tab 按摘要、科目、借方、贷方的可见列顺序流转。 |

中文大写金额应覆盖“零、壹、贰、叁、肆、伍、陆、柒、捌、玖、拾、佰、仟、万、亿、元、角、分、整”等规则；它只用于页面提示和打印展示，最终记账金额仍以 Decimal 校验结果为准。

### 2.3 草稿与命令语义

首期命令应有明确状态，避免在按钮尚无后端能力时让用户误以为已经记账：

| 命令 | 首期语义 | 调用结果 |
| --- | --- | --- |
| 保存草稿 | 仅保存浏览器会话草稿，或在二期接入 `Journal Entry` Draft；不得生成 GL Entry 或中国凭证。 | 留在当前页面，并提示草稿状态。 |
| 保存并记账 | 对完整且平衡的分录调用新增服务，创建并提交 `Journal Entry`。 | 现有钩子生成中国凭证快照，返回正式单据号。 |
| 保存并新增 | 成功记账后打开一张新的空白凭证，保留公司、日期和凭证字等可继承抬头字段。 | 不复用上张分录和金额。 |
| 保存并打印 | 仅在成功记账、已有正式 `Journal Entry` 后启用；跳转或打开对应打印格式。 | 失败或草稿状态不得打印为正式凭证。 |
| 模板/审核 | 一期若尚未实现，显示为禁用或隐藏。 | 不调用不存在的接口。 |

## 3. 建议修改文件

以下为正式实现时的文件清单。文件名采用新增文件优先，避免覆盖旧接口。

| 文件 | 类型 | 计划修改内容 |
| --- | --- | --- |
| `china_finance/services/manual_voucher.py` | 新增 | 提供页面上下文、借贷校验、公司/科目权限校验、创建并提交 `Journal Entry` 的服务。 |
| `china_finance/china_finance/page/china_new_voucher/china_new_voucher.json` | 新增 | 注册标准 Page、角色范围和页面元数据。 |
| `china_finance/china_finance/page/china_new_voucher/china_new_voucher.js` | 新增 | 实现纸质凭证布局、固定 5 行、金额逐位格转换、合计大写金额、行操作、页面调用和成功跳转。 |
| `china_finance/public/css/china_new_voucher.css` | 新增 | 实现凭证纸张、抬头横向字段、9 位借贷金额格、蓝红定位线、底部签名区和移动端滚动样式。 |
| `china_finance/hooks.py` | 最小修改 | 增加页面样式资源；如采用 Page 约定自动加载，则不增加旧 DocType hook。 |
| `china_finance/china_finance/workspace/china_finance/china_finance.json` | 最小修改 | 在“日常工作”或“凭证”分组增加 `新增凭证` Page 链接。 |
| `china_finance/services/manual_voucher.py` 对应测试文件 | 新增 | 覆盖借贷平衡、权限、公司、日期、科目和 Journal Entry 创建结果。 |

本期不修改：

- `China Accounting Voucher` 和 `China Accounting Voucher Entry` 表结构；
- `China Voucher Sequence` 编号逻辑；
- `china_finance.services.voucher.create_voucher_from_source`；
- `china_finance.services.voucher.on_gl_source_submit`；
- ERPNext `Journal Entry`、`GL Entry` 核心代码；
- 财务报表、税票、对账、现金流和结账报表接口。

## 4. 页面字段与现有表映射

| 页面字段 | 保存位置 | 说明 |
| --- | --- | --- |
| 公司 | `Journal Entry.company` | 同时决定中国财务设置、启用日期、本位币和科目范围。 |
| 凭证字 | `China Finance Settings.default_voucher_word` 作为默认值 | 首期只作为页面显示/上下文值；正式字号仍由既有凭证编号服务生成。 |
| 日期 | `Journal Entry.posting_date` | 必须不早于公司中国财务启用日期。 |
| 摘要 | `Journal Entry.user_remark`、分录 `user_remark` | 主摘要作为默认值，分录允许覆盖。 |
| 会计科目 | `Journal Entry.accounts.account` | 必须是当前公司的非组科目。 |
| 借方金额格 | `Journal Entry.accounts.debit_in_account_currency` | 前端将 Decimal 值拆为 9 个显示格，提交时合成为一个标准金额。 |
| 贷方金额格 | `Journal Entry.accounts.credit_in_account_currency` | 与借方金额互斥；逐位格不增加数据库字段，服务端再次校验。 |
| 附件张数/附件 | ERPNext `Journal Entry` 附件和 `China Electronic Document` | 首期可先保留页面数量字段；文件归档按既有电子档案服务扩展。 |
| 制单人 | `Journal Entry.owner`，快照 `prepared_by` | 不由浏览器提交用户任意指定。 |
| 审核人/记账人 | ERPNext 工作流和快照字段 | 首期沿用 Journal Entry 提交权限；启用制审分离时由既有规则阻止不合规提交。 |

## 5. 调用链路

```text
中国财务工作区
  -> 新增凭证 Page
  -> get_manual_voucher_context(company)
  -> 返回公司、本位币、启用日期、默认凭证字、当前日期
  -> 用户录入摘要、科目、借方/贷方分录
  -> 前端将金额拆为逐位格并计算合计/中文大写（仅提示，不作为安全校验）
  -> create_manual_voucher(company, posting_date, entries, remarks)
  -> 服务端重新解析参数并校验权限、公司、日期、科目、分录金额和借贷平衡
  -> 创建 ERPNext Journal Entry
  -> Journal Entry.insert()
  -> Journal Entry.submit()
  -> china_finance.services.voucher.on_gl_source_submit
  -> create_voucher_from_source(Journal Entry, Posting)
  -> 读取 GL Entry
  -> 创建并提交 China Accounting Voucher
  -> 创建 China Accounting Voucher Entry
  -> 如包含现金类科目，进入 China Cash Flow Assignment 分支
  -> 返回 Journal Entry 和中国凭证字号
  -> 前端跳转 Journal Entry 表单，可继续查看中国凭证快照
```

失败时应在创建 Journal Entry 前完成业务校验；提交后若快照生成异常，继续沿用现有 `China Voucher Sync Issue` 和补建机制，不在新接口中复制一套恢复逻辑。

## 6. 受影响模块

| 模块 | 影响方式 | 首期处理 |
| --- | --- | --- |
| 凭证 | 增加手工录入入口 | 新增 Page；底层使用 Journal Entry。 |
| 总账/账簿 | 新增 Journal Entry 产生 GL Entry | 完全复用 ERPNext 原生过账。 |
| 中国法定凭证 | 自动生成不可变快照 | 复用既有 `on_gl_source_submit`。 |
| 凭证编号 | 生成收付转记中的“记”字凭证号 | 复用 `China Voucher Sequence` 和现有分类逻辑。 |
| 现金流 | 现金科目凭证可能需要分类 | 复用 `create_assignment_if_required`，不在页面内直接写现金流表。 |
| 财务报表 | 新凭证进入 GL 后参与报表 | 不修改报表算法和映射。 |
| 对账 | 新凭证可能影响客户、供应商、银行余额 | 由现有对账服务读取 GL/凭证数据。 |
| 结账 | 新凭证受冻结日期和结账检查影响 | 继续使用 ERPNext Period Closing Voucher 和中国结账检查。 |
| 审计档案 | Journal Entry 附件可归档 | 复用电子文档哈希和档案包服务。 |
| 权限 | 增加页面访问和 Journal Entry 创建约束 | 页面角色 + 服务端 `Journal Entry` 权限双重校验。 |

## 7. 兼容与边界策略

### 7.1 老接口兼容

- 不改变所有现有白名单方法的参数和返回结构。
- 不把“手工凭证”加入来源单据捕获的特殊分支；它天然属于 `Journal Entry` 来源。
- 不直接调用或修改内部 `create_voucher_from_source` 的实现。
- 页面失败时不创建半成品 `China Accounting Voucher`；由 Frappe 事务回滚 Journal Entry。

### 7.2 权限和安全

- 页面角色：`Accounts User`、`Accounts Manager`、`China Finance Manager`、`System Manager`。
- 服务端强制检查 `Journal Entry` create 权限和 Company read 权限。
- 科目必须属于选定公司且 `is_group=0`。
- 借方/贷方每行只能填写一侧，至少两行，合计必须平衡。
- 日期不能早于中国财务启用日期。
- 不允许前端指定制单人、审核人、记账人或中国凭证字号。

### 7.3 事务和幂等

- 接口只创建一次 Journal Entry；前端重复点击应使用 freeze 状态，后续可增加幂等键。
- 中国凭证是否生成由现有 `source_key=Posting|Journal Entry|<name>` 判断。
- 快照失败不新增第二套补偿机制，沿用 `China Voucher Sync Issue`。

## 8. 测试与验收

### 8.1 后端测试

1. 正常两行借贷凭证能够创建并提交 Journal Entry。
2. 借贷不平、空科目、组科目、跨公司科目、负数和单行分录均被拒绝。
3. 日期早于启用日期被拒绝。
4. 无 Journal Entry 创建权限或无中国财务角色时被拒绝。
5. 提交后存在对应 `China Accounting Voucher` 和明细，`source_doctype` 为 `Journal Entry`。
6. 含现金科目时进入现有现金流分配待办，不在新增服务中重复创建分配逻辑。
7. 启用制审分离时，沿用既有审核规则，不绕过 `validate_source_approval`。

### 8.2 前端验收

- 页面入口在中国财务工作区可见；
- 公司切换会刷新默认币种和凭证上下文；
- 默认显示 5 行，列顺序与参考图一致；
- 借/贷各显示 9 个固定金额格，元位和角分定位线正确；
- 借贷金额互斥输入，逐位合计及中文大写金额实时更新；
- 桌面端抬头、表格和底部操作区不重叠；
- 390px 移动端凭证纸允许内容区横向滚动，页面本身无视口级溢出；
- 保存成功后显示 Journal Entry 和中国凭证字号；
- 接口错误以可读中文提示呈现，不吞掉服务端错误。

### 8.3 建议验证命令

```bash
bench --site aki_test.localhost migrate
bench --site aki_test.localhost clear-cache
bench run-tests --app china_finance --module china_finance.tests
bench build --app china_finance
```

浏览器验收地址：`http://aki_test.localhost:8300/app/china-new-voucher`。

## 9. 分阶段实施

### 一期：最小可用录入

- 新增 Page、前端表格、后端创建 Journal Entry 服务；
- 增加工作区入口和样式资源；
- 复用既有凭证快照钩子；
- 完成借贷校验、权限校验和基础测试。

### 二期：众马会计式效率功能

- 凭证模板和常用摘要；
- 科目快捷选择、最近使用和自动带出辅助核算；
- 附件上传、附件中心联动；
- 保存草稿、复制凭证、上一张/下一张。

### 三期：审核和凭证管理

- 制单/审核/记账分离工作流；
- 凭证汇总、回收站和批量打印；
- 凭证冲销入口和审计操作记录；
- 与结账、报表快照的交互式检查。

## 10. 回滚方案

一期仅新增页面、服务、样式和工作区链接。回滚时删除入口并停止调用新增服务即可，不需要删除任何业务数据。已经创建的 `Journal Entry`、`GL Entry` 和 `China Accounting Voucher` 属于正式财务记录，不应通过代码回滚删除；如需处理，应使用 ERPNext 取消/冲销流程并保留审计记录。

## 11. 结论

该方案将“众马会计式新增凭证”定位为中国财务的录入体验层，而不是重新设计一套凭证账务引擎。新增页面只负责收集和校验用户输入，正式记账仍由 ERPNext `Journal Entry` 完成，中国财务继续负责不可变凭证快照、凭证字号、现金流、报表、对账、结账和电子档案。这样可以在不改变老接口和既有表关系的前提下逐步完成界面重构。
