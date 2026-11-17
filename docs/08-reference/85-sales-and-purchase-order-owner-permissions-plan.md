# 销售与采购订单按业务负责人隔离查看最终优化方案

## 1. 文档目的

本文沉淀并明确最终实施口径：“业务人员使用自己的账号新建销售订单后，只能查看归属自己的销售订单；采购专员只能查看归属自己的采购订单。”本阶段只形成方案，不修改业务代码、数据库、站点字段或用户权限。

目标不是只隐藏列表记录，而是让记录级权限统一覆盖列表、直接打开、搜索、报表、导出及自定义接口读取。方案采用小增量实现：保留 ERPNext 标准角色权限、订单流程和现有接口契约，在自定义 app 中追加记录级权限分支，并补齐采购订单明确的负责人字段。

## 2. 已核实的站点现状

核实对象为本地运行的 `aki_test.localhost` 开发站点，版本为 Frappe/ERPNext 16.23.0。站点安装 `client_akivision` 等自定义应用。

### 2.1 销售订单

- 标准 `Sales Order` 使用原生 `sales_team` 子表，子表 `Sales Team.sales_person` 链接 `Sales Person`。
- 站点另有自定义字段 `Sales Order.custom_sales_person`，类型为 Link，目标为 `Sales Person`。
- 客户上有 `Customer.custom_responsible_sales_person`，类型为 Link，目标为 `Sales Person`。
- `Sales Person.employee` 链接 `Employee`；`Employee.user_id` 链接 `User`，可组成“登录用户 -> Employee -> Sales Person”的关联链路。
- `client_akivision.utils.sales_order_fields` 在保存前可从客户负责人补订单业务员，并在订单为空时补一条原生销售团队行；提交前会验证业务员。该逻辑维护归属数据，不负责限制订单读取。

### 2.2 采购订单

- 当前 `Purchase Order` 的标准字段及站点自定义字段中未发现采购专员/采购负责人 Link 字段。
- 现有采购订单自定义字段包括来源采购申请、采购比价、供应商汇总标记等，但它们不是人员归属字段。
- 标准 `owner` 表示创建记录的用户，不能可靠代表采购专员，尤其是导入、集成接口、代录或管理员创建的订单。
- `Employee.user_id` 可用作用户与员工的关联基础；建议新增采购负责人字段指向 Employee，以复用明确的人事主数据关系。

### 2.3 权限现状

- 当前 `client_akivision` 的 `permission_query_conditions` 和 `has_permission` 仅注册 Item、Item Price 的自定义权限，不包含 Sales Order 或 Purchase Order。
- 销售订单和采购订单的标准角色权限目前为 DocType/操作级授权；例如 Sales User、Sales Manager、Purchase User、Purchase Manager、Stock User 等角色拥有不同程度的订单读取权限。
- 站点已有报表、导出和 API 直接查询订单的实现。只新增列表过滤不足以形成安全边界，必须逐项审计其查询是否经过 Frappe 权限感知入口。

## 3. 目标和权限边界

### 3.1 目标

1. 普通销售人员新建订单时，订单业务员默认且服务端限定为当前登录账号关联的 `Sales Person`；其只能查看该业务员归属的订单。
2. 采购专员新建订单时，采购专员默认且服务端限定为当前登录账号关联的 Employee；其只能查看分配给自己的采购订单。
3. 列表、搜索、打开单据、标准导出以及自定义查询/导出接口遵守同一记录级规则。
4. 管理角色和明确授权的跨部门角色可按确认后的权限矩阵访问全部记录。
5. 不改变订单创建、提交、审批、收货、开票、结算、库存记账及现有 API 参数/返回结构。

### 3.2 建议的记录归属规则

| 单据 | 归属依据 | 普通人员可见范围 | 特殊情况建议 |
| --- | --- | --- | --- |
| Sales Order | `custom_sales_person` 与原生 `sales_team.sales_person` | 与当前 User 关联的 Sales Person 在订单负责人字段或团队成员中出现 | 多人销售团队任一成员可见；无归属的历史单据普通销售用户不可见，由销售管理角色核查 |
| Purchase Order | 新增 `custom_procurement_specialist`，Link 到 Employee | 字段对应 Employee 的 `user_id` 等于当前 User | 未分配订单只对采购管理/授权角色可见，并进入待补负责人清单 |

销售订单归属以登录账号关联的业务员为准，而不是客户资料中的默认业务员。普通 Sales User 新建订单时，当前账号关联的 `Sales Person` 是权威默认值；客户端可显示该值，服务端保存前必须再次写入/校验，普通销售用户不能把订单改归其他业务员。客户负责人只用于提示或管理角色代办，不得覆盖普通销售用户身份。订单保存后的可见范围以订单自身已保存字段及团队数据为准，避免客户负责人变更后历史单据归属漂移。

