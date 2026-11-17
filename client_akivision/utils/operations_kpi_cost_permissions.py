"""Authorization shared by cost dashboard and export."""
import frappe


def check_cost_dashboard_access():
    from client_akivision.client_akivision.api.operations_kpi import check_dashboard_access
    check_dashboard_access()
    if frappe.session.user != "Administrator" and not set(frappe.get_roles()) & {
        "Accounts User", "Accounts Manager", "System Manager"
    }:
        frappe.throw("您没有查看财务成本看板的权限。", frappe.PermissionError)


def check_cost_company(company):
    if not company or not frappe.get_list("Company", filters={"name": company}, limit_page_length=1):
        frappe.throw("请选择有权访问的公司。", frappe.PermissionError)
