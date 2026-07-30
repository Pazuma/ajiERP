"""Purchase Comparison: MR entry point, basket comparison, and PO draft creation.

The pricing engine is reused from the Purchase Recommendation report module so
report and document stay consistent; the report file itself is not modified.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from client_akivision.client_akivision.doctype.supplier_quote_import.supplier_quote_import import (
	_default_warehouse,
)
from client_akivision.client_akivision.report.purchase_recommendation import (
	purchase_recommendation as engine,
)
from client_akivision.utils.purchase_order_draft import add_item_to_supplier_po_draft

COMPARISON_DOCTYPE = "Purchase Comparison"


@frappe.whitelist()
def create_from_material_request(mr_name):
	"""Create (or reopen) a Purchase Comparison for a Material Request. Idempotent."""
	existing = frappe.get_all(
		COMPARISON_DOCTYPE,
		filters={"material_request": mr_name, "status": ("!=", "PO Created")},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)
	if existing:
		return existing[0]

	mr = frappe.get_doc("Material Request", mr_name)
	if mr.docstatus == 2:
		frappe.throw(_("The selected Material Request is cancelled."))
	if mr.docstatus != 1:
		frappe.throw(_("Please submit the Material Request before comparing suppliers."))
	if mr.material_request_type != "Purchase":
		frappe.throw(_("Supplier comparison is only available for Purchase Material Requests."))
	if mr.get("custom_purchase_scene") == "零星采购":
		frappe.throw(_("Supplier comparison is not available for miscellaneous purchase requests."))

	doc = frappe.get_doc(
		{
			"doctype": COMPARISON_DOCTYPE,
			"company": mr.company,
			"date": getdate(),
			"status": "Draft",
			"material_request": mr_name,
		}
	)
	for row in mr.items:
		if not row.item_code:
			continue
		remaining_qty = _remaining_mr_qty(row)
		if remaining_qty <= 0:
			continue
		doc.append(
			"items",
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": remaining_qty,
				"uom": row.uom,
				"warehouse": row.get("warehouse"),
				"material_request_item": row.name,
			},
		)
	if not doc.items:
		frappe.throw(_("The selected Material Request has no items."))

	run_comparison(doc)
	doc.insert()
	return doc.name


@frappe.whitelist()
def run_comparison_for(comparison_name):
	"""Re-run the comparison on a saved document (clears and refills the rows).

	When the demand list is empty but a source (Material Request / BOM) is set,
	the source items are pulled automatically first.
	"""
	doc = frappe.get_doc(COMPARISON_DOCTYPE, comparison_name)
	doc.check_permission("write")
	fetched = 0
	if not doc.get("items") and (doc.material_request or doc.bom):
		fetched = _fetch_source_items(doc)
	elif doc.material_request:
		_sync_remaining_mr_items(doc)
	unquoted_items = run_comparison(doc)
	doc.save()
	return {
		"unquoted_items": unquoted_items,
		"row_count": len(doc.get("rows", [])),
		"fetched": fetched,
	}


def run_comparison(doc):
	"""Fill the comparison rows from the demand items via the report engine.

	Only supplier rows with an actual price source are stored; the best-priced
	row per item is pre-selected and flagged. Returns item codes with no quote.
	"""
	if doc.material_request:
		_sync_remaining_mr_items(doc)
	items = [
		{"item_code": row.item_code, "item_name": row.item_name, "qty": flt(row.qty)}
		for row in doc.get("items", [])
	]
	doc.set("rows", [])
	doc.set("supplier_summary", [])
	if not items:
		doc.status = "Draft"
		return []

	on_date = getdate(today())
	company_currency = (
		frappe.get_cached_value("Company", doc.company, "default_currency") if doc.company else None
	)
	item_codes = [item["item_code"] for item in items]
	rules_by_item = engine._get_tier_rules_by_item(item_codes, doc.company, on_date)
	quotes = engine._get_quotation_rows_by_item(item_codes)
	prices = engine._get_item_prices_by_item(item_codes, on_date)
	po_rates = engine._get_po_rates_by_item(item_codes)
	suppliers = engine._get_suppliers_universe(rules_by_item, quotes, prices)

	unquoted_items = []
	item_rows_by_index = {}
	for item_index, item in enumerate(items):
		item_rows = []
		for name, supplier in suppliers.items():
			row_data = engine._build_supplier_row(
				name,
				supplier,
				item["item_code"],
				item["qty"],
				rules_by_item.get(item["item_code"], []),
				quotes.get((item["item_code"], name)),
				prices.get((item["item_code"], name)),
				po_rates.get((item["item_code"], name)),
				company_currency,
				on_date,
			)
			if row_data.get("price_source") and row_data.get("recommended_total") is not None:
				item_rows.append(row_data)

		if not item_rows:
			unquoted_items.append(item["item_code"])
			continue

		item_rows.sort(
			key=lambda row: (
				row["recommended_total"] is None,
				row["recommended_total"] if row["recommended_total"] is not None else 0,
				row["supplier"],
			)
		)
		item_rows_by_index[item_index] = item_rows

	# Prefer one supplier only when it has a valid price for every demand row.
	supplier_totals = {}
	supplier_indexes = {}
	for item_index, item_rows in item_rows_by_index.items():
		for row_data in item_rows:
			supplier = row_data["supplier"]
			supplier_indexes.setdefault(supplier, set()).add(item_index)
			supplier_totals[supplier] = supplier_totals.get(supplier, 0) + flt(row_data["recommended_total"])
	full_indexes = set(range(len(items)))
	full_suppliers = [supplier for supplier, indexes in supplier_indexes.items() if indexes == full_indexes]
	preferred_supplier = None
	preferred_suppliers = set()
	if full_suppliers:
		preferred_supplier = sorted(full_suppliers, key=lambda supplier: (supplier_totals[supplier], supplier))[0]
		preferred_suppliers.add(preferred_supplier)
	else:
		# When no supplier covers every item, suppliers with the same coverage
		# set compete as a basket; keep only the cheapest supplier for each set.
		coverage_groups = {}
		for supplier, indexes in supplier_indexes.items():
			coverage_groups.setdefault(frozenset(indexes), []).append(supplier)
		for suppliers_in_group in coverage_groups.values():
			winner = sorted(suppliers_in_group, key=lambda supplier: (supplier_totals[supplier], supplier))[0]
			preferred_suppliers.add(winner)

	for supplier in sorted(supplier_indexes):
		coverage_count = len(supplier_indexes[supplier])
		doc.append("supplier_summary", {
			"supplier": supplier,
			"coverage_count": coverage_count,
			"coverage_rate": coverage_count * 100 / len(items),
			"recommended_total": supplier_totals[supplier],
			"full_coverage": 1 if coverage_count == len(items) else 0,
			"is_preferred": 1 if supplier in preferred_suppliers else 0,
		})

	for item_index, item_rows in item_rows_by_index.items():
		candidate_suppliers = [row["supplier"] for row in item_rows if row["supplier"] in preferred_suppliers]
		selected_supplier = sorted(candidate_suppliers, key=lambda supplier: (supplier_totals[supplier], supplier))[0] if candidate_suppliers else item_rows[0]["supplier"]
		for index, row_data in enumerate(item_rows):
			doc.append(
				"rows",
				{
					"selected": 1 if row_data["supplier"] == selected_supplier else 0,
					"is_best_item": 1 if row_data["supplier"] == selected_supplier else 0,
					"item_code": items[item_index]["item_code"],
					"item_name": items[item_index].get("item_name"),
					"supplier": row_data["supplier"],
					"supplier_name": row_data["supplier_name"],
					"price_source": row_data["price_source"],
					"demanded_qty": items[item_index]["qty"],
					"recommended_qty": row_data["recommended_qty"],
					"recommended_rate": row_data["recommended_rate"],
					"recommended_total": row_data["recommended_total"],
					"order_qty": row_data["recommended_qty"],
					"order_total": (
						flt(row_data["recommended_qty"]) * flt(row_data["recommended_rate"])
						if row_data["recommended_qty"] is not None and row_data["recommended_rate"] is not None
						else None
					),
					"direct_total": row_data["direct_total"],
					"savings": row_data["savings"],
					"min_order_qty": row_data["min_order_qty"],
					"quote_valid_till": row_data["quote_valid_till"],
					"quote_expired": (
						1
						if row_data.get("quote_valid_till") and getdate(row_data["quote_valid_till"]) < on_date
						else 0
					),
					"payment_terms": row_data["payment_terms"],
					"note": row_data["note"],
				},
			)

	doc.status = "Compared" if doc.get("rows") else "Draft"
	return unquoted_items


@frappe.whitelist()
def fetch_source_items(comparison_name):
	"""Replace the demand items from the linked Material Request or BOM.

	Clears comparison rows and resets the status to Draft so the comparison is
	re-run against the fresh demand list.
	"""
	doc = frappe.get_doc(COMPARISON_DOCTYPE, comparison_name)
	doc.check_permission("write")
	if doc.status == "PO Created":
		frappe.throw(_("This comparison has already generated Purchase Orders."))
	count = _fetch_source_items(doc)
	doc.save()
	return count


def _fetch_source_items(doc):
	"""Pull demand items from the document's Material Request or BOM. Returns the count."""
	items = []
	if doc.material_request:
		mr = frappe.get_doc("Material Request", doc.material_request)
		if mr.docstatus == 2:
			frappe.throw(_("The selected Material Request is cancelled."))
		if mr.material_request_type != "Purchase":
			frappe.throw(_("Supplier comparison is only available for Purchase Material Requests."))
		if mr.get("custom_purchase_scene") == "零星采购":
			frappe.throw(_("Supplier comparison is not available for miscellaneous purchase requests."))
		for row in mr.items:
			if not row.item_code:
				continue
			remaining_qty = _remaining_mr_qty(row)
			if remaining_qty <= 0:
				continue
			items.append(
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"qty": remaining_qty,
					"uom": row.uom,
					"warehouse": row.get("warehouse"),
					"material_request_item": row.name,
				}
			)
	elif doc.bom:
		bom_items, error = engine._get_basket_items(
			frappe._dict({"compare_by": "BOM", "bom": doc.bom, "bom_qty": doc.bom_qty})
		)
		if error:
			frappe.throw(error)
		items = bom_items
	else:
		frappe.throw(_("Please set a Material Request or a BOM first."))

	if not items:
		frappe.throw(_("The source document has no items."))

	doc.set("items", [])
	for item in items:
		if not item.get("warehouse"):
			item["warehouse"] = _default_warehouse(item["item_code"], doc.company)
		doc.append("items", item)
	doc.set("rows", [])
	doc.status = "Draft"
	return len(doc.get("items", []))


