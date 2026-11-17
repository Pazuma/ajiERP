"""Formal, read-only Purchase Material Request PDF export."""

import frappe
from frappe import _
from frappe.utils import flt, get_fullname

from client_akivision.utils.formal_pdf_export import download_documents, parse_names, read_doc, render_pdf


def _employee_name(user):
	employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, ["employee_name", "department"], as_dict=True)
	return employee or {"employee_name": get_fullname(user), "department": ""}


def _context(doc):
	if doc.docstatus == 2 or doc.material_request_type != "Purchase":
		frappe.throw(_("采购申请单仅支持未取消的采购类型申请。"))
	employee = _employee_name(doc.owner)
	items, total, pending = [], 0, False
	for row in doc.items or []:
		if not row.item_code:
			continue
		has_rate = row.rate not in (None, "") and flt(row.rate) != 0
		amount = flt(row.amount) if has_rate else None
		if amount is None:
			pending = True
		else:
			total += amount
		items.append({"item_code": row.item_code, "item_name": row.item_name or row.item_code, "project": row.get("project") or doc.get("project") or "", "qty": row.qty, "uom": row.uom or row.stock_uom, "rate": row.rate if has_rate else "待询价", "amount": amount if amount is not None else "待询价", "supplier": row.get("supplier") or doc.get("supplier") or "", "remarks": row.get("description") or ""})
	if not items:
		frappe.throw(_("采购申请没有可打印的物料明细。"))
	company_name = frappe.db.get_value("Company", doc.company, "company_name") or doc.company
	return {
		"company_name": company_name,
		"doc": doc,
		"employee_name": employee.get("employee_name") or get_fullname(doc.owner),
		"department": doc.get("department") or employee.get("department") or "",
		"items": items,
		"total": total,
		"has_pending": pending,
	}


@frappe.whitelist()
def download_material_request_pdf(document_names):
	files = []
	for name in parse_names(document_names):
		doc = read_doc("Material Request", name)
		files.append((f"采购申请单-{doc.name}", render_pdf("templates/material_request_purchase_pdf.html", _context(doc), "Portrait")))
	download_documents(files, "采购申请单")


@frappe.whitelist()
def preview_material_request_pdf(document_name):
	"""Return one purchase request as HTML for confirmation before export."""
	doc = read_doc("Material Request", document_name)
	context = _context(doc)
	frappe.local.response["type"] = "html"
	frappe.local.response["message"] = frappe.render_template("templates/material_request_purchase_pdf.html", context)
