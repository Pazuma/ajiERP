# BOM 直接更新版本实施记录

日期：2026-10-10；站点：aki_test.localhost。

## 实际效果

已提交有效 BOM 增加“版本 → 更新版本”。系统复制为可编辑草稿，同一来源重复点击复用现有草稿。保存草稿不切换默认；“保存并启用”先保存页面修改，再调用标准提交，在物料行锁内检查默认来源并切换默认。来源保留已提交、有效，只有默认标记改变。

新增来源版本及版本号字段，不使用标准 amended_from 表达有效版本更新。标准取消修订入口保留。版本记录展示新来源并按读取权限过滤。版本状态从标准 docstatus/is_active/is_default 推导，未新增冗余状态字段。

草稿工单增加“版本 → 切换到最新 BOM”，显示前后组件、用量、子 BOM 和工序时间，确认后服务端重算并保存。已提交工单、已有库存/作业记录、有补料分配、分层子工单被拒绝。工单切换是确认后立即保存，与原方案“未保存可刷新恢复”不同，页面已明确提示。

分层补料原逻辑已经优先取父 BOM 行具体 bom_no，弹窗也已展示此单号，因此本次无需重复修改 layered_manufacturing.py 或补料弹窗。父 BOM 不自动升级子 BOM；复制时保留具体引用。

## 修改文件与调用

应用根目录：development/frappe-bench/apps/client_akivision。

- client_akivision/utils/bom_version.py：字段安装、版本创建/命名、校验、启用、取消时默认恢复、差异查询、草稿工单切换。
- client_akivision/utils/bom.py：只新增新来源的命名分支，保留首版和标准修订校验。
- client_akivision/hooks.py：追加字段安装和版本 validate/before_submit/before_cancel/on_cancel 钩子，保留工程图纸校验。
- client_akivision/public/js/bom.js：更新版本、保存并启用、来源显示。
- client_akivision/public/js/work_order.js：显式切换与组件/工序对照。
- client_akivision/client_akivision/api/bom.py：原参数不变，增加来源/版本字段，权限过滤、完整分页。
- client_akivision/utils/test_bom_version.py：真实事务测试。

```text
更新版本 → create_update_version → copy_doc → 标准 insert → 新草稿
保存并启用 → 标准 save → activate_bom_version → before_submit
           → 锁物料/校验来源 → 标准 submit/manage_default_bom
草稿工单切换 → 查询默认 → get_bom_version_diff → 用户确认
             → switch_draft_work_order_bom → 标准重算 → save
```

## 完整业务流

```text
已提交 A-V1（父 BOM 行固定 B-V1、C-V1）
  ↓ 更新版本
A-V2 草稿：修改组件/数量，需要时明确更换子 BOM
  ↓ 保存草稿：A-V1 仍默认
  ↓ 保存并启用：A-V2 成为默认，A-V1 有效且非默认
  ├─ 原工单：继续 A-V1 → 按原组件领料/生产/入库
  └─ 新工单：默认 A-V2 → 按新组件领料
       ├─ 库存足够：领料 → 分批组装 → 成品入库
       └─ 半成品不足：沿用补料列表选择采购或自产
            ├─ 采购：物料申请 → 采购订单 → 质检 → 入库
            └─ 自产：按父 BOM 指定子版本建子工单
                     → 子工单领料/生产 → 半成品实际入库
                     → 父工单领用 → 组装 → 成品入库
```

上述采购、质检、库存、成本路径沿用已有实现，本次没有重写接口或库存算法，也不按新版 BOM 回算历史库存成本。

## 验证及边界

已在测试站点安装字段并清缓存。6 个测试通过，后续增加草稿工单真实创建及切换验证后，3 个新版测试再次通过；原3个测试无新增改动。覆盖草稿复制/复用、组件修改保存不切默认、标准提交切默认、旧版保留、历史工单不变、草稿工单显式切换、过期来源启用拒绝、无权限拒绝、已提交工单拒绝。全部业务测试事务回滚，没有保留测试版本或工单。

BOM/工单脚本 Node 语法检查通过，本次修改文件 diff 空白检查通过。

尚未进行浏览器点击验收、真实并发压力测试、取消恢复联调，以及 MES/财务/完整出入库端到端验收。版本列表暂未新增工单引用数量列，差异对照覆盖组件与工序，不是所有 BOM 字段的审计差异。生产计划仍用标准具体 BOM 引用，没有新增计划重新取料提示。字段安装使用定向 ensure_schema，未执行全站 migrate。

回退时关闭新增入口/钩子，保留已创建的标准 BOM 及来源字段；不得删除已引用的版本。业务回退建议创建恢复旧结构的新版本。
