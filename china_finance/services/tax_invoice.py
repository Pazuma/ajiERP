import frappe
from frappe import _


@frappe.whitelist()
def import_invoices(records):
	frappe.only_for(("System Manager", "Accounts Manager", "China Tax User"))
	records = frappe.parse_json(records) if isinstance(records, str) else records
	if not isinstance(records, list):
		frappe.throw(_("records 必须是发票对象数组"))
	result = {"processed": len(records), "created": 0, "skipped": 0, "failed": 0, "errors": []}
	for index, record in enumerate(records, 1):
		try:
			key = build_invoice_key(record)
			if frappe.db.exists("China Tax Invoice", {"invoice_key": key}):
				result["skipped"] += 1
				continue
			doc = frappe.get_doc({"doctype": "China Tax Invoice", **record})
			doc.insert()
			result["created"] += 1
		except Exception as exc:
			result["failed"] += 1
			result["errors"].append({"row": index, "invoice_number": record.get("invoice_number"), "error": str(exc)})
	return result


def build_invoice_key(record):
	required = ("direction", "seller_tax_id", "invoice_number")
	missing = [field for field in required if not record.get(field)]
	if missing:
		frappe.throw(_("缺少必填字段：{0}").format(", ".join(missing)))
	return "|".join(
		(
			record["direction"],
			record["seller_tax_id"].strip().upper(),
			record["invoice_number"].strip().upper(),
		)
	)

