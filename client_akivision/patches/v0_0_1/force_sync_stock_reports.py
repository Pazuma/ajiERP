import frappe


def execute():
    for report_name in ("summary_calculation", "realtime_inventory"):
        frappe.reload_doc("client_akivision", "report", report_name, force=True)

    frappe.clear_cache()
