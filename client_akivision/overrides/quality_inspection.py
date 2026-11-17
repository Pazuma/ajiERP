"""Add Work Order references without treating production as a receipt item table."""
import frappe
from erpnext.stock.doctype.quality_inspection.quality_inspection import QualityInspection


class WorkOrderQualityInspection(QualityInspection):
	def validate(self):
		if self.reference_type == "Work Order" and self.reference_name:
			order = frappe.get_doc("Work Order", self.reference_name)
			order.check_permission("read")
			if order.docstatus == 2 or order.company != self.company:
				frappe.throw("请选择同公司且未取消的生产工单")
			if self.custom_work_order and self.custom_work_order != order.name:
				frappe.throw("引用生产工单与来源生产工单不一致")
			if self.item_code != order.production_item:
				frappe.throw("检验物料必须与生产工单的生产物料一致")
			self.custom_work_order = order.name
			self.inspection_type = "In Process"
		super().validate()

	def set_child_row_reference(self):
		if self.reference_type != "Work Order":
			return super().set_child_row_reference()
		self.child_row_reference = None

	def update_qc_reference(self, remove_reference=False):
		if self.reference_type != "Work Order":
			return super().update_qc_reference(remove_reference)
		# Production's existing quality gate consumes custom_work_order;
		# do not write quality_inspection into raw-material child rows.
