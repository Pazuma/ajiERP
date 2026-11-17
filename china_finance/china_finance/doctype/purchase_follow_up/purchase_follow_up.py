import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class PurchaseFollowUp(Document):
	def validate(self):
		if self.reconciliation_statement:
			statement = frappe.get_doc("China Reconciliation Statement", self.reconciliation_statement)
			if statement.docstatus != 1 or statement.status != "Confirmed" or statement.statement_type != "Supplier" or (self.company, self.supplier) != (statement.company, statement.party) or (statement.currency and self.currency != statement.currency):
				frappe.throw(_("采购对账草稿必须关联同一公司、供应商及币种的已确认供应商对账单"))
		if self.from_date > self.to_date:
			frappe.throw(_("对账开始日期不能晚于截止日期"))
		if self.docstatus == 0:
			self.system_amount = sum(flt(row.amount) for row in self.sources)
			self.difference_amount = flt(self.supplier_amount) - flt(self.system_amount)
			if self.sources and (any(flt(row.difference_amount) and not (row.difference_reason and row.resolution) for row in self.sources) or abs(flt(self.difference_amount)) > 0.01 and not self.remarks):
				self.status = "待处理差异"
			elif self.status not in ("待财务处理", "财务处理中", "部分付款", "已结清"):
				self.status = "对账中" if self.sources else "草稿"
		self._refresh_invoice_status()

	def before_submit(self):
		if not self.sources:
			frappe.throw(_("请先加载采购对账明细"))
		if any(flt(row.difference_amount) and not (row.difference_reason and row.resolution) for row in self.sources):
			frappe.throw(_("存在未处理差异，不能移交财务"))
		if abs(flt(self.difference_amount)) > 0.01 and not self.remarks:
			frappe.throw(_("供应商金额与系统金额不一致，请填写差异处理结论"))
		self._validate_sources()
		self.status = "待财务处理"
		self.handoff_by = frappe.session.user
		self.handoff_on = now_datetime()

	def on_cancel(self):
		if frappe.db.exists("Purchase Invoice", {"custom_purchase_follow_up": self.name, "docstatus": 1}):
			frappe.throw(_("存在已提交的关联采购发票，不能取消对账单"))
		self.db_set("status", "已取消", update_modified=False)

	def _validate_sources(self):
		seen = set()
		for row in sorted(self.sources, key=lambda item: item.source_detail or ""):
			if row.source_type != "Purchase Receipt" or not row.source_detail:
				frappe.throw(_("目前仅支持以采购收货行对账；其他采购类型请走现有财务流程"))
			if row.source_detail in seen:
				frappe.throw(_("对账明细中存在重复收货行"))
			seen.add(row.source_detail)
			if not frappe.has_permission("Purchase Receipt", "read", row.source_name):
				frappe.throw(_("没有读取采购收货单的权限"), frappe.PermissionError)
			# Lock the source row so two concurrent submissions cannot claim it together.
			source = frappe.db.sql("""SELECT pri.name, pri.parent, pri.qty, pri.amount, pr.company, pr.supplier,
				pr.currency, pr.docstatus, pr.is_return FROM `tabPurchase Receipt Item` pri
				JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
				WHERE pri.name = %s FOR UPDATE""", row.source_detail, as_dict=True)
			if not source or source[0].docstatus != 1 or source[0].company != self.company or source[0].supplier != self.supplier or source[0].currency != self.currency or source[0].parent != row.source_name:
				frappe.throw(_("收货来源已变化，请重新加载对账数据"))
			order = frappe.db.get_value("Purchase Receipt Item", row.source_detail, "purchase_order")
			if order and not source[0].is_return and frappe.get_meta("Purchase Order").has_field("custom_procurement_flow_status"):
				if frappe.db.get_value("Purchase Order", order, "custom_procurement_flow_status") == "已完成":
					frappe.throw(_("采购订单 {0} 已完成，无需再次对账，请重新加载明细。").format(order))
			if abs(flt(row.qty) - flt(source[0].qty) * (-1 if source[0].is_return else 1)) > 0.000001 or abs(flt(row.amount) - flt(source[0].amount) * (-1 if source[0].is_return else 1)) > 0.01:
				frappe.throw(_("收货数量或金额已变化，请重新加载对账数据"))
			occupied = frappe.db.sql("""SELECT p.name FROM `tabPurchase Follow Up Item` i
				JOIN `tabPurchase Follow Up` p ON p.name = i.parent
				WHERE i.source_detail = %s AND p.docstatus = 1 AND p.name != %s LIMIT 1""", (row.source_detail, self.name))
			if occupied:
				frappe.throw(_("收货行已在其他有效对账单确认：{0}").format(occupied[0][0]))

	def _refresh_invoice_status(self):
		if not self.name or not frappe.db.exists("DocType", "Purchase Invoice"):
			return
		invoices = frappe.get_all("Purchase Invoice", filters={"custom_purchase_follow_up": self.name}, fields=["name", "docstatus", "outstanding_amount", "grand_total"])
		self.linked_purchase_invoices = ", ".join(row.name for row in invoices)
		posted = [row for row in invoices if row.docstatus == 1]
		if not invoices:
			self.purchase_invoice_status = "待财务开票"
		elif not posted and all(row.docstatus == 2 for row in invoices):
			self.purchase_invoice_status = "采购发票已取消"
		elif posted and any(flt(row.outstanding_amount) < -0.01 for row in posted):
			self.purchase_invoice_status = "余额异常/退款待核查"
		elif posted and all(abs(flt(row.outstanding_amount)) <= 0.01 for row in posted):
			self.purchase_invoice_status = "已结清"
		elif posted:
			self.purchase_invoice_status = "部分付款" if any(flt(row.outstanding_amount) < flt(row.grand_total) - 0.01 for row in posted) else "待付款"
		else:
			self.purchase_invoice_status = "发票草稿"


