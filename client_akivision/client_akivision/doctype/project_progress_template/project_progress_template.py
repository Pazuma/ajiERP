import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ProjectProgressTemplate(Document):
	def validate(self):
		used = {row.milestone_code for row in self.items if row.milestone_code}
		next_number = 1
		for row in self.items:
			if row.milestone_code:
				continue
			while f"STEP-{next_number:03d}" in used:
				next_number += 1
			row.milestone_code = f"STEP-{next_number:03d}"
			used.add(row.milestone_code)
			next_number += 1
		codes = [row.milestone_code for row in self.items]
		if len(codes) != len(set(codes)):
			frappe.throw(_("模板节点编码不能重复"))
		for row in self.items:
			if flt(row.weight) <= 0:
				frappe.throw(_("节点 {0} 的权重必须大于零").format(row.subject))
			if row.end_day_offset < row.start_day_offset:
				frappe.throw(_("节点 {0} 的完成日偏移不能早于开始日偏移").format(row.subject))
			if row.completion_rule == "Document Submitted" and not row.reference_doctype:
				frappe.throw(_("节点 {0} 必须选择关联表单").format(row.subject))
		if self.items and abs(sum(flt(row.weight) for row in self.items) - 100) > 0.01:
			frappe.throw(_("模板节点权重合计必须等于 100%"))
