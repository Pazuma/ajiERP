import frappe
from frappe.model.document import Document


class FinishedGoodsStatus(Document):
    def validate(self):
        if self.serial_no and not self.item_code:
            self.item_code = frappe.db.get_value("Serial No", self.serial_no, "item_code")

        if self.item_code:
            item = frappe.get_doc("Item", self.item_code)
            if not self.internal_model:
                self.internal_model = item.get("custom_internal_model")
            if not self.external_model:
                self.external_model = item.get("custom_external_model")

        if self.serial_no and not self.warehouse:
            self.warehouse = frappe.db.get_value("Serial No", self.serial_no, "warehouse")
