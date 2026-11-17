import frappe
from frappe import _
from frappe.model.rename_doc import rename_doc

from erpnext.buying.doctype.supplier.supplier import Supplier


class ManuallyNumberedSupplier(Supplier):
	"""Keep the Supplier document name equal to its manually entered code."""

	def autoname(self):
		code = str(self.get("custom_supplier_code") or "").strip()
		if not code:
			frappe.throw(_("供应商编号必填，并作为系统编号使用。"))
		self.name = code

	def validate(self):
		super().validate()
		code = str(self.get("custom_supplier_code") or "").strip()
		if not code:
			frappe.throw(_("供应商编号必填，并作为系统编号使用。"))
		self.custom_supplier_code = code

	def on_update(self):
		super().on_update()
		code = str(self.get("custom_supplier_code") or "").strip()
		if code and self.name != code:
			rename_doc(
				doctype="Supplier",
				old=self.name,
				new=code,
				ignore_permissions=False,
				show_alert=False,
			)

	def after_rename(self, old, new, merge=False):
		if not merge and self.custom_supplier_code != new:
			frappe.db.set_value("Supplier", new, "custom_supplier_code", new, update_modified=False)
			self.custom_supplier_code = new