def _remaining_mr_qty(row):
	"""Return the un-ordered quantity in the Material Request row's UOM."""
	conversion = flt(row.get("conversion_factor")) or 1
	stock_qty = flt(row.get("stock_qty")) or flt(row.get("qty")) * conversion
	ordered_qty = flt(row.get("ordered_qty"))
	return max(flt(stock_qty - ordered_qty) / conversion, 0)


def _sync_remaining_mr_items(doc):
	"""Refresh saved comparison demand from the linked MR before re-comparing."""
	mr = frappe.get_doc("Material Request", doc.material_request)
	remaining = {row.name: _remaining_mr_qty(row) for row in mr.items if row.item_code}
	kept = []
	for row in doc.get("items", []):
		if row.material_request_item in remaining:
			qty = remaining[row.material_request_item]
			if qty <= 0:
				continue
			row.qty = qty
		kept.append(row)
	doc.set("items", kept)


@frappe.whitelist()
def create_po_drafts(comparison_name):
	"""Create PO drafts from the selected comparison rows.

	Rows are merged into each supplier's open draft PO (see purchase_order_draft);
	MR line references are carried over so the Material Request tracks ordering.
	"""
	doc = frappe.get_doc(COMPARISON_DOCTYPE, comparison_name)
	doc.check_permission("write")

	rows = [row for row in doc.get("rows", []) if row.selected]
	if not rows:
		frappe.throw(_("Please select at least one comparison row."))

	mr_item_map = {row.item_code: row.material_request_item for row in doc.get("items", [])}
	warehouse_map = {row.item_code: row.get("warehouse") for row in doc.get("items", [])}
	purchase_orders = []
	skipped = []
	for row in rows:
		qty = flt(row.get("order_qty")) or flt(row.recommended_qty)
		if qty <= 0 or row.recommended_rate is None:
			skipped.append(f"{row.item_code} / {row.supplier}")
			continue
		result = add_item_to_supplier_po_draft(
			supplier=row.supplier,
			item_code=row.item_code,
			qty=qty,
			rate=row.recommended_rate,
			company=doc.company,
			payment_terms=row.payment_terms,
			material_request=doc.material_request,
			material_request_item=mr_item_map.get(row.item_code),
			purchase_comparison=doc.name,
			warehouse=warehouse_map.get(row.item_code),
		)
		if result["purchase_order"] not in purchase_orders:
			purchase_orders.append(result["purchase_order"])

	if skipped:
		frappe.msgprint(_("Rows without a recommended price were skipped: {0}").format(", ".join(skipped)))
	if not purchase_orders:
		frappe.throw(_("No Purchase Order could be created from the selected rows."))

	doc.db_set("purchase_orders", ", ".join(purchase_orders))
	doc.db_set("status", "PO Created")
	return purchase_orders