def ensure_purchase_follow_up_from_statement(statement):
	"""Map only the statement's invoices to their exact receipt rows."""
	statement.check_permission("read")
	if statement.docstatus != 1 or statement.status != "Confirmed" or statement.statement_type != "Supplier":
		frappe.throw(_("仅可从已确认的供应商对账单创建采购对账草稿"))
	frappe.db.sql("SELECT name FROM `tabChina Reconciliation Statement` WHERE name=%s FOR UPDATE", statement.name)
	existing = frappe.db.get_value("Purchase Follow Up", {"reconciliation_statement": statement.name}, "name")
	if existing:
		return {"name": existing}
	invoices = {row.voucher_no for row in statement.lines if row.voucher_type == "Purchase Invoice" and row.voucher_no}
	if not invoices:
		return {"name": None, "reason": _("对账单没有采购发票明细")}
	if not frappe.has_permission("Purchase Follow Up", "create"):
		frappe.throw(_("没有创建采购对账草稿的权限"), frappe.PermissionError)
	receipts = {}
	invoiced_qty = {}
	for name in sorted(invoices):
		invoice = frappe.get_doc("Purchase Invoice", name)
		if invoice.docstatus != 1 or (invoice.company, invoice.supplier) != (statement.company, statement.party):
			return {"name": None, "reason": _("采购发票 {0} 与对账单不一致").format(name)}
		if statement.currency and invoice.currency != statement.currency:
			return {"name": None, "reason": _("采购发票 {0} 币种不一致").format(name)}
		if not invoice.items or invoice.is_return:
			return {"name": None, "reason": _("采购发票 {0} 为退货或无明细，请人工处理").format(name)}
		for item in invoice.items:
			if not item.purchase_receipt or not item.purchase_receipt_item:
				return {"name": None, "reason": _("采购发票 {0} 有明细未关联采购收货行").format(name)}
			receipts[item.purchase_receipt_item] = item.purchase_receipt
			invoiced_qty[item.purchase_receipt_item] = flt(invoiced_qty.get(item.purchase_receipt_item)) + flt(item.qty)
	if not receipts:
		return {"name": None, "reason": _("没有可关联的采购收货行")}
	rows = []
	currency = None
	for detail, receipt_name in sorted(receipts.items()):
		source = frappe.db.get_value(
			"Purchase Receipt Item", detail,
			["parent", "purchase_order", "item_code", "item_name", "qty", "rate", "amount"], as_dict=True,
		)
		receipt = frappe.db.get_value(
			"Purchase Receipt", receipt_name,
			["company", "supplier", "currency", "posting_date", "docstatus", "is_return"], as_dict=True,
		)
		if not source or not receipt or source.parent != receipt_name or receipt.docstatus != 1 or receipt.is_return or (receipt.company, receipt.supplier) != (statement.company, statement.party):
			return {"name": None, "reason": _("收货行 {0} 来源不符或为退货").format(detail)}
		if abs(flt(source.qty) - invoiced_qty[detail]) > 0.000001:
			return {"name": None, "reason": _("收货行 {0} 只完成部分开票或跨期拆票，请人工处理").format(detail)}
		if currency and currency != receipt.currency or statement.currency and statement.currency != receipt.currency:
			return {"name": None, "reason": _("关联收货行币种不一致")}
		currency = receipt.currency
		if frappe.db.sql("""SELECT p.name FROM `tabPurchase Follow Up Item` i
			JOIN `tabPurchase Follow Up` p ON p.name=i.parent
			WHERE i.source_detail=%s AND p.docstatus=1 LIMIT 1""", detail):
			return {"name": None, "reason": _("收货行 {0} 已在其他采购对账单确认").format(detail)}
		rows.append({"source_type": "Purchase Receipt", "source_name": receipt_name, "source_detail": detail,
			"purchase_order": source.purchase_order, "purchase_receipt": receipt_name,
			"item_code": source.item_code, "item_name": source.item_name, "posting_date": receipt.posting_date,
			"qty": source.qty, "rate": source.rate, "amount": source.amount, "currency": currency})
	doc = frappe.get_doc({"doctype": "Purchase Follow Up", "reconciliation_statement": statement.name,
		"auto_reconciliation_statement": statement.name,
		"company": statement.company, "supplier": statement.party, "currency": currency,
		"from_date": statement.from_date, "to_date": statement.to_date, "sources": rows})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
