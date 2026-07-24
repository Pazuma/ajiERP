import frappe

# erpnext 原生 zh.po 中翻译不当的条目。
# 使用 Translation 记录覆盖，避免依赖各应用翻译文件的安装顺序；
# 用户翻译在 get_all_translations 合并时优先级最高。
# 幂等：已存在且译文一致时不做任何写操作。
TRANSLATION_OVERRIDES = {
    # 科目表根节点：西式会计恒等式表述，中国会计习惯直接称"资产"
    # 注意：仅对将来新建公司生效（建账时按此翻译生成根科目名），
    # 以及报表等运行时翻译该 msgid 的场景。
    # 已存在的错误科目名由 rename_legacy_asset_root_accounts patch 重命名。
    "Application of Funds (Assets)": "资产",
    # ERPNext 原生 zh.po 将 Journal Entry 翻为"日记账凭证"。
    # ERP 操作里 Journal Entry 是整张凭证，明细行才是会计分录。
    "Journal Entry": "记账凭证",
    "Journal Entries": "记账凭证",
    "Journal Entry Account": "会计分录",
    "Journal Entry Template": "记账凭证模板",
    "Journal Entry Template Account": "会计分录模板科目",
    "Journal Entry Type": "记账凭证类型",
    "Journals": "记账凭证",
    "Create Journal Entry": "创建记账凭证",
    "Create Journal Entries": "创建记账凭证",
    "Submit Journal entries": "提交记账凭证",
    "Book deferred entries via Journal Entry": "通过记账凭证登记递延分录",
    # ERPNext 原生 zh.po 将 Payment Entry 翻为"收付款凭证"；
    # 这里作为业务单据入口，统一使用更简洁的"收付款单"。
    "Payment Entry": "收付款单",
    "Payment Entries": "收付款单",
    "Payment Entry Deduction": "收付款单扣款",
    "Payment Entry Reference": "收付款单参考",
    "Create Payment Entry": "创建收付款单",
    # Bank Account 页面：ERPNext 原生中文存在"户头"、"科目"等不符合大陆业务语境的翻译。
    # 注意 Bank Account DocType 中字段源文本是 "Is Default Account"，不是通用的 "Is Default"。
    "Bank Account": "银行账户",
    "Bank Accounts": "银行账户",
    "Account Name": "银行账户名称",
    "Bank Account Type": "银行账户类型",
    "Is Default Account": "默认账户",
    "Is Company Account": "本公司银行账户",
    "Is Credit Card": "信用卡账户",
    "Account Details": "银行账户信息",
    "IBAN": "国际银行账号（IBAN）",
    "Branch Code": "银行支行代码",
    "Bank Account No": "银行账号",
    "Statement PDF Password": "银行对账单PDF密码",
}


def execute():
    for source_text, translated_text in TRANSLATION_OVERRIDES.items():
        name = frappe.db.exists(
            "Translation", {"source_text": source_text, "language": "zh"}
        )
        if name:
            current = frappe.db.get_value("Translation", name, "translated_text")
            if current != translated_text:
                frappe.db.set_value(
                    "Translation",
                    name,
                    "translated_text",
                    translated_text,
                    update_modified=False,
                )
        else:
            frappe.get_doc(
                {
                    "doctype": "Translation",
                    "language": "zh",
                    "source_text": source_text,
                    "translated_text": translated_text,
                }
            ).insert(ignore_permissions=True)
