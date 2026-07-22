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
