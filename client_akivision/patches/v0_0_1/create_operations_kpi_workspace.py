import frappe


def execute():
    """Configure the Operations desktop entry without creating a Workspace.

    The dashboard is a custom Frappe Page.  Keeping the Desktop Icon and its
    Workspace Sidebar aligned with that Page avoids an empty native Workspace
    being opened for new sites.
    """
    from client_akivision.utils.operations_management import sync_operations_management_desktop_icon

    sync_operations_management_desktop_icon()
    frappe.clear_cache()
