import frappe
from frappe.model.document import Document


class ChinaTaxWorksheetSnapshot(Document):
	def validate(self):
		if not self.flags.worksheet_service:
			frappe.throw("请通过税费计算表维护底稿", frappe.PermissionError)

	def on_trash(self):
		frappe.throw("税费底稿版本不可删除")
