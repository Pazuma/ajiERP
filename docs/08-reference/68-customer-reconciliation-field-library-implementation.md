---
title: 客户对账字段库补充实施记录
---

# 客户对账字段库补充实施记录

## 本次范围

本轮按“小增量、保留旧接口”的要求，先把客户对账所需字段直接补充到现有 DocType 字段定义中。没有删除或改名既有字段，也没有修改 `preview_customer_account_statement`、旧 Delivery 分支或导出接口。

## 修改文件

| 文件 | 修改内容 |
| --- | --- |
| `china_finance_settings.json` | 增加客户对账明细视图、订单/送货、账单、收款、财务流水四组展示开关。 |
| `china_reconciliation_statement.json` | 增加期初未结账单数、期初未结账单合计、期初调整项字段。 |
| `china_reconciliation_line.json` | 增加销售发票、收款单、关联订单/送货、客户订单号、订单/送货/开票数量、原始/已结/未结金额、开票状态、收款状态和纳入原因字段。关键字段加入明细表可见列。 |
| `china_finance/setup/install.py` | 迁移时为已有公司回填展示配置默认值，并将字段加入部署结构校验。 |
| `china_finance/api.py` | 新建公司初始化时写入同一组展示配置默认值。 |

## 调用链路

```text
安装/迁移
  -> China Finance Settings 字段同步
  -> 已有公司空配置回填默认值
  -> 新建公司初始化写入默认值

客户对账单
  -> 现有“加载往来账”接口
  -> 现有 China Reconciliation Line 明细表
  -> 新增账单/订单/收款/金额字段可承载关联快照
```

## 预期效果

打开“China Finance Settings”后，可以配置客户对账明细展示范围和四类明细开关。打开“China Reconciliation Statement”后，明细表具备显示销售发票、销售订单、送货单、收款单、订单数量、已送数量、已开票数量、原始账单金额、已结金额、未结金额及状态的字段位置。

本轮只完成字段库和元数据落位，不改变现有账务计算口径。后续服务端扩展返回 `opening_documents`、`order_billing_rows` 后，可直接填入这些字段；旧接口和历史 Delivery 对账单继续可用。

## 校验

- 三个 DocType JSON 已通过 JSON 解析；
- `install.py`、`api.py` 已通过 Python 编译检查；
- 变更未删除既有字段、接口或旧分支。
