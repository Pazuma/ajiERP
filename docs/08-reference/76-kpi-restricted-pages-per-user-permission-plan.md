# 指标看板受限页面按用户授权优化方案

## 1. 背景

“指标看板”侧边栏目前包含“运营指标看板”“项目节点超时表”“业务表单总表”等入口。其中以下两张表不应默认向所有能够进入指标看板的业务用户开放：

- 项目节点超时表；
- 业务表单总表。

当前两张 Page 均配置了较宽泛的财务、销售、采购、库存、生产角色。“项目节点超时表”的查询和导出复用主看板角色校验；“业务表单总表”虽然会按各业务 DocType 的读取权限决定展示类别，但没有独立的页面准入权限校验。因此，目前无法由管理员在具体用户上分别决定这两张表是否可见。

本方案只沉淀优化设计，不在本阶段修改代码、数据库或现有用户权限。

## 2. 目标与范围

### 2.1 目标

1. 管理员可在具体用户的“角色”区域逐项授权两张受限页面。
2. 未授权用户不看到对应侧边栏入口。
3. 未授权用户即使直接输入 Page 路由，也不能正常打开页面。
4. 未授权用户直接调用查询或导出接口时，后端返回权限错误，不泄露数据。
5. 授权页面后，表内数据仍遵守现有 Project 或业务单据读取权限，不因页面角色扩大数据范围。
6. 保留现有接口路径、参数、返回结构和前端调用方式，采用新增角色、新增权限辅助函数和新增判断分支实现。

### 2.2 本期范围

本期只控制：

| 页面 | 路由 | 专用角色建议名称 |
| --- | --- | --- |
| 项目节点超时表 | `project-progress-timeout` | `项目节点超时表查看者` |
| 业务表单总表 | `business-form-overview` | `业务表单总表查看者` |

`Administrator`、`System Manager` 建议保留管理兜底访问；其他用户必须获得对应专用角色。

### 2.3 非本期范围

- 不把“指标看板”新增为 Module Def，也不改变“允许模块”的语义。
- 不给 User 新增两个独立 Check 字段，避免形成标准角色之外的第二套授权数据源。
- 不调整运营指标看板现有访问角色和指标口径。
- 不改变项目节点完成逻辑、业务单据生命周期或现有导出格式。
- 不重命名现有 Page、方法、路由和响应字段。
- 技术模块名称的中文翻译作为独立本地化事项处理，不与本次权限变更耦合。

## 3. 权限模型

### 3.1 采用专用角色按人授权

管理员打开“用户”，在现有角色列表为具体用户勾选：

```text
项目节点超时表查看者
业务表单总表查看者
```

这等价于逐人选择页面是否可见，同时继续使用 Frappe 标准角色体系。暂不在 User 表单增加自定义开关，避免出现“角色已授权但开关关闭”或“开关开启但角色未授权”的双数据源冲突。

### 3.2 权限矩阵

| 用户权限 | 运营指标看板 | 项目节点超时表 | 业务表单总表 |
| --- | --- | --- | --- |
| 现有 KPI 业务角色，无专用角色 | 按现状可见 | 不可见 | 不可见 |
| 项目节点超时表查看者 | 按原角色判断 | 可见 | 不可见 |
| 业务表单总表查看者 | 按原角色判断 | 不可见 | 可见 |
| 两个专用角色 | 按原角色判断 | 可见 | 可见 |
| System Manager / Administrator | 可见 | 可见 | 可见 |

专用角色只授予对应页面入口和接口准入，不自动授予 Project、Sales Order、Payment Entry 等业务单据的读取权限。

### 3.3 四层控制

权限必须同时落在四层：

1. **用户角色层**：管理员在具体用户上分配专用角色。
2. **侧边栏层**：启动数据中按角色过滤两张受限页面的链接。
3. **Page 层**：Page 的 `roles` 只保留专用角色和管理兜底角色。
4. **API 层**：查询和导出接口在读取数据前执行独立权限校验。

侧边栏隐藏只改善体验，Page 与 API 校验才是安全边界。

