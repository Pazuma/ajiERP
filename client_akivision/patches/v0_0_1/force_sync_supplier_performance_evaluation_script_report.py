import frappe


def execute():
    frappe.reload_doc("client_akivision", "report", "supplier_performance_evaluation", force=True)
    frappe.clear_cache()