def preview_purchase_follow_up_sources(company, supplier, from_date, to_date, currency=None):
	if not frappe.has_permission("Purchase Follow Up", "create"):
		frappe.throw(_("没有创建采购跟进单的权限"), frappe.PermissionError)
	if not frappe.has_permission("Company", "read", company) or not frappe.has_permission("Supplier", "read", supplier):
		frappe.throw(_("没有读取公司或供应商的权限"), frappe.PermissionError)
	if from_date > to_date:
		frappe.throw(_("对账开始日期不能晚于截止日期"))
	params = {"company": company, "supplier": supplier, "from_date": from_date, "to_date": to_date}
	conditions = ["pr.company=%(company)s", "pr.supplier=%(supplier)s", "pr.posting_date BETWEEN %(from_date)s AND %(to_date)s", "pr.docstatus=1"]
	if frappe.get_meta("Purchase Order").has_field("custom_procurement_flow_status"):
		# Returns are new movements and still need reconciliation after an order completes.
		conditions.append("""(pr.is_return=1 OR NOT EXISTS (
			SELECT 1 FROM `tabPurchase Order` po WHERE po.name=pri.purchase_order
			AND po.custom_procurement_flow_status='已完成'))""")
	if currency:
		conditions.append("pr.currency=%(currency)s")
		params["currency"] = currency
	rows = frappe.db.sql(f"""
		SELECT pri.name source_detail, pr.name source_name, pri.purchase_order, pri.item_code, pri.item_name,
			pr.posting_date, pri.qty, pri.rate, pri.amount, pr.currency, pr.is_return,
			COALESCE((SELECT SUM(pii.qty) FROM `tabPurchase Invoice Item` pii
				JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent AND pi.docstatus=1
				WHERE pii.purchase_receipt=pr.name AND pii.pr_detail=pri.name), 0) billed_qty
		FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
		WHERE {' AND '.join(conditions)}
		AND NOT EXISTS (SELECT 1 FROM `tabPurchase Follow Up Item` fi
			JOIN `tabPurchase Follow Up` f ON f.name = fi.parent
			WHERE fi.source_type='Purchase Receipt' AND fi.source_detail = pri.name AND f.docstatus = 1)
		ORDER BY pr.posting_date, pr.name, pri.idx
	""", params, as_dict=True)
	result = []
	for row in rows:
		if not frappe.has_permission("Purchase Receipt", "read", row.source_name):
			continue
		qty = flt(row.qty) * (-1 if row.is_return else 1)
		amount = flt(row.amount) * (-1 if row.is_return else 1)
		result.append({"source_type": "Purchase Receipt", "source_name": row.source_name, "source_detail": row.source_detail, "purchase_order": row.purchase_order, "purchase_receipt": row.source_name, "item_code": row.item_code, "item_name": row.item_name, "posting_date": row.posting_date, "qty": qty, "rate": row.rate, "amount": amount, "currency": row.currency, "return_qty": abs(qty) if row.is_return else 0, "billed_qty": row.billed_qty})
	return {"rows": result, "system_amount": sum(flt(row["amount"]) for row in result), "currency": currency or (result[0]["currency"] if result else None), "row_count": len(result)}


