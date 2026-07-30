import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

STAR = "⭐"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	mode = filters.get("compare_by") or "Single Item"

	if mode == "Single Item":
		if not filters.get("item_code") or not flt(filters.get("qty")):
			return (
				get_columns(filters),
				[],
				_("Please select an Item and enter a demanded quantity."),
				None,
				[],
				1,
			)
		data = get_recommendation_rows(filters)
		message = None if data else _("No quotations or pricing rules found for this item.")
		return get_columns(filters), data, message, None, get_summary(data), 1

	items, error_message = _get_basket_items(filters)
	if error_message:
		return get_columns(filters), [], error_message, None, [], 1

	data = get_basket_rows(filters, items)
	message = None if data else _("No quotations or pricing rules found for the selected items.")
	return get_columns(filters), data, message, None, get_basket_summary(data, items), 1


def get_columns(filters=None):
	mode = (filters or {}).get("compare_by") or "Single Item"
	columns = [
		{"label": _("Best"), "fieldname": "recommended", "fieldtype": "Data", "width": 60},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 170},
	]
	if mode != "Single Item":
		columns += [
			{"label": _("Coverage"), "fieldname": "coverage", "fieldtype": "Data", "width": 70},
			{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
			{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		]
	columns += [
		{"label": _("Price Source"), "fieldname": "price_source", "fieldtype": "Data", "width": 110},
		{"label": _("Demanded Qty"), "fieldname": "demanded_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Recommended Qty"), "fieldname": "recommended_qty", "fieldtype": "Float", "width": 115},
		{"label": _("Direct Rate"), "fieldname": "direct_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Direct Total"), "fieldname": "direct_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Recommended Rate"), "fieldname": "recommended_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Recommended Total"), "fieldname": "recommended_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Savings"), "fieldname": "savings", "fieldtype": "Currency", "width": 100},
		{"label": _("MOQ"), "fieldname": "min_order_qty", "fieldtype": "Float", "width": 80},
	]
	if mode == "Single Item":
		columns += [
			{"label": _("Last PO Rate"), "fieldname": "last_transaction_rate", "fieldtype": "Currency", "width": 100},
			{"label": _("Lead Time (Days)"), "fieldname": "lead_time_days", "fieldtype": "Int", "width": 100},
		]
	columns.append({"label": _("Quote Valid Till"), "fieldname": "quote_valid_till", "fieldtype": "Date", "width": 110})
	columns.append({"label": _("Payment Terms"), "fieldname": "payment_terms", "fieldtype": "Link", "options": "Payment Terms Template", "width": 130})
	if mode != "Single Item":
		columns.append({"label": _("Missing Items"), "fieldname": "missing_items", "fieldtype": "Data", "width": 160})
	columns.append({"label": _("Note"), "fieldname": "note", "fieldtype": "Data", "width": 180})
	return columns


def get_summary(data):
	priced = [row for row in data if row.get("recommended_total") is not None]
	if not priced:
		return []

	best = priced[0]
	savings = flt(best.get("savings"))
	return [
		{"label": _("Best Supplier"), "value": best.get("supplier_name") or best.get("supplier"), "datatype": "Data", "indicator": "Green"},
		{"label": _("Recommended Qty"), "value": best.get("recommended_qty"), "datatype": "Float", "indicator": "Green"},
		{"label": _("Savings"), "value": savings, "datatype": "Currency", "indicator": "Green" if savings > 0 else "Blue"},
		{"label": _("Suppliers Compared"), "value": len(priced), "datatype": "Int", "indicator": "Blue"},
	]


