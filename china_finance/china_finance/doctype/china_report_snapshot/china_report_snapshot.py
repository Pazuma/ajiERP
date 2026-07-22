import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class ChinaReportSnapshot(Document):
	def before_insert(self):
		self.created_on = now_datetime()
		self.created_by = frappe.session.user
		self.sha256 = hashlib.sha256(self.data_json.encode("utf-8")).hexdigest()

	def validate(self):
		old = self.get_doc_before_save()
		immutable_fields = (
			"data_json", "sha256", "template", "template_version", "report_status", "to_date",
			"comparison_from_date", "comparison_to_date", "notes", "notes_sha256", "mapping_sha256",
			"cash_scope_sha256", "validation_json", "approved_by", "approved_on",
		)
		if old and any(self.get(field) != old.get(field) for field in immutable_fields):
			frappe.throw(_("已生成的财务报表快照不可修改"))
