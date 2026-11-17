# 客户业务人员字段与销售团队页面精简方案

## 目标

简化客户资料页面，并将客户负责业务员维护在“详细信息”页签，供销售订单选择客户时自动带出。

目标页面效果：

1. 客户“销售团队”页签不再显示客户经理、负责业务、负责业务名称和销售团队明细表。
2. 该页签仅保留“业务人员”和“佣金率”两个字段。
3. 客户“详细信息”页签的基本资料区域，在截图红框所示右侧空位增加“业务人员”选择组件。
4. 销售订单自动关联时，只读取“详细信息”中的业务人员。

## 现状与字段澄清

当前客户页面存在三类不同性质的数据，必须区分：

| 当前页面名称 | 字段名 | 关联对象 | 后续处理 |
|---|---|---|---|
| 客户经理 | `account_manager` | `User` | 隐藏 |
| 负责业务 | `custom_responsible_sales_person` | `Sales Person` | 从销售团队页签移到详细信息，并改名为“业务人员” |
| 负责业务名称 | `custom_responsible_business_name` | 文本 | 隐藏，仅保留历史导入原文 |
| 销售团队 | `sales_team` | `Sales Team` 子表 | 隐藏，不作为客户一对一负责人维护入口 |
| 业务伙伴 | `default_sales_partner` | `Sales Partner` | 保留在销售团队页签，标签改为“业务人员（业务伙伴）” |
| 佣金率 | `default_commission_rate` | 数值 | 保留在销售团队页签 |

注意：`Sales Partner`（业务伙伴）和 `Sales Person`（业务人员）是 ERPNext 两套不同主数据：

- `Sales Partner` 通常表示渠道、代理或合作伙伴；
- `Sales Person` 表示内部业务员，并用于销售订单 `sales_team`、业绩、交付和回款统计。

因此，截图中原生“业务伙伴”字段不能直接改造成订单业务员来源。为避免两个相同标签造成误操作，页面显示建议使用：

- 详细信息：`业务人员`，关联 `Sales Person`，用于客户负责人和订单自动带出；
- 销售团队页签：`业务人员（业务伙伴）`，字段仍为 `default_sales_partner`，仅用于渠道/合作伙伴佣金；
- 佣金率：保持 `default_commission_rate`，对应业务伙伴佣金。

如果业务确认不存在渠道/代理业务，`default_sales_partner` 和 `default_commission_rate` 应一并隐藏；不能只把 `Sales Partner` 改名为“业务人员”，否则会写入错误主数据。

## 页面调整

### 详细信息页签

在基本信息区域新增或移动现有字段：

| 位置 | 字段 | 类型 | 行为 |
|---|---|---|---|
| 客户组/区域所在行的右侧空位 | `custom_responsible_sales_person` | Link / `Sales Person` | 标签为“业务人员”，可选择启用的叶子业务员 |

字段不新建第二份数据，直接复用现有 `custom_responsible_sales_person`。通过调整 Custom Field 的 `insert_after` 和字段顺序使其展示在截图红框位置，防止产生两个相同含义的客户负责人字段。

选择条件：

- 仅显示 `enabled = 1` 的 `Sales Person`；
- 排除业务员树中的组节点；
- 保存时再次服务端校验，防止接口或导入写入无效值。

### 销售团队页签

隐藏以下字段或区块：

- `account_manager`（客户经理）；
- `custom_responsible_sales_person`（已迁移至详细信息）；
- `custom_responsible_business_name`（历史导入文本）；
- `sales_team`（原生销售团队子表）；
- `sales_team_section`（销售团队表的空白区块）。

该页签只保留：

- `default_sales_partner`，显示标签为“业务人员（业务伙伴）”；
- `default_commission_rate`，显示标签为“佣金率”。

字段隐藏应使用应用内可迁移的 Property Setter 或字段布局同步函数完成，不在单个站点手工调整，保证 `aki_test.localhost` 升级和部署后仍一致。

## 与销售订单的关联

销售订单选择客户后，读取：

```text
Customer.custom_responsible_sales_person
```

并写入订单原生 `sales_team`：

```text
sales_person = 客户业务人员
allocated_percentage = 100
```

不读取：

- `default_sales_partner`；
- `default_commission_rate`；
- `custom_responsible_business_name`；
- 客户 `sales_team` 子表。

这样，订单业务员归属、业绩统计与客户“详细信息 > 业务人员”保持一条明确的数据链路。

## 数据处理

实施前执行只读核查，输出：

1. 已配置 `custom_responsible_sales_person` 的客户数；
2. 仅有 `custom_responsible_business_name` 原始文本、没有有效业务人员关联的客户；
3. 客户 `sales_team` 有数据但客户业务人员为空的客户；
4. `default_sales_partner` 已填写的客户及佣金率，用于确认渠道数据不受影响。

不删除历史字段和历史数据：

- `custom_responsible_business_name` 保留但隐藏；
- `sales_team` 表数据保留但隐藏；
- 已提交销售订单不回写；
- 客户业务人员缺失的记录进入待维护清单，不按名称自动猜测匹配。

## 验收标准

1. 客户详细信息中可看到并选择“业务人员”，且只能选择有效 `Sales Person`。
2. 客户销售团队页签不显示截图红框中的客户经理、负责业务、负责业务名称和销售团队表。
3. 销售团队页签只显示“业务人员（业务伙伴）”与“佣金率”。
4. 新建销售订单选择已配置业务人员的客户后，订单销售团队自动生成该业务员一行，贡献为 100%。
5. 修改客户的业务人员不会改变已提交订单；新建订单按新业务人员带出。
6. 业务伙伴及佣金率仍可正常保存，且不会被误作为订单业务员。
