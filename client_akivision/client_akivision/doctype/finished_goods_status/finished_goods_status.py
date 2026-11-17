import frappe
from frappe import _
from frappe.model.document import Document


class FinishedGoodsStatus(Document):
    def validate(self):
        self._set_serial_no_details()
        self._set_item_details()
        self._set_contact_details()
        self._set_work_order_details()

    def _set_serial_no_details(self):
        if not self.serial_no:
            return

        serial_no = frappe.db.get_value(
            "Serial No", self.serial_no, ["item_code", "warehouse"], as_dict=True
        )
        if not serial_no:
            frappe.throw(_("序列号 {0} 不存在").format(self.serial_no))
        if self.item_code and self.item_code != serial_no.item_code:
            frappe.throw(_("物料编码必须与序列号 {0} 的物料一致").format(self.serial_no))
        self.item_code = serial_no.item_code
        self.warehouse = serial_no.warehouse or self.warehouse

    def _set_item_details(self):
        if not self.item_code:
            return
        item = frappe.db.get_value(
            "Item",
            self.item_code,
            ["custom_internal_model", "custom_external_model"],
            as_dict=True,
        )
        if not item:
            frappe.throw(_("物料 {0} 不存在").format(self.item_code))
        self.internal_model = item.custom_internal_model
        self.external_model = item.custom_external_model

    def _set_contact_details(self):
        if not self.contact_person:
            self.phone = None
            return
        if self.customer and not frappe.db.exists(
            "Dynamic Link",
            {
                "parenttype": "Contact",
                "parent": self.contact_person,
                "link_doctype": "Customer",
                "link_name": self.customer,
            },
        ):
            frappe.throw(_("联系人 {0} 不属于客户 {1}").format(self.contact_person, self.customer))
        self.phone = frappe.db.get_value(
            "Contact", self.contact_person, "mobile_no"
        ) or frappe.db.get_value("Contact", self.contact_person, "phone")

    def _set_work_order_details(self):
        if not self.work_order_no:
            self.work_order_status = None
            return
        self.work_order_status = frappe.db.get_value("Work Order", self.work_order_no, "status")

        if self.serial_no and not self.warehouse:
            self.warehouse = frappe.db.get_value("Serial No", self.serial_no, "warehouse")
