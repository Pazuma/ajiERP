import frappe
from frappe import _
from frappe.model.document import Document

from china_finance.services.archive import populate_archive_metadata


class ChinaElectronicDocument(Document):
	def validate(self):
		populate_archive_metadata(self)
		old = self.get_doc_before_save()
		if old and old.status == "Archived":
			for fieldname in ("company", "document_category", "reference_doctype", "reference_name", "file", "sha256"):
				if self.get(fieldname) != old.get(fieldname):
					frappe.throw(_("已归档电子文件不允许修改"))

