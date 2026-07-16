import frappe


OLD_REPORT_NAME = "实时库存"
NEW_REPORT_NAME = "Realtime Inventory"


def execute():
    frappe.reload_doc("client_akivision", "report", "realtime_inventory", force=True)

    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET link_to = %s, label = %s
        WHERE type = 'Link' AND link_type = 'Report' AND link_to = %s
        """,
        (NEW_REPORT_NAME, NEW_REPORT_NAME, OLD_REPORT_NAME),
    )

    if frappe.db.exists("Report", OLD_REPORT_NAME):
        frappe.delete_doc("Report", OLD_REPORT_NAME, force=True, ignore_permissions=True)

    frappe.clear_cache()
