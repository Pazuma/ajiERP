import frappe


OLD_REPORT_NAME = "汇总计算"
NEW_REPORT_NAME = "Summary Calculation"


def execute():
    """Rename the report so Frappe can resolve its Python module path."""
    frappe.reload_doc("client_akivision", "report", "summary_calculation", force=True)

    if frappe.db.exists("Report", NEW_REPORT_NAME):
        frappe.db.set_value(
            "Report", NEW_REPORT_NAME, "report_type", "Script Report", update_modified=False
        )

    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET link_to = %s, label = %s
        WHERE type = 'Link' AND link_type = 'Report' AND link_to = %s
        """,
        (NEW_REPORT_NAME, "汇总计算", OLD_REPORT_NAME),
    )

    if frappe.db.exists("Report", OLD_REPORT_NAME):
        frappe.delete_doc("Report", OLD_REPORT_NAME, force=True, ignore_permissions=True)

    frappe.clear_cache(doctype="Report")
    frappe.cache.delete_key("report:" + OLD_REPORT_NAME)
    frappe.cache.delete_key("report:" + NEW_REPORT_NAME)
