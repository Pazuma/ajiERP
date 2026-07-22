import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime


TAX_USERS = ("System Manager", "Accounts Manager", "China Tax User")
FINANCE_MANAGERS = ("System Manager", "Accounts Manager", "China Finance Manager")
ACTIVE_BATCH_STATUSES = ("Draft", "Selected")


def _only_for(roles):
	frappe.only_for(roles)


def _parse_names(tax_invoices):
	tax_invoices = frappe.parse_json(tax_invoices) if isinstance(tax_invoices, str) else tax_invoices
	if not isinstance(tax_invoices, list) or not tax_invoices:
		frappe.throw(_("至少选择一张进项税务发票"))
	return list(dict.fromkeys(tax_invoices))


def _get_input_invoice(name):
	doc = frappe.get_doc("China Tax Invoice", name)
	if doc.docstatus != 1 or doc.direction != "进项" or doc.invoice_status != "蓝票":
		frappe.throw(_("税务发票 {0} 必须是已提交的进项蓝票").format(name))
	return doc


def _active_batch_for_invoice(name, exclude_batch=None):
	conditions = "item.tax_invoice=%s AND batch.status IN ('Draft', 'Selected')"
	values = [name]
	if exclude_batch:
		conditions += " AND batch.name!=%s"
		values.append(exclude_batch)
	rows = frappe.db.sql(
		"""
		SELECT batch.name FROM `tabChina Input Tax Deduction Item` item
		INNER JOIN `tabChina Input Tax Deduction Batch` batch ON batch.name=item.parent
		WHERE {conditions}
		LIMIT 1
		""".format(conditions=conditions),
		values,
	)
	return rows[0][0] if rows else None


def _ensure_eligible_for_selection(doc, company, exclude_batch=None):
	if doc.company != company:
		frappe.throw(_("进项税务发票 {0} 与抵扣批次公司不一致").format(doc.name))
	if doc.verification_status != "查验通过" or doc.deduction_status != "待勾选":
		frappe.throw(_("进项税务发票 {0} 必须已查验并处于待勾选状态").format(doc.name))
	if _active_batch_for_invoice(doc.name, exclude_batch):
		frappe.throw(_("进项税务发票 {0} 已在未完成抵扣批次中").format(doc.name))


@frappe.whitelist()
def verify_input_invoices(tax_invoices):
	_only_for(TAX_USERS)
	result = {"processed": 0, "succeeded": 0, "failed": 0, "errors": []}
	for name in _parse_names(tax_invoices):
		result["processed"] += 1
		try:
			doc = _get_input_invoice(name)
			if doc.verification_status not in ("未查验", "查验失败"):
				raise frappe.ValidationError(_("进项税务发票已完成查验"))
			doc.db_set("verification_status", "查验通过")
			doc.db_set("deduction_status", "待勾选")
			doc.db_set("verification_by", frappe.session.user)
			doc.db_set("verification_on", now_datetime())
			result["succeeded"] += 1
		except Exception as exc:
			result["failed"] += 1
			result["errors"].append({"tax_invoice": name, "error": str(exc)})
	return result


@frappe.whitelist()
def create_input_tax_deduction_batch(company, deduction_period, tax_invoices, remarks=None):
	_only_for(TAX_USERS)
	deduction_period = getdate(deduction_period)
	items = []
	for name in _parse_names(tax_invoices):
		doc = _get_input_invoice(name)
		_ensure_eligible_for_selection(doc, company)
		items.append(
			{
				"tax_invoice": doc.name,
				"invoice_number": doc.invoice_number,
				"invoice_date": doc.invoice_date,
				"seller_name": doc.seller_name,
				"net_amount": doc.net_amount,
				"tax_amount": doc.tax_amount,
				"gross_amount": doc.gross_amount,
			}
		)
	doc = frappe.get_doc(
		{"doctype": "China Input Tax Deduction Batch", "company": company, "deduction_period": deduction_period, "remarks": remarks, "items": items}
	).insert()
	return {"name": doc.name, "status": doc.status, "invoice_count": doc.invoice_count}