def get_basket_summary(data, items):
	total_rows = [row for row in data if row.get("row_type") == "supplier_total"]
	if not total_rows:
		return []

	best = next((row for row in total_rows if row.get("recommended") == STAR), None)
	unquoted = sum(
		1
		for item in items
		if not any(
			row.get("row_type") == "detail" and row.get("item_code") == item["item_code"] and row.get("price_source")
			for row in data
		)
	)
	savings = flt(best.get("savings")) if best else 0
	return [
		{"label": _("Basket Best Supplier"), "value": (best.get("supplier_name") or best.get("supplier")) if best else "—", "datatype": "Data", "indicator": "Green" if best else "Gray"},
		{"label": _("Basket Recommended Total"), "value": best.get("recommended_total") if best else 0, "datatype": "Currency", "indicator": "Green" if best else "Gray"},
		{"label": _("Total Savings"), "value": savings, "datatype": "Currency", "indicator": "Green" if savings > 0 else "Blue"},
		{"label": _("Items Without Any Quote"), "value": unquoted, "datatype": "Int", "indicator": "Red" if unquoted else "Blue"},
	]


# Tier engine (pure functions, unit-testable)
# -------------------------------------------


def _normalize_tiers(rules):
	"""Turn raw Pricing Rule rows into sorted qty tiers. max_qty 0/None means unlimited."""
	tiers = []
	for rule in rules:
		tiers.append(
			{
				"min_qty": flt(rule.get("min_qty")),
				"max_qty": flt(rule.get("max_qty")),
				"rate": flt(rule.get("rate")),
				"priority": cint(rule.get("priority")),
			}
		)
	tiers.sort(key=lambda tier: (tier["min_qty"], -tier["priority"]))
	return tiers


def _hit_tier(tiers, qty):
	"""Return the tier covering qty: highest min_qty <= qty whose max_qty covers it; priority breaks ties."""
	candidates = [
		tier
		for tier in tiers
		if tier["min_qty"] <= qty and (not tier["max_qty"] or qty <= tier["max_qty"])
	]
	if not candidates:
		return None
	return max(candidates, key=lambda tier: (tier["min_qty"], tier["priority"]))


def _best_purchase(tiers, demanded_qty):
	"""Compute direct-purchase price and the round-up recommendation for one supplier.

	Tries the demanded qty plus every higher tier's min_qty and picks the cheapest
	total; ties go to the smaller qty. Savings compare against the no-round-up
	baseline: the demanded qty as-is, or — when the demand hits no tier — the
	smallest tier above the demand (the cheapest way to buy at all).
	"""
	direct = _hit_tier(tiers, demanded_qty)
	direct_rate = direct["rate"] if direct else None
	direct_total = demanded_qty * direct_rate if direct else None

	candidate_qtys = set()
	if direct:
		candidate_qtys.add(demanded_qty)
	for tier in tiers:
		if tier["min_qty"] > demanded_qty:
			candidate_qtys.add(tier["min_qty"])

	best_qty = best_rate = best_total = None
	for qty in sorted(candidate_qtys):
		tier = _hit_tier(tiers, qty)
		if not tier:
			continue
		total = qty * tier["rate"]
		if (
			best_total is None
			or total < best_total - 1e-9
			or (abs(total - best_total) <= 1e-9 and qty < best_qty)
		):
			best_qty, best_rate, best_total = qty, tier["rate"], total

	baseline_qty = baseline_total = None
	if direct_total is not None:
		baseline_qty, baseline_total = demanded_qty, direct_total
	else:
		entry = next((tier for tier in tiers if tier["min_qty"] > demanded_qty), None)
		if entry:
			baseline_qty = entry["min_qty"]
			baseline_total = baseline_qty * entry["rate"]

	savings = None
	if baseline_total is not None and best_total is not None:
		savings = baseline_total - best_total

	return {
		"direct_rate": direct_rate,
		"direct_total": direct_total,
		"recommended_qty": best_qty,
		"recommended_rate": best_rate,
		"recommended_total": best_total,
		"savings": savings,
		"baseline_qty": baseline_qty,
		"baseline_total": baseline_total,
	}


# Data assembly
# -------------


