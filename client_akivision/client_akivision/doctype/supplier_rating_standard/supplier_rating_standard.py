import frappe
from frappe import _
from frappe.model.document import Document


class SupplierRatingStandard(Document):
	def validate(self):
		from client_akivision.utils.supplier_rating import (
			normalize_rating_params,
			validate_rating_params,
		)

		normalize_rating_params(self)
		validate_rating_params(self)
		self.validate_schedule()
		self.validate_unique_suppliers()

	def validate_schedule(self):
		if self.rating_frequency and self.rating_frequency not in ("Weekly", "Monthly", "Quarterly"):
			frappe.throw(_("评级周期只能为每周/每月/每季度。"))
		if (self.evaluation_period_months or 0) < 0:
			frappe.throw(_("评估周期（月）不能为负。"))

	def on_update(self):
		self.sync_supplier_links()

	def on_rename(self, old_name, new_name, merge=False):
		# Keep supplier links pointing at the renamed standard.
		frappe.db.sql(
			"UPDATE `tabSupplier` SET custom_rating_standard = %s WHERE custom_rating_standard = %s",
			(new_name, old_name),
		)

	def on_trash(self):
		# Suppliers linked to a deleted standard fall back to the default config.
		frappe.db.sql(
			"UPDATE `tabSupplier` SET custom_rating_standard = NULL WHERE custom_rating_standard = %s",
			self.name,
		)

	def validate_unique_suppliers(self):
		seen = set()
		for row in self.applied_suppliers or []:
			if row.supplier in seen:
				frappe.throw(_("供应商 {0} 在本标准中重复添加。").format(row.supplier))
			seen.add(row.supplier)

	def sync_supplier_links(self):
		"""Write this standard's applied suppliers back to Supplier.custom_rating_standard.

		Suppliers removed from the list are reset to empty so they fall back to the
		default config in Buying Settings. Both this child table and the
		Supplier form write the same field, so the two entry points stay consistent.
		"""
		if not frappe.db.has_column("Supplier", "custom_rating_standard"):
			return
		current = {row.supplier for row in (self.applied_suppliers or []) if row.supplier}
		linked = set(
			frappe.db.sql_list(
				"SELECT name FROM `tabSupplier` WHERE custom_rating_standard = %s", self.name
			)
		)
		for supplier in linked - current:
			frappe.db.set_value(
				"Supplier", supplier, "custom_rating_standard", None, update_modified=False
			)
		for supplier in current:
			frappe.db.set_value(
				"Supplier", supplier, "custom_rating_standard", self.name, update_modified=False
			)
