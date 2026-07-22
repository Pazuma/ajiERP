import frappe

# 撤销 fix_zh_accounting_translations 早期版本写入的
# "Source of Funds (Liabilities)" 覆盖记录（经确认该项不需要改译）。
# 幂等：记录不存在时不做任何操作。


def execute():
    frappe.db.delete(
        "Translation",
        {"source_text": "Source of Funds (Liabilities)", "language": "zh"},
    )