## 4. 数据范围原则

### 4.1 项目节点超时表

页面角色只决定能否使用该页面。获得角色后，查询仍应通过 `frappe.get_list("Project", ...)` 获取当前用户可读取的项目，再查询这些项目的节点，保持现有 Project 权限过滤能力。

预期规则：

- 无页面角色：不返回任何数据，直接抛出 PermissionError；
- 有页面角色、无某项目读取权限：该项目及其节点不出现在结果中；
- 有页面角色且有项目读取权限：按原有公司、日期、完成和超时条件显示；
- 点击项目编号时，仍由 Project 自身权限做最终校验。

### 4.2 业务表单总表

页面角色只决定能否进入总表。获得角色后，仍沿用 `_registry()`、`frappe.has_permission(doctype, "read")` 和现有财务角色判断，不能因为获得总表角色而自动获得跨模块读取权限。

实施时还需专项复核当前原始 SQL 是否完整应用文档级 User Permission、共享和自定义 permission query conditions。若仅有 DocType 级 `has_permission` 不足以约束单条记录，应新增权限条件分支或改用权限感知查询，但不改变接口响应字段。

预期规则：

- 无页面角色：查询、筛选和导出全部拒绝；
- 有页面角色但无某 DocType 读取权限：不返回该类单据；
- 有页面角色且有 DocType 权限：仍只返回当前用户有权读取的记录；
- 财务分类继续受现有 `FINANCE_ROLES` 限制；
- 点击单据编号时，原单据权限继续生效。

## 5. 小增量实现设计

### 5.1 新增统一权限定义

建议新增轻量权限辅助模块，例如：

`client_akivision/utils/kpi_page_permissions.py`

集中定义：

```python
PROJECT_TIMEOUT_VIEWER_ROLE = "项目节点超时表查看者"
BUSINESS_FORM_OVERVIEW_VIEWER_ROLE = "业务表单总表查看者"
PRIVILEGED_ROLES = {"System Manager"}

def can_view_project_timeout(user=None): ...
def check_project_timeout_access(user=None): ...
def can_view_business_form_overview(user=None): ...
def check_business_form_overview_access(user=None): ...
```

判断函数用于菜单过滤，校验函数用于 Page 数据接口和导出接口。权限名称只在此处定义，避免多个文件硬编码后产生漂移。

`Administrator` 应显式作为兜底用户处理；不依赖其角色列表恰好包含某个业务角色。

### 5.2 幂等创建专用角色

在现有 `after_migrate` 链路中新增一个幂等同步函数，例如 `ensure_kpi_restricted_page_roles()`：

1. Role 不存在时新增；
2. Role 已存在时不覆盖管理员后续配置；
3. 不自动给现有普通用户批量授权；
4. 不删除或改名其他角色；
5. 同步两张 Page 的角色配置，确保数据库记录与标准 JSON 一致。

优先复用 `operations_management.py` 的同步入口，仅增加独立函数或调用分支；不改动现有桌面图标创建逻辑。

### 5.3 侧边栏过滤

`workspace_sidebar.ensure_operations_management_sidebar(sidebars)` 当前会向启动数据补齐两张页面链接。实施时新增按链接目标判断的过滤分支：

```text
link_to = project-progress-timeout
  -> can_view_project_timeout() 为真时保留

link_to = business-form-overview
  -> can_view_business_form_overview() 为真时保留
```

需要同时覆盖两种启动状态：

- 数据库已有 `Workspace Sidebar` 及 items；
- 启动阶段动态构造 fallback sidebar。

持久化的 Workspace Sidebar 可以继续保存完整菜单，按当前用户过滤的只应是 boot payload，避免某个用户登录时把公共菜单永久删除。

### 5.4 Page 角色调整

调整两张 Page 的标准 JSON：

- `project-progress-timeout`：保留 `System Manager`，增加 `项目节点超时表查看者`，移除宽泛业务角色；
- `business-form-overview`：保留 `System Manager`，增加 `业务表单总表查看者`，移除宽泛业务角色。

