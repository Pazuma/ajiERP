"""Financial report authorization independent of operational dashboard access."""
import frappe


def check_report_access():
    if frappe.session.user != "Administrator" and not set(frappe.get_roles()) & {
        "Accounts User", "Accounts Manager", "System Manager"
    }:
        frappe.throw("您没有查看财务成本汇总表的权限。", frappe.PermissionError)
