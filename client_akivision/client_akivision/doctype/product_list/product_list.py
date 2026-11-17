from frappe.model.document import Document

def sync_all():
	import frappe
	for name in frappe.get_all("Product List", pluck="name"):
		frappe.get_doc("Product List", name).sync_sales_item()
	frappe.db.commit()

class ProductList(Document):
	def on_update(self):
		self.sync_sales_item()

	def after_insert(self):
		self.sync_sales_item()

	def sync_sales_item(self):
		"""Mirror the inventory product into the canonical Item used by sales."""
		import frappe
		if not self.product_code:
			return
		item = frappe.db.exists("Item", self.product_code)
		if item:
			doc = frappe.get_doc("Item", self.product_code)
		else:
			group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
			uom = frappe.db.exists("UOM", "Nos") or frappe.db.get_single_value("Stock Settings", "default_stock_uom") or "Nos"
			doc = frappe.get_doc({"doctype": "Item", "item_code": self.product_code,
				"item_name": self.product_name or self.product_code, "item_group": group,
				"stock_uom": uom, "is_stock_item": 1})
		doc.item_name = self.product_name or doc.item_name or self.product_code
		doc.is_sales_item = 1
		doc.disabled = 0
		if hasattr(doc, "custom_product_name") and self.product_name:
			doc.custom_product_name = self.product_name
		if self.description and hasattr(doc, "description"):
			doc.description = self.description
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
