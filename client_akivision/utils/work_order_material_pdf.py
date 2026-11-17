"""Formal, read-only Work Order material issue PDF export."""

import frappe
from frappe import _
from frappe.utils import flt

from client_akivision.utils.formal_pdf_export import download_documents, parse_names, read_doc, render_pdf


def _context(doc):
	if doc.docstatus == 2:
		frappe.throw(_("已取消工单不能生成领料单。"))
	if not flt(doc.qty):
		frappe.throw(_("工单计划数量为零，不能计算单套用量。"))
	items = []
	for row in doc.required_items or []:
		required, transferred = flt(row.required_qty), flt(row.transferred_qty)
		items.append({"drawing_no": row.get("custom_drawing_no") or row.get("drawing_no") or "", "item_code": row.item_code, "item_name": row.item_name or row.item_code, "per_set_qty": required / flt(doc.qty), "required_qty": required, "issued_qty": transferred, "shortage_qty": max(required - transferred, 0), "remarks": row.get("description") or ""})
	if not items:
		frappe.throw(_("工单没有可打印的领料明细。"))
	company_name = frappe.db.get_value("Company", doc.company, "company_name") or doc.company
	return {"company_name": company_name, "doc": doc, "items": items, "model": doc.get("custom_model") or doc.production_item, "remarks": doc.get("description") or ""}


@frappe.whitelist()
def download_work_order_material_pdf(document_names):
	files = []
	for name in parse_names(document_names):
		doc = read_doc("Work Order", name)
		files.append((f"产品组装领料单-{doc.name}", render_pdf("templates/work_order_material_issue_pdf.html", _context(doc), "Landscape")))
	download_documents(files, "产品组装领料单")
