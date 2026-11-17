import frappe
from frappe import _
from frappe.model.document import Document


class ProjectProgressReference(Document):
	def validate(self):
		row = frappe.db.get_value(
			"Project Progress Item",
			{"name": self.progress_item, "parent": self.project, "parenttype": "Project"},
			["milestone_code", "subject"],
			as_dict=True,
		)
		if not row or row.milestone_code != self.milestone_code:
			frappe.throw(_("关联的进度节点不属于项目 {0}").format(self.project))
		if not frappe.db.exists(self.reference_doctype, self.reference_name):
			frappe.throw(_("关联单据 {0} 不存在").format(self.reference_name))
		duplicate = frappe.db.exists(
			"Project Progress Reference",
			{
				"reference_doctype": self.reference_doctype,
				"reference_name": self.reference_name,
				"name": ["!=", self.name or ""],
			},
		)
		if duplicate:
			frappe.throw(_("单据 {0} 已关联其他项目进度节点").format(self.reference_name))
		self.step_name = row.subject