@frappe.whitelist()
def create_rfq(comparison_name, suppliers):
	"""Create a Request for Quotation for the comparison's unquoted items."""
	doc = frappe.get_doc(COMPARISON_DOCTYPE, comparison_name)
	doc.check_permission("write")
	if isinstance(suppliers, str):
		suppliers = frappe.parse_json(suppliers)
	suppliers = [supplier for supplier in (suppliers or []) if supplier]
	if not suppliers:
		frappe.throw(_("Please select at least one supplier."))

	unquoted = _get_unquoted_items(doc)
	if not unquoted:
		frappe.throw(_("No unquoted items to request for quotation."))

	rfq = frappe.get_doc(
		{
			"doctype": "Request for Quotation",
			"company": doc.company,
			"transaction_date": getdate(),
			"status": "Draft",
			"subject": _("Request for quotation of unquoted items ({0})").format(doc.name),
			"suppliers": [{"supplier": supplier} for supplier in suppliers],
			"items": [_rfq_item(doc, item) for item in unquoted],
		}
	)
	rfq.insert()
	return rfq.name


def _get_unquoted_items(doc):
	"""Demand items that no comparison row priced."""
	quoted = {row.item_code for row in doc.get("rows", [])}
	return [row for row in doc.get("items", []) if row.item_code not in quoted]


def _rfq_item(doc, item):
	stock_uom = item.get("uom") or frappe.db.get_value("Item", item.item_code, "stock_uom")
	return {
		"item_code": item.item_code,
		"qty": flt(item.qty),
		"uom": stock_uom,
		"stock_uom": stock_uom,
		"conversion_factor": 1,
		"schedule_date": getdate(),
		"material_request": doc.material_request or None,
		"material_request_item": item.get("material_request_item") or None,
	}


# Dashboard connections
# ---------------------


def get_material_request_dashboard(data):
	"""Show linked Purchase Comparisons on the Material Request connections panel."""
	data.transactions.append({"label": _("Purchase Comparison"), "items": ["Purchase Comparison"]})
	return data


def get_purchase_comparison_dashboard(data):
	"""Show generated Purchase Orders on the Purchase Comparison connections panel."""
	data.transactions.append({"label": _("Purchase Orders"), "items": ["Purchase Order"]})
	return data
