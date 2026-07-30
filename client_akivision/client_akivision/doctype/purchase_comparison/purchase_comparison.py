from frappe.model.document import Document
from frappe.utils import flt


class PurchaseComparison(Document):
	def validate(self):
		for row in self.get("rows", []):
			qty = flt(row.get("order_qty")) or flt(row.get("recommended_qty"))
			row.order_total = (
				qty * flt(row.get("recommended_rate")) if row.get("recommended_rate") is not None else None
			)
