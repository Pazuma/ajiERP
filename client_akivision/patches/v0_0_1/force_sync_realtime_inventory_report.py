import frappe


def execute():
    frappe.reload_doc("client_akivision", "report", "realtime_inventory", force=True)
    frappe.clear_cache()