同步逻辑不能继续通过 `ICON_ROLES` 把所有业务角色重新写回 `business-form-overview`。应将“桌面指标看板入口角色”和“受限 Page 角色”拆成不同常量，避免下一次 migrate 恢复过宽权限。

前端 Page JS 不承担授权判断；后端拒绝时沿用 Frappe 权限提示。必要时只新增友好的错误展示分支，不改数据加载逻辑。

### 5.5 查询接口新增准入分支

保持旧接口不变，在入口第一行新增专用校验：

| 现有方法 | 新增处理 |
| --- | --- |
| `get_project_progress_timeout_data(filters=None)` | 将通用 `check_dashboard_access()` 替换或前置为 `check_project_timeout_access()` |
| `get_business_form_overview(filters=None, page=1, page_size=20)` | 第一行调用 `check_business_form_overview_access()` |

不修改方法名、白名单状态、参数、分页字段和响应 JSON，因此现有前端无需改调用地址。

内部计算函数 `get_project_progress_timeout_rows()` 建议继续保持非白名单纯查询函数，由公开入口负责校验；但所有可达的导出入口必须独立校验，不能假设内部函数只会被安全入口调用。

### 5.6 导出接口同步控制

| 现有方法 | 新增处理 |
| --- | --- |
| `export_project_progress_timeouts(filters=None)` | 调用 `check_project_timeout_access()` 后再生成文件 |
| `export_business_form_overview(filters=None)` | 在复用列表查询之前显式调用或依赖列表入口校验，并保留一次清晰的权限边界 |

导出与页面使用相同的数据范围。未授权用户不能通过 POST 下载文件；授权用户导出仍遵循项目和业务单据权限。

运营指标看板的 `export_kpi_dashboard()` 保持原有 `check_dashboard_access()`，不因两个独立页面角色发生变化。

## 6. 调用链路

### 6.1 用户授权链路

```text
管理员打开 User
  -> 在标准角色列表勾选一个或两个专用角色
  -> 保存 User
  -> Frappe 更新 Has Role
  -> 用户重新加载 Desk/重新登录
  -> boot_session 构造 workspace_sidebar_item
  -> kpi_page_permissions 判断当前用户角色
  -> 只返回有权访问的侧边栏链接
```

### 6.2 项目节点超时表链路

```text
用户点击“项目节点超时表”
  -> Page roles 做第一层路由限制
  -> project_progress_timeout.js
  -> get_project_progress_timeout_data(filters)
  -> check_project_timeout_access()
  -> normalise_filters(filters)
  -> get_project_progress_timeout_rows(filters)
  -> frappe.get_list("Project") 保留项目读取权限过滤
  -> 查询对应 Project Progress Item
  -> 返回分页结果

用户点击“导出 Excel”
  -> export_project_progress_timeouts(filters)
  -> check_project_timeout_access()
  -> 同一查询函数（paginate=False）
  -> 生成 XLSX
```

### 6.3 业务表单总表链路

```text
用户点击“业务表单总表”
  -> Page roles 做第一层路由限制
  -> business_form_overview.js
  -> get_business_form_overview(filters, page, page_size)
  -> check_business_form_overview_access()
  -> _registry() 按财务角色收敛表单范围
  -> has_permission / 文档权限条件过滤各 DocType
  -> 返回分页结果

用户点击“导出”
  -> export_business_form_overview(filters)
  -> check_business_form_overview_access()
  -> 复用相同查询范围
  -> 生成 CSV
```

## 7. 计划修改的文件

以下为实施阶段预计文件，不代表本方案阶段已经修改。