@frappe.whitelist()
def refresh_purchase_follow_up_status(name):
	doc = frappe.get_doc("Purchase Follow Up", name)
	doc.check_permission("read")
	doc._refresh_invoice_status()
	return {"status": doc.status, "purchase_invoice_status": doc.purchase_invoice_status, "linked_purchase_invoices": doc.linked_purchase_invoices}


@frappe.whitelist()
def receive_purchase_follow_up(name):
	if not set(frappe.get_roles()) & {"Accounts User", "Accounts Manager", "System Manager"}:
		frappe.throw(_("仅财务人员可接收采购对账单"), frappe.PermissionError)
	doc = frappe.get_doc("Purchase Follow Up", name)
	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("仅可接收已提交的采购对账单"))
	if not doc.finance_received_on:
		doc.db_set({"finance_receiver": frappe.session.user, "finance_received_on": now_datetime(), "status": "财务处理中"})
	return {"finance_receiver": doc.finance_receiver, "finance_received_on": doc.finance_received_on}


def validate_purchase_invoice_follow_up(doc, method=None):
	if not doc.get("custom_purchase_follow_up"):
		return
	follow_up = frappe.get_doc("Purchase Follow Up", doc.custom_purchase_follow_up)
	if follow_up.docstatus != 1 or (doc.company, doc.supplier, doc.currency) != (follow_up.company, follow_up.supplier, follow_up.currency):
		frappe.throw(_("采购发票关联的对账单必须已提交，且公司、供应商和币种一致"))
	if doc.docstatus == 0 and not frappe.has_permission("Purchase Follow Up", "read", follow_up.name):
		frappe.throw(_("没有读取关联采购对账单的权限"), frappe.PermissionError)


def validate_purchase_invoice_follow_up_amount(doc, method=None):
	if not doc.get("custom_purchase_follow_up") or doc.get("is_return"):
		return
	validate_purchase_invoice_follow_up(doc)
	# Serialize competing invoice submissions against the same reconciliation.
	frappe.db.sql("SELECT name FROM `tabPurchase Follow Up` WHERE name = %s FOR UPDATE", doc.custom_purchase_follow_up)
	limit = flt(frappe.db.get_value("Purchase Follow Up", doc.custom_purchase_follow_up, "supplier_amount"))
	if limit <= 0:
		frappe.throw(_("请先确认对账单的供应商金额，再提交采购发票"))
	used = frappe.db.sql("""SELECT COALESCE(SUM(grand_total), 0) FROM `tabPurchase Invoice`
		WHERE custom_purchase_follow_up = %s AND docstatus = 1 AND name != %s AND is_return = 0""",
		(doc.custom_purchase_follow_up, doc.name))[0][0]
	if flt(used) + flt(doc.grand_total) > limit + 0.01:
		frappe.throw(_("关联采购发票合计超过对账单确认的供应商金额"))
