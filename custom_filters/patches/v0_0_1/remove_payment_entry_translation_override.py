import frappe


OLD_TRANSLATIONS = {
    "Payment Entry": "收付款单",
    "Payment Entries": "收付款单",
    "Payment Entry Deduction": "收付款单扣款",
    "Payment Entry Reference": "收付款单参考",
    "Create Payment Entry": "创建收付款单",
}


def execute():
    """Remove the obsolete database overrides so the app translation file takes over."""
    for source_text, translated_text in OLD_TRANSLATIONS.items():
        names = frappe.get_all(
            "Translation",
            filters={
                "language": "zh",
                "source_text": source_text,
                "translated_text": translated_text,
            },
            pluck="name",
        )
        for name in names:
            frappe.delete_doc("Translation", name, ignore_permissions=True, force=True)