### 3.3 管理角色与跨模块角色

必须在实施前确认角色矩阵。建议明确区分：

- 可看个人记录的业务角色：Sales User、Purchase User 等实际岗位角色；
- 可查看该模块全部记录的管理角色：Sales Manager、Purchase Manager；
- 财务、库存、生产等确实需要全量订单的跨模块岗位，通过明确的全量查看角色授予，不由任意 DocType 读取角色隐式放行；
- `Administrator` / `System Manager` 保留管理兜底。

不要采用“只要用户还有任意一个能读该 DocType 的角色就跳过过滤”的判断方式，否则给销售人员附加 Accounts User 或 Stock User 角色可能无意扩大订单范围。全量访问应来自明确的受信角色清单或用户权限配置。

## 4. 小增量实现设计

### 4.1 统一记录权限服务

建议新增 `client_akivision/utils/order_record_permissions.py`，集中提供：

- 当前用户可关联的 Sales Person / Employee 解析；
- Sales Order 列表查询条件构造；
- Sales Order 单据级 `has_permission` 判断；
- Purchase Order 列表查询条件构造；
- Purchase Order 单据级 `has_permission` 判断；
- 受信全量查看角色判断；
- 未绑定人员或订单无负责人时的安全默认处理。

不要在多个 Hook、报表、导出文件内各自实现一套角色判断。权限服务只负责规则；业务事件负责填充归属字段；前端脚本只负责默认值和提示，不作为安全边界。

### 4.2 Frappe 权限 Hook

在 `client_akivision/hooks.py` 中给现有字典增量追加 Sales Order、Purchase Order：

- `permission_query_conditions`：为普通用户的列表和权限感知查询附加负责人条件；
- `has_permission`：检查单条订单是否属于当前用户，覆盖直接打开和单据级操作权限判断。

保留现有 Item、Item Price Hook，不替换现有字典。必须确认 Hook 函数正确返回 SQL 条件、对角色/未登录/系统用户处理正确，并使用参数化条件或安全的用户标识，不拼接不受信任输入。

注意：Frappe 的 `permission_query_conditions` 主要约束权限感知列表查询，不会自动保护绕过权限的 `frappe.get_all`、任意 SQL 或自定义聚合。因此 API/报表仍须逐一确认并补充权限校验。

### 4.3 采购负责人字段与默认值

最终方案新增字段：

| DocType | 字段名 | 标签 | 类型 | 选项 |
| --- | --- | --- | --- | --- |
| Purchase Order | `custom_procurement_specialist` | 采购专员 | Link | Employee |

实施时通过现有自定义字段配置/安装同步机制创建字段，避免手工只改一个站点。采购订单新建时按当前 `User -> Employee` 关系默认带出当前用户对应员工；普通 Purchase User 不能将订单指派给其他员工，采购管理角色可代办并指定负责人。保存时由服务端验证字段、员工有效性、用户映射及修改权限。导入/API 未提供负责人时不静默归属系统用户：普通用户创建的订单应由服务端按调用用户映射补齐；无法映射的集成账号只能由明确授权的管理入口指定负责人，否则拒绝提交，草稿可按管理策略进入待分配清单。

负责人字段修改后只改变后续读取范围，不回写 `owner`、创建人或历史流程记录。已提交订单的负责人变更应按权限和审计要求限制，仅授权管理角色可改，并记录变更。

### 4.4 销售订单归属兼容

- 优先沿用 `custom_sales_person`，同时兼容原生 `sales_team`，不新增重复的销售负责人字段。
- 新建订单的 `custom_sales_person` 优先由当前 User 对应的 Sales Person 设置；客户默认负责人不能覆盖当前业务人员身份。
- 多业务员归属按团队“任一成员可见”执行；团队成员在 `sales_team` 中有记录即可查看该订单。
- 若 `custom_sales_person` 与 `sales_team` 不一致，建议使用两者并集确保实际参与人员不被误隐藏，并生成数据审计报告；如业务要求以单一字段为准，应先统一历史数据规则。
- 普通 Sales User 保存时不得将 `custom_sales_person` 或 `sales_team` 改成其他人员；只有 Sales Manager 等明确全量角色可以代办/调整归属。

## 5. 预计修改文件

下表为依据当前站点源码推定的实现位置；实际开发时须以目标部署分支和安装包目录为准。本次没有修改这些文件。

