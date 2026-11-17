# 中国财务账簿增加“会计总账”入口方案

## 1. 背景与目标

当前“会计总账”属于会计/开票管理侧的既有页面，用户需要离开中国财务工作区才能进入。目标是在“中国财务工作台 -> 账簿”分组下增加“会计总账”入口，点击后直接跳转到现有会计总账页面，并同时显示在工作台主体卡片和左侧导航中。

本方案只调整导航元数据，不新增 DocType、数据表、查询接口或业务逻辑，确保现有会计总账页面和老接口保持不变。

## 2. 设计原则

- **复用现有页面**：仅新增一个 `Workspace Sidebar`/`Workspace` 链接，目标为现有会计总账路由或页面标识。
- **小增量修改**：优先在中国财务导航配置中新增一条分支，不重构会计总账实现。
- **兼容老接口**：不改变会计总账的查询参数、权限校验、数据来源和前端脚本。
- **迁移可重复**：通过现有 `sync_navigation_metadata` 同步，重复执行不会产生重复入口。
- **权限沿用**：入口可见性由目标页面原有角色和权限控制；无权用户打开时仍由原页面拒绝访问。

## 3. 预期修改文件

### 3.1 `development/frappe-bench/apps/china_finance/china_finance/setup/install.py`

在 `BUSINESS_NAVIGATION_GROUPS` 的“账簿”分组中增加一条链接：

```python
("General Ledger", "会计总账", "Report"),
```

经实施前核对，现有会计总账是 ERPNext `Accounts` 模块的标准脚本报表，内部标识为 `General Ledger`，链接类型为 `Report`：

```bash
bench --site <site> mariadb -e \
  "SELECT name, report_type, module FROM tabReport WHERE name='General Ledger';"
```

该入口不新建对象。同步逻辑会把同一条 `Report` 链接写入中国财务侧边栏和工作区主体。

工作台主体要求：更新“账簿”卡片的 `link_count`（现有 2 条改为 3 条），并在 `Workspace.links` 的“账簿”`Card Break` 后追加同一条 `Link`。`Workspace.content` 只保存卡片布局，卡片名称必须与 `Workspace.links` 的分组标签一致。

### 3.2 `development/frappe-bench/apps/china_finance/china_finance/workspace/china_finance/china_finance.json`

更新 fixture 中“账簿”卡片的 `link_count`，并增加对应 `Link` 项。该文件是应用安装/迁移时的静态基线，必须与 `install.py` 的导航定义一致。

示意：

```json
{
  "type": "Card Break",
  "label": "账簿",
  "link_count": 3
},
{
  "type": "Link",
  "label": "会计总账",
  "link_to": "General Ledger",
  "link_type": "Report",
  "is_query_report": 1
}
```

### 3.3 `development/frappe-bench/apps/china_finance/china_finance/workspace_sidebar/china_finance.json`

增加“账簿 -> 会计总账”侧边栏链接，保持 `indent`、`child`、`collapsible` 和图标字段与现有条目一致。工作台主体和侧边栏必须共用同一 `link_to`/`link_type`，避免出现入口名称相同但跳转目标不同。若部署流程始终由 `sync_simplified_navigation` 生成侧边栏，可将该文件作为同步后的导出结果，不在此处添加额外逻辑。

### 3.4 文档与验证（不改业务代码）

本方案文档：`docs/08-reference/30-china-finance-general-ledger-navigation-plan.md`。

## 4. 调用链路

```text
用户点击“中国财务 -> 账簿 -> 会计总账”
        |
        v
Frappe Desk 根据 link_type/link_to 解析目标
        |
        v
现有会计总账 Page/Report 的路由与前端脚本
        |
        v
原有筛选器、权限校验、查询 API、总账数据
```

部署同步链路：

```text
bench migrate
  -> 应用 fixture 同步
  -> china_finance.setup.install.after_migrate
  -> sync_navigation_metadata
  -> sync_simplified_navigation
  -> 更新 Workspace / Workspace Sidebar
  -> 清理 bootinfo、desktop_icons、站点缓存
```

## 5. 受影响模块

- **China Finance 导航**：新增一个账簿入口，工作区卡片数量从 2 增加到 3（现有现金流量指定单、对账单保持不变）。
- **Frappe Desk Workspace/Sidebar**：读取并渲染新增链接。
- **会计总账页面**：仅作为被跳转目标，代码、接口和数据查询不变。
- **权限系统**：继续使用会计总账原有权限；不复制或放宽权限。

不受影响：凭证生成、凭证快照、结账、报表计算、销售结算、税务、数据库结构及任何既有 API。

## 6. 实施步骤（后续执行）

1. 确认现有会计总账的真实 `link_to` 和 `link_type`，避免使用显示标题代替内部标识。
2. 在 `BUSINESS_NAVIGATION_GROUPS` 的“账簿”分支新增链接。
3. 同步更新 Workspace 和 Workspace Sidebar fixture。
4. 执行 `bench --site <site> migrate`，再执行导航同步和缓存清理。
5. 使用 Administrator 和普通财务角色分别验证入口可见性、跳转地址、日期/账簿筛选和无权限行为。

## 7. 验收标准

- 中国财务工作台的“账簿”分组显示“会计总账”。
- 工作台主体卡片和左侧导航都显示“会计总账”，且“账簿”卡片链接数量为 3。
- 点击后进入当前系统已有的会计总账页面，而不是新建页面。
- 原会计总账的筛选、分页、导出、权限和数据结果与原入口一致。
- 重复执行迁移不会出现重复链接或重复卡片。
- 数据库无新增表，老接口无签名或行为变化。

## 8. 风险与回滚

主要风险是目标页面内部标识确认错误，导致入口跳转失败。上线前必须用 `frappe.db.exists` 和现有菜单入口核对标识。

回滚只需移除新增导航链接并重新执行迁移/同步；不会影响会计总账页面、数据表或业务接口。
