from __future__ import annotations

import re


ACCOUNT_CATALOG = {
    "1001": "库存现金",
    "1002": "银行存款",
    "1122": "应收账款",
    "1123": "预付账款",
    "1221": "其他应收款",
    "1405": "库存商品",
    "1601": "固定资产",
    "1602": "累计折旧",
    "2202": "应付账款",
    "2203": "预收账款",
    "2211": "应付职工薪酬",
    "2221": "应交税费",
    "2241": "其他应付款",
    "3001": "实收资本",
    "3104": "利润分配",
    "4104": "本年利润",
    "6001": "主营业务收入",
    "6051": "其他业务收入",
    "6301": "营业外收入",
    "6401": "主营业务成本",
    "6402": "其他业务成本",
    "6403": "税金及附加",
    "6601": "销售费用",
    "6602": "管理费用",
    "6603": "财务费用",
    "6711": "营业外支出",
    "6801": "所得税",
}

EXPENSE_RULES = [
    {"priority": 100, "patterns": [r"代发工资手续费", r"跨行.*手续费", r"余额变动提醒手续费", r"手续费", r"收费明细", r"对公收费", r"扣费"], "account": "财务费用-手续费"},
    {"priority": 95, "patterns": [r"工资", r"薪资", r"薪酬", r"代发(?!.*手续费)"], "account": "应付职工薪酬-工资"},
    {"priority": 94, "patterns": [r"社保", r"社会保险", r"社保\d+"], "account": "应付职工薪酬-社保"},
    {"priority": 93, "patterns": [r"公积金", r"住房公积金"], "account": "应付职工薪酬-公积金"},
    {"priority": 90, "patterns": [r"国库", r"税收", r"增值税", r"所得税", r"印花税", r"附加税", r"公共缴费", r"扣税"], "account": "应交税费"},
    {"priority": 80, "patterns": [r"货款", r"采购", r"供应商", r"材料", r"商品"], "account": "应付账款"},
    {"priority": 70, "patterns": [r"房租", r"租金", r"物业"], "account": "管理费用-房租"},
    {"priority": 65, "patterns": [r"运费", r"物流", r"运输"], "account": "管理费用-运输费"},
    {"priority": 60, "patterns": [r"快递", r"办公", r"耗材", r"用品", r"服务费", r"咨询费", r"技术服务"], "account": "管理费用-办公费"},
    {"priority": 55, "patterns": [r"报销", r"差旅", r"餐费", r"招待"], "account": "管理费用-报销"},
    {"priority": 40, "patterns": [r"利息"], "account": "财务费用-利息"},
]

INCOME_RULES = [
    {"priority": 95, "patterns": [r"利息"], "account": "财务费用-利息收入"},
    {"priority": 90, "patterns": [r"销售", r"收入", r"货款", r"客户", r"回款", r"收款", r"转存"], "account": "主营业务收入"},
    {"priority": 80, "patterns": [r"营业外收入", r"补贴", r"赔款"], "account": "营业外收入"},
    {"priority": 70, "patterns": [r"投资", r"股东", r"实收资本"], "account": "实收资本"},
    {"priority": 60, "patterns": [r"退款", r"退回", r"返还"], "account": "其他应收款"},
]


ACCOUNT_ROOTS = {
    "库存现金": "asset",
    "银行存款": "asset",
    "应收账款": "asset",
    "预付账款": "asset",
    "其他应收款": "asset",
    "库存商品": "asset",
    "固定资产": "asset",
    "累计折旧": "asset_credit",
    "应付账款": "liability",
    "预收账款": "liability",
    "应付职工薪酬": "liability",
    "应交税费": "liability",
    "其他应付款": "liability",
    "实收资本": "equity",
    "利润分配": "equity",
    "本年利润": "equity",
    "主营业务收入": "income",
    "其他业务收入": "income",
    "营业外收入": "income",
    "主营业务成本": "expense",
    "其他业务成本": "expense",
    "税金及附加": "expense",
    "销售费用": "expense",
    "管理费用": "expense",
    "财务费用": "expense",
    "营业外支出": "expense",
    "所得税": "expense",
}


def normalize_text(*parts):
    return " ".join(str(part or "") for part in parts).strip()


def counterparty_suffix(counterparty):
    cleaned = re.sub(r"\s+", "", str(counterparty or ""))
    if not cleaned:
        return "待确认"
    return cleaned[:24]


def base_account(account):
    return str(account or "").split("-", 1)[0]


def account_root_type(account):
    base = base_account(account)
    return ACCOUNT_ROOTS.get(base, "unknown")


def is_valid_account(account):
    if not account:
        return False
    return base_account(account) in ACCOUNT_ROOTS


def allowed_base_accounts():
    return sorted(ACCOUNT_ROOTS)


def _match_rule(compact, rules):
    ordered_rules = sorted(rules, key=lambda item: item.get("priority", 0), reverse=True)
    for rule in ordered_rules:
        for pattern in rule.get("patterns", []):
            if re.search(pattern, compact):
                return rule["account"], pattern
    return None, None


def map_transaction(summary=None, purpose=None, counterparty=None, direction="out"):
    text = normalize_text(summary, purpose, counterparty)
    compact = re.sub(r"\s+", "", text)

    if direction == "out":
        debit_account, pattern = _match_rule(compact, EXPENSE_RULES)
        if debit_account:
            return debit_account, "银行存款", f"规则匹配：{debit_account}（{pattern}）"
        if not str(counterparty or "").strip() and re.search(r"手续费|收费|扣费|服务费", compact):
            return "财务费用-手续费", "银行存款", "对方单位为空且摘要为收费类，按银行手续费归类"
        return "其他应收款-待确认", "银行存款", "未命中规则，按待确认支出处理，需人工复核"

    credit_account, pattern = _match_rule(compact, INCOME_RULES)
    if credit_account:
        return "银行存款", credit_account, f"规则匹配：{credit_account}（{pattern}）"
    if re.search(r"网转|转账|往来", compact):
        return "银行存款", "其他应付款-待确认", "转入往来款待确认，需人工复核"
    return "银行存款", "其他应付款-待确认", "未命中规则，按待确认收入处理，需人工复核"