| 文件/位置 | 变更类型 | 预计内容 |
| --- | --- | --- |
| `apps/client_akivision/client_akivision/hooks.py` | 修改 | 在现有权限 Hook 中追加两个订单 DocType；保留现有 Item、Item Price 权限配置 |
| `apps/client_akivision/client_akivision/utils/order_record_permissions.py` | 新增 | 用户映射、个人归属过滤、管理角色兜底和单据级校验的统一服务 |
| `apps/client_akivision/client_akivision/utils/sales_order_fields.py` | 修改 | 普通 Sales User 新建/保存订单时以当前 User 映射的 Sales Person 覆盖客户默认值；经理代办继续走显式负责人设置；保留其他订单字段同步逻辑 |
| `apps/client_akivision/client_akivision/config/excel_form_fields.json` 或现有字段同步配置 | 修改 | 声明 `Purchase Order.custom_procurement_specialist`，保证站点可迁移/同步 |
| `apps/client_akivision/client_akivision/utils/purchase_order_fields.py` | 新增或扩展 | 采购订单默认负责人、服务端归属校验、已提交单据修改约束；如已有等价模块则增量扩展 |
| `apps/client_akivision/client_akivision/hooks.py` 中 Purchase Order `doc_events` | 修改 | 追加保存前校验/默认逻辑，不覆盖现有事件处理 |
| `apps/client_akivision/client_akivision/public/js/purchase_order_owner.js` | 新增 | 当前用户默认采购专员、字段显示和提示；不承载授权判断 |
| `apps/client_akivision/client_akivision/hooks.py` 中 `doctype_js` | 修改 | 追加 Purchase Order 客户端脚本，保留已有脚本加载 |
| `apps/client_akivision/client_akivision/utils/test_order_record_permissions.py` | 新增 | 用户映射、团队成员、多角色、普通用户不能指派他人、未绑定、未分配、管理角色和直接单据权限测试 |
| `apps/client_akivision/client_akivision/utils/test_purchase_order_fields.py` | 新增 | 默认负责人、接口/导入、字段缺失、代办和提交校验测试 |
| 受影响报表/API/导出模块 | 逐项增量修改 | 在原查询路径增加统一权限校验或改为权限感知查询；不改变方法参数和响应字段 |

字段迁移应使用该仓库既有的配置/patch 规范。若字段配置会被安装器自动同步，需确认其同步行为是否会覆盖管理员运行时设置；避免未经评估地全量同步其他字段。

## 6. 调用链路

### 6.1 销售订单列表与直接打开

```text
用户登录
  -> 解析 User -> Employee -> Sales Person
  -> Frappe Sales Order 列表读取
  -> permission_query_conditions 附加负责人/团队条件
  -> 列表只返回匹配订单

用户打开某张 Sales Order
  -> Frappe 单据权限检查
  -> has_permission 校验 custom_sales_person / sales_team
  -> 属于本人或明确全量角色：允许；否则拒绝
```

### 6.2 采购订单创建、列表与读取

```text
用户新建 Purchase Order
  -> 由当前 User 查找 Employee
  -> 前端可默认采购专员；服务端保存前再次验证
  -> 保存 custom_procurement_specialist

用户读取 Purchase Order
  -> permission_query_conditions 按 Employee.user_id 过滤列表
  -> has_permission 校验单张订单
  -> API/报表/导出显式调用同一权限服务或使用权限感知查询
```

### 6.3 自定义查询和导出

```text
现有 API/报表/导出入口
  -> 先校验 DocType 操作权限
  -> 获取订单集合时应用记录级权限
  -> 若逐单读取/导出，再执行单据级权限检查
  -> 保持原有参数、筛选语义和响应结构
```

客户端隐藏列表、按钮或字段只是体验优化，不能替代服务端检查。已有按原始 SQL 汇总的报表必须把订单范围条件下推到 SQL，不能先读取全量数据再仅在页面隐藏。

## 7. 受影响模块与关联部分

### 7.1 必须纳入本期审计

- Desk 原生 Sales Order / Purchase Order 列表、搜索、全局搜索及直接路由打开；
- 标准导出、已选单据导出、PDF/Excel 自定义导出；
- `business_form_overview` 等使用 SQL/`frappe.get_all` 汇总订单的页面；
- `sales_order_list`、销售履约与成本等读取 Sales Order 的自定义报表/API；
- Purchase Order 对账、采购进度、供应商合并下单、采购质量/收货等读取订单的服务；
- 订单转换/链接选择器，例如从订单创建 Delivery Note、Purchase Receipt、Purchase Invoice 或关联查询来源订单的接口。

### 7.2 关联单据处理原则

- 本期的核心授权对象是 Sales Order 和 Purchase Order，不自动改变 Delivery Note、Sales Invoice、Purchase Receipt、Purchase Invoice、Payment Entry 等 DocType 的既有权限矩阵。
- 但任何自定义接口若通过关联单据返回订单编号、金额、客户/供应商或订单明细，必须确保其读取订单时遵守本方案，避免关联页面成为旁路。
- 从订单生成下游单据时，服务端先校验来源订单读/写权限；下游单据自身继续使用原有权限。不能仅因用户看不到订单就破坏已经授权的收货、发货、开票和财务流程。
- 报表和导出应分别定义口径：若报表读取的是订单事实，使用订单范围；若角色确实需要汇总全公司数据，应单独授权该报表并避免暴露无关订单明细。

