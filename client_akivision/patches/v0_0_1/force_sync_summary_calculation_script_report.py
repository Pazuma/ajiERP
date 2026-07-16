import frappe


def execute():
    """Upgrade the existing standard report from Query to Script Report."""
    frappe.reload_doc("client_akivision", "report", "summary_calculation", force=True)
    if frappe.db.exists("Report", "Summary Calculation"):
        frappe.db.set_value(
            "Report",
            "Summary Calculation",
            "report_type",
            "Script Report",
            update_modified=False,
        )
    frappe.clear_cache(doctype="Report")
    frappe.cache.delete_key("report:Summary Calculation")
