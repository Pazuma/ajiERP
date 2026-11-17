"""Create costing roles before DocType role permissions are imported."""
import frappe


def execute():
    for role in ("成本报价核算员", "成本报价主管"):
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