## 8. 数据准备与上线步骤

1. 按本文默认口径建立角色矩阵：普通业务角色个人可见、经理和明确授权的跨模块角色全量可见；多人销售订单对团队任一成员可见。
2. 只读盘点 Employee.user_id 与 Sales Person.employee 的重复/缺失关系，并统计订单业务员为空、字段与团队不一致的记录；不自动猜测归属。
3. 新增采购负责人字段；未分配订单对普通采购用户不可见，采购管理角色负责补齐归属，缺少负责人不得由系统账号静默提交。
4. 实现统一权限辅助服务、Hook 和采购字段默认/校验逻辑。
5. 审计并补齐所有订单 SQL、报表、导出、API 和关联选择器；接口签名与响应结构保持不变。
6. 在测试站点迁移字段并为测试账号配置角色和 User/Employee/Sales Person 关联。
7. 执行单元/集成测试及多角色浏览器验收，核对性能与 SQL 执行计划后再安排生产发布。
8. 上线前导出权限配置和待补归属清单；上线后抽查拒绝日志、列表数量、导出数量及下游流程。

## 9. 预期效果

- 销售人员登录后，Sales Order 列表及相关搜索只显示其本人业务员身份出现在订单归属/销售团队中的订单；直接打开无权订单会被服务端拒绝。
- 采购专员登录后，Purchase Order 列表、直接打开、导出和自定义接口只返回分配给该专员的订单。
- 销售经理、采购经理及经确认的跨模块授权角色可以按矩阵访问团队/全量订单；普通用户叠加无关角色不会意外绕过个人范围。
- 未关联用户的 Sales Person、采购订单未分配负责人、历史归属冲突记录不会被猜测性归属；按确认策略限制普通用户并提供管理核查清单。
- 订单创建、提交、审批、导入、采购收货、销售发货、结算及既有接口契约保持不变；增加的负责人默认仅作用于明确符合条件的新建流程。
- 无权订单不通过列表分页、全局搜索、报表聚合、批量导出或关联接口泄露。

## 10. 验收场景

1. 销售 A 关联 Sales Person A；单人订单 A 可见，业务员 B 不可见。
2. 多人销售团队订单分别用成员 A、成员 B 登录验证；结果符合最终确认的团队可见策略。
3. 销售用户直接输入他人订单路由、调用标准读取接口，均被拒绝；无权限用户导出被选订单失败且不泄露部分数据。
4. 采购 A 新建订单后负责人默认为 A；采购 B 看不到，采购 A 可见并可按授权编辑。
5. 导入/API 使用系统账号创建采购订单时，不将系统账号错误写为采购专员；缺少负责人按确认策略处理。
6. 普通用户额外拥有 Accounts User 或 Stock User 等角色时，仍按权限矩阵限制，不发生隐式全量访问。
7. Sales Manager、Purchase Manager、System Manager 及财务等授权角色的全量/团队范围与最终矩阵一致。
8. 历史订单归属为空、负责人无 User 映射、销售字段与团队不一致时符合安全默认规则，并可由管理角色核查。
9. 报表、业务表单总表、自定义 Excel/PDF 导出和关联单据选择器不会显示或聚合超范围订单。
10. 销售履约、采购收货、发票、付款、库存与审批流程回归通过；现有接口参数和返回字段未变。

## 11. 最终实施口径与上线前检查

本方案默认采用以下规则，实施时不再把它们留作开放式设计问题：

1. Sales User / Purchase User 等普通业务账号只看本人归属订单；新建时负责人自动取当前账号映射的业务人员/员工，服务端拒绝普通用户指派给他人。
2. Sales Order 多人团队任一 `sales_team` 成员可见；`custom_sales_person` 与团队归属使用并集判断，历史冲突不自动改写。
3. Sales Manager / Purchase Manager 可查看并管理模块全量订单；`Administrator` / `System Manager` 保留兜底。财务、库存等跨模块全量访问必须配置明确授权角色。
4. 空归属订单普通用户不可见；采购集成账号未映射负责人时不得静默提交，进入管理补齐/授权代办流程。
5. 列表、直接打开、标准接口、自定义报表/导出及关联查询执行同一记录范围；API 签名和响应结构保持兼容。
6. 普通业务账号必须唯一映射到有效 Employee；销售人员对应唯一有效 Sales Person。上线盘点发现缺失或一对多映射时先修正配置，不在权限代码里猜测归属。

上线前仍需执行数据盘点、目标分支文件核对、角色实际分配确认和跨模块授权名单整理。这些是部署准备，不改变本文已确定的记录可见规则。本阶段仍只沉淀文档，不修改业务代码、数据库或站点权限。
