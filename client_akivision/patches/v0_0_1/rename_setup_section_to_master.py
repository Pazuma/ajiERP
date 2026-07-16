import frappe


def execute():
    """Rename native Setup sections to Masters (translated as 主数据)."""
    for sidebar_name in ("Stock", "Selling", "Buying"):
        if not frappe.db.exists("Workspace Sidebar", sidebar_name):
            continue

        # Rename the Setup section break to Masters
        frappe.db.sql(
            """
            UPDATE `tabWorkspace Sidebar Item`
            SET label = 'Masters'
            WHERE parent = %s
              AND type IN ('Section Break', 'Card Break')
              AND label IN ('Setup', '设置')
            """,
            (sidebar_name,),
        )

    frappe.clear_cache()
