"""Historical price checks used before a Supplier Quotation is submitted."""

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_higher_price_items(supplier, currency, items, quotation_name=None):
	"""Return historical rows whose matching current quotation row is more expensive.

	Rows match only when supplier, item, currency, UOM, and quantity are equal.
	The latest submitted quotation containing each matching row is used as the
	historical reference.  Returned quotations are permission-checked before
	their details are exposed to the Desk client.
	"""
	if not frappe.has_permission("Supplier Quotation", "submit"):
		frappe.throw(_("You do not have permission to submit Supplier Quotations."), frappe.PermissionError)
	if not frappe.has_permission("Supplier Quotation", "read"):
		frappe.throw(_("You do not have permission to read Supplier Quotations."), frappe.PermissionError)

	if isinstance(items, str):
		items = frappe.parse_json(items)

	current_rows = _normalize_rows(items)
	if not supplier or not currency or not current_rows:
		return []

	historical_rows = frappe.db.sql(
		"""
		SELECT
			sq.name AS quotation,
			sq.transaction_date,
			sq.creation,
			sq.modified,
			sqi.idx,
			sqi.item_code,
			sqi.uom,
			sqi.qty,
			sqi.rate
		FROM `tabSupplier Quotation` sq
		INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		WHERE sq.docstatus = 1
			AND sq.supplier = %(supplier)s
			AND sq.currency = %(currency)s
			AND sqi.item_code IN %(item_codes)s
			AND sq.name != %(quotation_name)s
		ORDER BY sq.transaction_date DESC, sq.creation DESC, sq.modified DESC, sqi.idx ASC
		""",
		{
			"supplier": supplier,
			"currency": currency,
			"item_codes": tuple({row["item_code"] for row in current_rows}),
			"quotation_name": quotation_name or "",
		},
		as_dict=True,
	)

	current_by_key = {(row["item_code"], row["uom"], row["qty"]): row for row in current_rows}
	latest_by_key = {}
	for row in historical_rows:
		key = (row.item_code, row.uom, flt(row.qty))
		if key not in current_by_key or key in latest_by_key:
			continue
		if not frappe.has_permission("Supplier Quotation", "read", doc=row.quotation):
			continue
		latest_by_key[key] = row

	return [
		{
			"item_code": current["item_code"],
			"uom": current["uom"],
			"qty": current["qty"],
			"current_rate": current["rate"],
			"historical_rate": flt(history.rate),
			"currency": currency,
			"quotation": history.quotation,
		}
		for key, history in latest_by_key.items()
		if (current := current_by_key[key])["rate"] > flt(history.rate)
	]


@frappe.whitelist()
def get_tier_shrinkage(supplier, items, quotation_name=None):
	"""Return items whose current quotation has fewer quantity price points than
	the latest submitted quotation for the same supplier+item.

	Points are counted as distinct quantities; only the most recent quotation
	containing each item is used as the historical reference.
	"""
	if not frappe.has_permission("Supplier Quotation", "submit"):
		frappe.throw(_("You do not have permission to submit Supplier Quotations."), frappe.PermissionError)
	if not frappe.has_permission("Supplier Quotation", "read"):
		frappe.throw(_("You do not have permission to read Supplier Quotations."), frappe.PermissionError)

	if isinstance(items, str):
		items = frappe.parse_json(items)

	current_qtys = {}
	for row in items or []:
		item_code = (row.get("item_code") or "").strip()
		qty = flt(row.get("qty"))
		if not item_code or not qty:
			continue
		current_qtys.setdefault(item_code, set()).add(qty)
	if not supplier or not current_qtys:
		return []

	latest_by_item = {}
	for row in frappe.db.sql(
		"""
		SELECT sq.name AS quotation, sqi.item_code, sqi.qty
		FROM `tabSupplier Quotation` sq
		JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		WHERE sq.docstatus = 1
			AND sq.supplier = %(supplier)s
			AND sq.name != %(quotation_name)s
			AND sqi.item_code IN %(item_codes)s
		ORDER BY sq.transaction_date DESC, sq.creation DESC, sq.modified DESC, sqi.idx ASC
		""",
		{
			"supplier": supplier,
			"quotation_name": quotation_name or "",
			"item_codes": tuple(current_qtys),
		},
		as_dict=True,
	):
		entry = latest_by_item.get(row.item_code)
		if entry is None:
			if not frappe.has_permission("Supplier Quotation", "read", doc=row.quotation):
				continue
			entry = latest_by_item[row.item_code] = {"quotation": row.quotation, "qtys": set()}
		if row.quotation != entry["quotation"]:
			continue  # Only the latest quotation containing the item counts.
		entry["qtys"].add(flt(row.qty))

	return [
		{
			"item_code": item_code,
			"current_tiers": len(qtys),
			"historical_tiers": len(latest_by_item[item_code]["qtys"]),
			"quotation": latest_by_item[item_code]["quotation"],
		}
		for item_code, qtys in current_qtys.items()
		if item_code in latest_by_item and len(qtys) < len(latest_by_item[item_code]["qtys"])
	]


def _normalize_rows(items):
	"""Keep only complete rows and normalize numeric quantities for matching."""
	rows_by_key = {}
	for row in items or []:
		item_code = (row.get("item_code") or "").strip()
		uom = (row.get("uom") or "").strip()
		qty = flt(row.get("qty"))
		if not item_code or not uom:
			continue
		rows_by_key[(item_code, uom, qty)] = {
			"item_code": item_code,
			"uom": uom,
			"qty": qty,
			"rate": flt(row.get("rate")),
		}
	return list(rows_by_key.values())