| 文件 | 类型 | 计划修改 | 兼容策略 |
| --- | --- | --- | --- |
| `client_akivision/utils/kpi_page_permissions.py` | 新增 | 集中定义两个角色及 can/check 辅助函数 | 新文件，不影响旧调用 |
| `client_akivision/utils/operations_management.py` | 小改 | 幂等创建角色、同步 Page roles；拆分入口角色与受限页面角色 | 保留桌面图标、主看板和侧边栏持久化逻辑 |
| `client_akivision/utils/workspace_sidebar.py` | 小改 | 对两个稳定 `link_to` 新增当前用户可见性过滤分支 | 不删除数据库菜单，不改其他侧边栏过滤 |
| `client_akivision/hooks.py` | 小改或不改 | 若不复用现有同步函数，则在 `after_migrate` 追加角色同步函数 | 只追加钩子，不调整旧钩子顺序 |
| `client_akivision/client_akivision/page/project_progress_timeout/project_progress_timeout.json` | 修改 | Page roles 收敛为专用角色与管理角色 | 路由、标题、模块不变 |
| `client_akivision/client_akivision/page/business_form_overview/business_form_overview.json` | 修改 | Page roles 收敛为专用角色与管理角色 | 路由、标题、模块不变 |
| `client_akivision/client_akivision/api/operations_kpi.py` | 小改 | 超时表公开接口新增专用权限校验 | 参数和返回结构不变，主看板接口不变 |
| `client_akivision/client_akivision/api/operations_kpi_export.py` | 小改 | 超时表独立导出新增专用权限校验 | 主看板 Excel 导出不变 |
| `client_akivision/client_akivision/api/business_form_overview.py` | 小改 | 查询与 CSV 导出新增准入校验；复核文档级权限条件 | 方法名、筛选和响应字段不变 |
| `client_akivision/tests/test_kpi_restricted_page_permissions.py` | 新增 | 覆盖角色、菜单、查询、导出和数据范围 | 独立测试，不改旧测试断言 |
| `client_akivision/docs/运营指标看板人工测试顺序.md` | 修改 | 增加逐人授权和越权访问验收 | 仅追加步骤 |

前端 `project_progress_timeout.js` 和 `business_form_overview.js` 预计无需改动。只有在实测发现 Page 权限错误未被 Frappe 统一处理时，才新增最小错误提示分支。

## 8. 关联修改与一致性要求

实施时必须同步处理以下关联点，不能只改侧边栏：

1. 标准 Page JSON 与数据库 Page roles 一致；
2. `operations_management.py` 不再通过 `ICON_ROLES` 恢复宽泛 Page roles；
3. boot payload 中已有菜单和 fallback 菜单都执行同一权限判断；
4. 页面查询和导出使用同一专用角色；
5. 业务总表查询、筛选、分页和 CSV 导出保持同一数据范围；
6. 超时表分页查询和全量 Excel 导出保持同一项目权限范围；
7. 缓存处理覆盖 `bootinfo`、桌面图标和 Workspace Sidebar，角色变更后重新加载可生效；
8. 管理角色兜底规则在菜单、Page 和 API 三处一致；
9. 角色名称新增中文翻译通常不需要额外映射；若界面仍出现英文技术名称，再单独补翻译，不与授权逻辑混写。

## 9. 兼容与迁移策略

### 9.1 不改老接口

以下保持不变：

- `/api/method/...get_project_progress_timeout_data`；
- `/api/method/...export_project_progress_timeouts`；
- `/api/method/...get_business_form_overview`；
- `/api/method/...export_business_form_overview`；
- 现有 filters、page、page_size 参数；
- 现有响应字段、分页结构和下载格式。

只在方法入口新增授权分支。

### 9.2 现有用户迁移

上线后默认采用“最小权限”：普通业务角色不再自动看到两张受限表。实施前应由业务方提供授权名单，迁移脚本原则上不根据旧的宽泛角色自动赋予新角色。

如必须保证特定管理人员上线无感，可另外准备显式白名单映射，但名单应作为部署配置或一次性迁移输入，不写死在通用代码中。

### 9.3 回滚边界

若需要回滚：

- 恢复 Page 原 roles；
- 移除 API 入口的专用校验分支；
- 移除 boot payload 的两个链接过滤分支。

专用 Role 可保留为空角色，不必删除，避免已分配用户产生引用问题。所有业务数据、项目节点和导出内容均无需回滚。