@frappe.whitelist()
def select_input_tax_deduction_batch(name):
	_only_for(TAX_USERS)
	batch = frappe.get_doc("China Input Tax Deduction Batch", name)
	if batch.status != "Draft":
		frappe.throw(_("只有草稿抵扣批次可以勾选"))
	for row in batch.items:
		frappe.db.sql("SELECT name FROM `tabChina Tax Invoice` WHERE name=%s FOR UPDATE", row.tax_invoice)
		doc = _get_input_invoice(row.tax_invoice)
		_ensure_eligible_for_selection(doc, batch.company, batch.name)
	batch.db_set("status", "Selected")
	batch.db_set("selected_by", frappe.session.user)
	batch.db_set("selected_on", now_datetime())
	for row in batch.items:
		doc = frappe.get_doc("China Tax Invoice", row.tax_invoice)
		doc.db_set("deduction_status", "已勾选")
		doc.db_set("selected_by", frappe.session.user)
		doc.db_set("selected_on", now_datetime())
	return {"name": batch.name, "status": "Selected"}


@frappe.whitelist()
def deduct_input_tax_batch(name):
	_only_for(FINANCE_MANAGERS)
	batch = frappe.get_doc("China Input Tax Deduction Batch", name)
	if batch.status != "Selected":
		frappe.throw(_("只有已勾选抵扣批次可以确认抵扣"))
	for row in batch.items:
		doc = _get_input_invoice(row.tax_invoice)
		if doc.deduction_status != "已勾选":
			frappe.throw(_("进项税务发票 {0} 不处于已勾选状态").format(doc.name))
	batch.db_set("status", "Deducted")
	batch.db_set("deducted_by", frappe.session.user)
	batch.db_set("deducted_on", now_datetime())
	for row in batch.items:
		doc = frappe.get_doc("China Tax Invoice", row.tax_invoice)
		doc.db_set("deduction_status", "已抵扣")
		doc.db_set("deduction_period", batch.deduction_period)
		doc.db_set("deducted_by", frappe.session.user)
		doc.db_set("deducted_on", now_datetime())
	return {"name": batch.name, "status": "Deducted"}


@frappe.whitelist()
def cancel_input_tax_deduction_batch(name, reason):
	_only_for(FINANCE_MANAGERS)
	if not reason:
		frappe.throw(_("取消抵扣批次必须填写原因"))
	batch = frappe.get_doc("China Input Tax Deduction Batch", name)
	if batch.status not in ACTIVE_BATCH_STATUSES:
		frappe.throw(_("只有草稿或已勾选抵扣批次可以取消"))
	if batch.status == "Selected":
		for row in batch.items:
			doc = frappe.get_doc("China Tax Invoice", row.tax_invoice)
			if doc.deduction_status == "已勾选":
				doc.db_set("deduction_status", "待勾选")
				doc.db_set("selected_by", None)
				doc.db_set("selected_on", None)
	batch.db_set("status", "Cancelled")
	batch.db_set("cancelled_by", frappe.session.user)
	batch.db_set("cancelled_on", now_datetime())
	batch.db_set("cancellation_reason", reason)
	return {"name": batch.name, "status": "Cancelled"}


@frappe.whitelist()
def mark_input_tax_non_deductible(name, reason):
	_only_for(FINANCE_MANAGERS)
	if not reason:
		frappe.throw(_("不得抵扣必须填写原因"))
	doc = _get_input_invoice(name)
	if doc.deduction_status in ("已抵扣", "不得抵扣") or _active_batch_for_invoice(name):
		frappe.throw(_("已进入抵扣流程的税务发票不能标记为不得抵扣"))
	doc.db_set("deduction_status", "不得抵扣")
	doc.db_set("non_deduction_reason", reason)
	doc.db_set("non_deductible_by", frappe.session.user)
	doc.db_set("non_deductible_on", now_datetime())
	return {"name": doc.name, "deduction_status": "不得抵扣"}
