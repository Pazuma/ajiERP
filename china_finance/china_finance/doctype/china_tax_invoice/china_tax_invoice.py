import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from china_finance.services.archive import calculate_file_hash, create_archive_record


class ChinaTaxInvoice(Document):
	INPUT_TAX_CONTROL_FIELDS = (
		"verification_status", "deduction_status", "verification_by", "verification_on", "selected_by", "selected_on",
		"deduction_period", "deducted_by", "deducted_on", "non_deduction_reason", "non_deductible_by", "non_deductible_on",
	)

	def before_validate(self):
		if self.company and not self.currency:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		if self.invoice_number and self.seller_tax_id and self.direction:
			self.invoice_key = "|".join((self.direction, self.seller_tax_id.strip().upper(), self.invoice_number.strip().upper()))

	def validate(self):
		self.validate_input_tax_status_changes()
		self.net_amount = 0
		self.tax_amount = 0
		for row in self.items:
			row.gross_amount = flt(row.net_amount, 2) + flt(row.tax_amount, 2)
			self.net_amount += flt(row.net_amount, 2)
			self.tax_amount += flt(row.tax_amount, 2)
		self.gross_amount = self.net_amount + self.tax_amount
		if self.invoice_status == "红票":
			self.validate_red_invoice()
		if self.invoice_request:
			self.validate_invoice_request()
		allocated = 0
		for row in self.allocations:
			row.allocated_gross_amount = flt(row.allocated_net_amount, 2) + flt(row.allocated_tax_amount, 2)
			allocated += row.allocated_gross_amount
		if abs(allocated) - abs(self.gross_amount) > 0.01:
			frappe.throw(_("业务单据分摊金额不能超过发票价税合计"))
		if self.original_file:
			self.file_hash = calculate_file_hash(self.original_file)

	def validate_input_tax_status_changes(self):
		if self.direction != "进项":
			return
		old = self.get_doc_before_save()
		if old and any(getattr(old, fieldname, None) != getattr(self, fieldname, None) for fieldname in self.INPUT_TAX_CONTROL_FIELDS):
			frappe.throw(_("进项税认证和抵扣状态只能通过抵扣批次服务变更"))
		if not old and (self.verification_status not in (None, "未查验") or self.deduction_status not in (None, "不适用")):
			frappe.throw(_("新进项税务发票必须从未查验和不适用状态开始"))

	def on_submit(self):
		if self.invoice_status == "蓝票":
			self.db_set("red_status", "Not Red", update_modified=False)
			self.db_set("remaining_red_amount", self.gross_amount, update_modified=False)
		self.update_red_status()
		from china_finance.services.tax_invoice_request import sync_request_from_tax_invoice

		sync_request_from_tax_invoice(self)
		if self.original_file:
			create_archive_record(self.company, self.doctype, self.name, "Tax Invoice", self.original_file)

	def on_cancel(self):
		self.update_red_status()
		from china_finance.services.tax_invoice_request import sync_request_from_tax_invoice

		sync_request_from_tax_invoice(self)

	def validate_invoice_request(self):
		request = frappe.get_doc("China Tax Invoice Request", self.invoice_request)
		if request.status not in ("Approved", "Invoiced"):
			frappe.throw(_("税务发票只能关联已审批开票申请"))
		if request.company != self.company:
			frappe.throw(_("开票申请与税务发票公司不一致"))
		if abs(flt(request.gross_amount) - flt(self.gross_amount)) > 0.01 or abs(flt(request.tax_amount) - flt(self.tax_amount)) > 0.01:
			frappe.throw(_("税务发票金额必须与开票申请一致"))
		request_totals = {}
		for row in request.items:
			bucket = request_totals.setdefault(row.sales_invoice, [0, 0])
			bucket[0] += flt(row.net_amount)
			bucket[1] += flt(row.tax_amount)
		allocation_totals = {}
		for row in self.allocations:
			if row.reference_doctype == "Sales Invoice":
				bucket = allocation_totals.setdefault(row.reference_name, [0, 0])
				bucket[0] += flt(row.allocated_net_amount)
				bucket[1] += flt(row.allocated_tax_amount)
		if set(request_totals) != set(allocation_totals) or any(
			abs(request_totals[name][0] - allocation_totals[name][0]) > 0.01
			or abs(request_totals[name][1] - allocation_totals[name][1]) > 0.01
			for name in request_totals
		):
			frappe.throw(_("税务发票的销售发票分摊必须与开票申请快照一致"))

	def validate_red_invoice(self):
		if not self.original_invoice or not self.credit_note:
			frappe.throw(_("红字发票必须关联原蓝票和销售退货或贷项发票"))
		blue = frappe.get_doc("China Tax Invoice", self.original_invoice)
		credit_note = frappe.get_doc("Sales Invoice", self.credit_note)
		if blue.docstatus != 1 or blue.invoice_status != "蓝票" or credit_note.docstatus != 1 or not credit_note.is_return:
			frappe.throw(_("红字发票必须关联已提交蓝票及已提交销售退货或贷项发票"))
		if any(flt(row.net_amount) >= 0 or flt(row.tax_amount) >= 0 for row in self.items):
			frappe.throw(_("红字发票所有明细金额必须为负数"))
		already_red = frappe.db.sql("SELECT COALESCE(SUM(ABS(gross_amount)), 0) FROM `tabChina Tax Invoice` WHERE original_invoice=%s AND invoice_status='红票' AND docstatus=1 AND name!=%s", (blue.name, self.name))[0][0]
		if flt(already_red) + abs(flt(self.gross_amount)) - flt(blue.gross_amount) > 0.01:
			frappe.throw(_("累计红冲金额不能超过原蓝票可红冲金额"))

	def update_red_status(self):
		if not self.original_invoice:
			return
		blue = frappe.get_doc("China Tax Invoice", self.original_invoice)
		red_amount = frappe.db.sql("SELECT COALESCE(SUM(ABS(gross_amount)), 0) FROM `tabChina Tax Invoice` WHERE original_invoice=%s AND invoice_status='红票' AND docstatus=1", blue.name)[0][0]
		remaining = max(0, flt(blue.gross_amount) - flt(red_amount))
		status = "Fully Red" if remaining <= 0.01 else "Partially Red" if red_amount else "Not Red"
		blue.db_set("red_status", status, update_modified=False)
		blue.db_set("remaining_red_amount", remaining, update_modified=False)