def get_recommendation_rows(filters):
	on_date = getdate(today())
	company_currency = (
		frappe.get_cached_value("Company", filters.company, "default_currency")
		if filters.get("company")
		else None
	)
	item_codes = [filters.item_code]

	rules_by_item = _get_tier_rules_by_item(item_codes, filters.get("company"), on_date)
	quotes = _get_quotation_rows_by_item(item_codes)
	prices = _get_item_prices_by_item(item_codes, on_date)
	po_rates = _get_po_rates_by_item(item_codes)
	suppliers = _get_suppliers_universe(rules_by_item, quotes, prices, filters.get("supplier"))

	rows = [
		_build_supplier_row(
			name,
			supplier,
			filters.item_code,
			flt(filters.qty),
			rules_by_item.get(filters.item_code, []),
			quotes.get((filters.item_code, name)),
			prices.get((filters.item_code, name)),
			po_rates.get((filters.item_code, name)),
			company_currency,
			on_date,
		)
		for name, supplier in suppliers.items()
	]
	_sort_and_star(rows)
	return rows


def get_basket_rows(filters, items):
	on_date = getdate(today())
	company_currency = (
		frappe.get_cached_value("Company", filters.company, "default_currency")
		if filters.get("company")
		else None
	)
	item_codes = [item["item_code"] for item in items]

	rules_by_item = _get_tier_rules_by_item(item_codes, filters.get("company"), on_date)
	quotes = _get_quotation_rows_by_item(item_codes)
	prices = _get_item_prices_by_item(item_codes, on_date)
	po_rates = _get_po_rates_by_item(item_codes)
	suppliers = _get_suppliers_universe(rules_by_item, quotes, prices, filters.get("supplier"))
	if not suppliers:
		return []

	detail_rows = []
	for item in items:
		item_rows = []
		for name, supplier in suppliers.items():
			row = _build_supplier_row(
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
			row["row_type"] = "detail"
			row["item_code"] = item["item_code"]
			row["item_name"] = item.get("item_name")
			item_rows.append(row)
		_sort_and_star(item_rows)
		detail_rows.extend(item_rows)

	total_rows = [
		_build_supplier_total(
			name,
			supplier,
			len(items),
			[row for row in detail_rows if row["supplier"] == name],
		)
		for name, supplier in suppliers.items()
	]
	total_rows.sort(
		key=lambda row: (
			row["coverage_count"] < row["item_count"],
			row["recommended_total"] is None,
			row["recommended_total"] if row["recommended_total"] is not None else 0,
			row["supplier"],
		)
	)
	best_index = _pick_basket_best(total_rows)
	if best_index is not None:
		total_rows[best_index]["recommended"] = STAR

	return (
		[{"row_type": "section", "supplier": _("Supplier Basket Summary")}]
		+ total_rows
		+ [{"row_type": "section", "supplier": _("Item Details")}]
		+ detail_rows
	)


def _build_supplier_total(name, supplier, item_count, rows):
	"""Aggregate one supplier's per-item rows into a basket-level comparison row.

	Pure function (unit-testable): coverage counts items with any price source;
	totals only sum items where the figure is computable.
	"""
	covered = [row for row in rows if row.get("price_source")]
	direct_values = [row["direct_total"] for row in covered if row.get("direct_total") is not None]
	recommended_values = [row["recommended_total"] for row in covered if row.get("recommended_total") is not None]
	savings_values = [row["savings"] for row in covered if row.get("savings") is not None]
	missing = [row["item_code"] for row in rows if not row.get("price_source")]

	notes = []
	if missing:
		notes.append(_("Missing prices for {0} item(s)").format(len(missing)))

	return {
		"row_type": "supplier_total",
		"recommended": "",
		"supplier": name,
		"supplier_name": supplier.supplier_name,
		"coverage_count": len(covered),
		"item_count": item_count,
		"coverage": f"{len(covered)}/{item_count}",
		"direct_total": sum(direct_values) if direct_values else None,
		"recommended_total": sum(recommended_values) if recommended_values else None,
		"savings": sum(savings_values) if savings_values else None,
		"missing_items": ", ".join(missing[:3]) + (" …" if len(missing) > 3 else ""),
		"payment_terms": supplier.payment_terms,
		"note": "; ".join(notes),
	}


def _pick_basket_best(total_rows):
	"""Return the index of the cheapest fully-covering supplier, or None."""
	best_index = None
	for index, row in enumerate(total_rows):
		if row["coverage_count"] < row["item_count"] or row["recommended_total"] is None:
			continue
		if best_index is None or row["recommended_total"] < total_rows[best_index]["recommended_total"] - 1e-9:
			best_index = index
	return best_index


def _get_basket_items(filters):
	"""Resolve the item basket [{item_code, item_name, qty}] for non-single modes."""
	mode = filters.get("compare_by")

	if mode == "Multiple Items":
		item_codes = filters.get("items") or []
		if isinstance(item_codes, str):
			# Route options / deep links arrive as a JSON array string.
			try:
				import json

				parsed = json.loads(item_codes)
				item_codes = parsed if isinstance(parsed, list) else [item_codes]
			except ValueError:
				item_codes = [code.strip() for code in item_codes.split(",") if code.strip()]
		if not item_codes or not flt(filters.get("qty")):
			return None, _("Please select at least one Item and enter a demanded quantity.")
		names = _get_item_names(item_codes)
		return (
			[{"item_code": code, "item_name": names.get(code), "qty": flt(filters.qty)} for code in item_codes],
			None,
		)

	if mode == "BOM":
		if not filters.get("bom"):
			return None, _("Please select a BOM.")
		bom_doc = frappe.get_doc("BOM", filters.bom)
		bom_doc.get_exploded_items()
		bom_qty = flt(filters.get("bom_qty")) or 1
		merged = {}
		for key, row in (bom_doc.cur_exploded_items or {}).items():
			item_code = key if isinstance(key, str) else key[0]
			entry = merged.setdefault(
				item_code, {"item_code": item_code, "item_name": row.get("item_name"), "qty": 0}
			)
			entry["qty"] += flt(row.get("stock_qty")) * bom_qty
		items = list(merged.values())
		if not items:
			return None, _("The selected BOM has no material items.")
		return items, None

	if mode == "Material Request":
		if not filters.get("material_request"):
			return None, _("Please select a Material Request.")
		mr = frappe.get_doc("Material Request", filters.material_request)
		if mr.docstatus == 2:
			return None, _("The selected Material Request is cancelled.")
		items = [
			{"item_code": row.item_code, "item_name": row.item_name, "qty": flt(row.qty)}
			for row in mr.items
			if row.item_code
		]
		if not items:
			return None, _("The selected Material Request has no items.")
		return items, None

	return None, _("Please select an Item and enter a demanded quantity.")


def _get_item_names(item_codes):
	if not item_codes:
		return {}
	return {
		row.name: row.item_name
		for row in frappe.get_all("Item", filters={"name": ("in", item_codes)}, fields=["name", "item_name"])
	}


def _get_suppliers_universe(rules_by_item, quotes, prices, supplier_filter=None):
	supplier_names = set()
	group_names = set()
	for rules in rules_by_item.values():
		supplier_names |= {rule.supplier for rule in rules if rule.supplier}
		group_names |= {rule.supplier_group for rule in rules if not rule.supplier and rule.supplier_group}
	supplier_names |= {supplier for (_item_code, supplier) in quotes}
	supplier_names |= {supplier for (_item_code, supplier) in prices}

	suppliers = {}
	if supplier_names or group_names:
		for supplier in frappe.get_all(
			"Supplier",
			fields=["name", "supplier_name", "supplier_group", "payment_terms"],
		):
			if supplier.name in supplier_names or (
				supplier.supplier_group and supplier.supplier_group in group_names
			):
				suppliers[supplier.name] = supplier

	if supplier_filter:
		suppliers = {supplier_filter: suppliers[supplier_filter]} if supplier_filter in suppliers else {}
	return suppliers


def _sort_and_star(rows):
	rows.sort(
		key=lambda row: (
			row["recommended_total"] is None,
			row["recommended_total"] if row["recommended_total"] is not None else 0,
			row["supplier"],
		)
	)
	if rows and rows[0]["recommended_total"] is not None:
		rows[0]["recommended"] = STAR


def _build_supplier_row(
	name, supplier, item_code, demanded_qty, rules, quote, price, po_rate, company_currency, on_date
):
	def currency_ok(currency):
		return not currency or not company_currency or currency == company_currency

	direct_rules = [rule for rule in rules if rule.supplier == name]
	group_rules = [
		rule
		for rule in rules
		if not rule.supplier and rule.supplier_group and rule.supplier_group == supplier.supplier_group
	]
	tier_rules = direct_rules or group_rules

	row = {
		"recommended": "",
		"supplier": name,
		"supplier_name": supplier.supplier_name,
		"price_source": "",
		"demanded_qty": demanded_qty,
		"recommended_qty": None,
		"direct_rate": None,
		"direct_total": None,
		"recommended_rate": None,
		"recommended_total": None,
		"savings": None,
		"min_order_qty": None,
		"last_transaction_rate": po_rate["rate"] if po_rate else None,
		"quote_valid_till": quote["valid_till"] if quote else None,
		"lead_time_days": price["lead_time_days"] if price else None,
		"payment_terms": supplier.payment_terms,
		"note": "",
	}
	notes = []

	if tier_rules and all(currency_ok(rule.get("currency")) for rule in tier_rules):
		tiers = _normalize_tiers(tier_rules)
		row.update(_best_purchase(tiers, demanded_qty))
		row["price_source"] = _("Pricing Rule")
		row["min_order_qty"] = min((tier["min_qty"] for tier in tiers), default=None)
		if not direct_rules:
			notes.append(_("Group-level pricing rule"))
	elif quote and currency_ok(quote.get("currency")):
		quote_tiers = _quotation_tiers(quote)
		if quote_tiers:
			row.update(_best_purchase(quote_tiers, demanded_qty))
			row["price_source"] = _("Supplier Quotation")
			row["min_order_qty"] = min((tier["min_qty"] for tier in quote_tiers), default=None)
		else:
			rate = flt(quote["rows"][0]["rate"])
			row.update(
				price_source=_("Supplier Quotation"),
				direct_rate=rate,
				direct_total=demanded_qty * rate,
				recommended_qty=demanded_qty,
				recommended_rate=rate,
				recommended_total=demanded_qty * rate,
				savings=0,
			)
		if quote.get("valid_till") and getdate(quote["valid_till"]) < on_date:
			notes.append(_("Quote expired"))
	elif price and currency_ok(price.get("currency")):
		rate = flt(price["price_list_rate"])
		row.update(
			price_source=_("Item Price"),
			direct_rate=rate,
			direct_total=demanded_qty * rate,
			recommended_qty=demanded_qty,
			recommended_rate=rate,
			recommended_total=demanded_qty * rate,
			savings=0,
		)
	elif tier_rules or quote or price:
		notes.append(_("Non-default currency quote not compared"))

	if row["direct_total"] is None and row.get("price_source"):
		notes.append(_("Demand matches no price tier"))
	baseline_qty = flt(row.get("baseline_qty"))
	if baseline_qty and flt(row.get("recommended_qty")) > baseline_qty:
		notes.append(
			_("Buying {0} units costs less in total than the {1}-unit minimum").format(
				"{:g}".format(flt(row["recommended_qty"])), "{:g}".format(baseline_qty)
			)
		)

	row["note"] = "; ".join(notes)
	return row


# Source queries
# --------------


def _get_tier_rules_by_item(item_codes, company, on_date):
	rules = frappe.get_all(
		"Pricing Rule",
		filters={
			"buying": 1,
			"disable": 0,
			"apply_on": "Item Code",
			"rate_or_discount": "Rate",
		},
		fields=[
			"name",
			"supplier",
			"supplier_group",
			"company",
			"currency",
			"min_qty",
			"max_qty",
			"rate",
			"priority",
			"valid_from",
			"valid_upto",
		],
	)
	rules = [
		rule
		for rule in rules
		if (not rule.company or not company or rule.company == company)
		and (not rule.valid_from or getdate(rule.valid_from) <= on_date)
		and (not rule.valid_upto or getdate(rule.valid_upto) >= on_date)
	]
	if not rules:
		return {}

	matched = frappe.get_all(
		"Pricing Rule Item Code",
		filters={"parent": ("in", [rule.name for rule in rules]), "item_code": ("in", item_codes)},
		fields=["parent", "item_code"],
	)
	items_by_parent = {}
	for row in matched:
		items_by_parent.setdefault(row.parent, []).append(row.item_code)

	rules_by_item = {code: [] for code in item_codes}
	for rule in rules:
		for code in items_by_parent.get(rule.name, []):
			rules_by_item[code].append(rule)
	return rules_by_item


def _get_quotation_rows_by_item(item_codes):
	"""Return quantity price points from every submitted Supplier Quotation, per (item, supplier)."""
	rows = frappe.db.sql(
		"""
		SELECT sq.supplier, sq.name AS quotation, sq.valid_till, sq.currency,
			sqi.item_code, sqi.idx, sqi.qty, sqi.rate
		FROM `tabSupplier Quotation` sq
		JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		WHERE sq.docstatus = 1 AND sqi.item_code IN %(item_codes)s
		ORDER BY sq.transaction_date DESC, sq.modified DESC, sqi.idx ASC
		""",
		{"item_codes": tuple(item_codes)},
		as_dict=True,
	)
	by_item = {}
	for row in rows:
		by_item.setdefault(row["item_code"], []).append(row)

	quotes = {}
	for code, item_rows in by_item.items():
		for supplier, quote in _merge_quotation_rows(item_rows).items():
			quotes[(code, supplier)] = quote
	return quotes


def _merge_quotation_rows(rows):
	"""Merge SQL rows (newest quotation first) into per-supplier price points.

	Every submitted quotation row for the item is a quantity price point (row
	qty = tier start, row rate = tier price); at the same quantity the newer
	quotation wins. valid_till/currency come from the supplier's latest quote.
	"""
	by_supplier = {}
	seen_qtys = {}
	for row in rows:
		entry = by_supplier.get(row["supplier"])
		if entry is None:
			entry = by_supplier[row["supplier"]] = {
				"quotation": row["quotation"],
				"valid_till": row["valid_till"],
				"currency": row["currency"],
				"rows": [],
			}
			seen_qtys[row["supplier"]] = set()
		if row["qty"] in seen_qtys[row["supplier"]]:
			continue  # At the same quantity the newer quotation wins.
		seen_qtys[row["supplier"]].add(row["qty"])
		entry["rows"].append(row)
	return by_supplier


def _quotation_tiers(quote):
	"""Build qty tiers when the quotation prices the item in multiple qty rows.

	A single-row quotation is a flat price for any qty and returns None.
	Later lines override earlier ones at the same qty break.
	"""
	rows = quote.get("rows") or []
	if len(rows) < 2:
		return None
	by_qty = {}
	for row in rows:
		by_qty[flt(row.get("qty"))] = flt(row.get("rate"))
	if len(by_qty) < 2:
		return None
	return _normalize_tiers(
		[{"min_qty": qty, "max_qty": 0, "rate": rate} for qty, rate in by_qty.items()]
	)


def _get_item_prices_by_item(item_codes, on_date):
	prices = frappe.get_all(
		"Item Price",
		filters={"item_code": ("in", item_codes), "buying": 1, "supplier": ("is", "set")},
		fields=[
			"supplier",
			"item_code",
			"price_list_rate",
			"currency",
			"valid_from",
			"valid_upto",
			"lead_time_days",
		],
		order_by="valid_from desc, modified desc",
	)
	latest = {}
	for price in prices:
		if price.valid_from and getdate(price.valid_from) > on_date:
			continue
		if price.valid_upto and getdate(price.valid_upto) < on_date:
			continue
		latest.setdefault((price.item_code, price.supplier), price)
	return latest


def _get_po_rates_by_item(item_codes):
	rows = frappe.db.sql(
		"""
		SELECT po.supplier, poi.item_code, poi.rate
		FROM `tabPurchase Order` po
		JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE po.docstatus = 1 AND poi.item_code IN %(item_codes)s
		ORDER BY po.transaction_date DESC, po.modified DESC
		""",
		{"item_codes": tuple(item_codes)},
		as_dict=True,
	)
	latest = {}
	for row in rows:
		latest.setdefault((row["item_code"], row["supplier"]), row)
	return latest
