import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw("请先登录", frappe.PermissionError)