## 10. 风险与处理

| 风险 | 表现 | 处理 |
| --- | --- | --- |
| 只隐藏菜单 | 直接 URL/API 仍能获取数据 | Page 与 API 同时校验 |
| migrate 恢复宽泛角色 | 权限收敛后再次放开 | 拆分 `ICON_ROLES` 与 Page roles |
| 角色变更后菜单未刷新 | 用户仍看到旧入口 | 清 boot 缓存并要求刷新 Desk；同步函数清相关缓存 |
| 业务总表跨权限泄露 | 有页面角色后看到无权单据 | 复核并补齐文档级权限条件，不只检查 DocType read |
| 导出绕过页面 | 未授权用户直接下载 | 每个导出入口独立调用 check 函数 |
| 自动给旧用户授权过宽 | 原业务角色全部继承受限表 | 默认不批量授权，按确认名单分配 |
| 专用角色看不到指标看板入口 | 用户只有专用角色但不在 `ICON_ROLES` | 明确产品口径：专用角色也应使“指标看板”桌面入口可见，但只显示获权页面；同步扩展图标/侧边栏入口条件 |
| System Manager 口径不一致 | 菜单可见但 API 拒绝 | 管理兜底角色集中定义并复用 |

## 11. 测试与验收

### 11.1 自动测试

至少覆盖以下组合：

1. 无专用角色：两个菜单均不存在，四个查询/导出入口均返回 PermissionError。
2. 只有超时表角色：只显示超时表；超时查询和导出成功，业务总表查询和导出拒绝。
3. 只有业务总表角色：只显示业务总表；业务查询和导出成功，超时查询和导出拒绝。
4. 两个角色都有：两个入口和接口均可用。
5. System Manager / Administrator：保持全部可用。
6. 有超时表角色但无某 Project 权限：结果和导出均不包含该项目。
7. 有业务总表角色但无财务角色：财务分类不出现。
8. 有总表角色但无某业务 DocType 或单据读取权限：列表和导出均不包含对应数据。
9. 角色被撤销并清缓存后：菜单消失，旧页面刷新和旧下载请求立即拒绝。
10. 主运营指标看板及其 Excel 导出保持原权限和结果。

### 11.2 人工验收

准备四个非管理员测试用户，分别配置零个、超时表、业务总表、两个专用角色，验证：

- 用户页可以清楚勾选并保存专用角色；
- 左侧菜单组合正确，无空白分组或错位；
- 直接输入两个路由不能绕过权限；
- 浏览器直接调用查询和导出方法不能绕过权限；
- 页面筛选、分页、刷新和导出保持原行为；
- 单据链接只在原单据可读时可用；
- 手机和桌面端菜单均按相同权限隐藏；
- 撤销角色后刷新会话即可生效。

## 12. 预期效果

实施后，管理员无需修改“允许模块”，可以直接在具体用户的标准角色区域决定两张表的可见性。

```text
普通 KPI 用户
指标看板
└── 运营指标看板

授予“项目节点超时表查看者”
指标看板
├── 运营指标看板（若原角色允许）
└── 项目节点超时表

授予“业务表单总表查看者”
指标看板
├── 运营指标看板（若原角色允许）
└── 业务表单总表
```

最终应达到：菜单不暴露、路由不可绕过、接口和导出不泄露、页面角色不扩大底层业务数据权限，同时不破坏主运营指标看板和现有业务流程。

## 13. 实施前待确认

1. 两个角色最终中文名称是否采用“项目节点超时表查看者”“业务表单总表查看者”。
2. `System Manager` 是否自动拥有两张表，还是也必须逐项授权。本方案建议自动拥有。
3. 只有专用页面角色、没有原 KPI 业务角色的用户，是否需要看到“指标看板”桌面入口。本方案建议需要，并只显示获权页面。
4. 业务表单总表是否严格遵循单条文档权限。本方案建议严格遵循，不能只做 DocType 级权限。
5. 上线时现有用户是否全部默认不授权，再由管理员按名单配置。本方案建议默认不授权。

