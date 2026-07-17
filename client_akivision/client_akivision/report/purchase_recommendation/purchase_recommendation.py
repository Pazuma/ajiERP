import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

STAR = "⭐"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("item_code") or not flt(filters.get("qty")):
		return (
			get_columns(),
			[],
			_("Please select an Item and enter a demanded quantity."),
			None,
			[],
			1,
		)

	data = get_recommendation_rows(filters)
	message = None
	if not data:
		message = _("No quotations or pricing rules found for this item.")
	return get_columns(), data, message, None, get_summary(data), 1


def get_columns():
	return [
		{"label": _("Best"), "fieldname": "recommended", "fieldtype": "Data", "width": 60},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
		{"label": _("Price Source"), "fieldname": "price_source", "fieldtype": "Data", "width": 120},
		{"label": _("Demanded Qty"), "fieldname": "demanded_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Recommended Qty"), "fieldname": "recommended_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Direct Rate"), "fieldname": "direct_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Direct Total"), "fieldname": "direct_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Recommended Rate"), "fieldname": "recommended_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Recommended Total"), "fieldname": "recommended_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Savings"), "fieldname": "savings", "fieldtype": "Currency", "width": 100},
		{"label": _("MOQ"), "fieldname": "min_order_qty", "fieldtype": "Float", "width": 80},
		{"label": _("Last PO Rate"), "fieldname": "last_transaction_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Quote Valid Till"), "fieldname": "quote_valid_till", "fieldtype": "Date", "width": 110},
		{"label": _("Lead Time (Days)"), "fieldname": "lead_time_days", "fieldtype": "Int", "width": 100},
		{"label": _("Payment Terms"), "fieldname": "payment_terms", "fieldtype": "Link", "options": "Payment Terms Template", "width": 140},
		{"label": _("Note"), "fieldname": "note", "fieldtype": "Data", "width": 180},
	]


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
	total; ties go to the smaller qty. Savings compare against buying the demanded
	qty as-is (None when the demanded qty hits no tier).
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

	savings = None
	if direct_total is not None and best_total is not None:
		savings = direct_total - best_total

	return {
		"direct_rate": direct_rate,
		"direct_total": direct_total,
		"recommended_qty": best_qty,
		"recommended_rate": best_rate,
		"recommended_total": best_total,
		"savings": savings,
	}


# Data assembly
# -------------


def get_recommendation_rows(filters):
	on_date = getdate(today())
	demanded_qty = flt(filters.qty)
	company_currency = (
		frappe.get_cached_value("Company", filters.company, "default_currency")
		if filters.get("company")
		else None
	)

	rules = _get_item_tier_rules(filters.item_code, filters.get("company"), on_date)
	quotes = _get_latest_quotations(filters.item_code)
	prices = _get_latest_item_prices(filters.item_code, on_date)
	po_rates = _get_last_po_rates(filters.item_code)

	supplier_names = {rule.supplier for rule in rules if rule.supplier}
	supplier_names |= set(quotes) | set(prices)
	group_names = {rule.supplier_group for rule in rules if not rule.supplier and rule.supplier_group}

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

	if filters.get("supplier"):
		suppliers = {filters.supplier: suppliers[filters.supplier]} if filters.supplier in suppliers else {}

	rows = [
		_build_supplier_row(
			name,
			supplier,
			demanded_qty,
			rules,
			quotes,
			prices,
			po_rates,
			company_currency,
			on_date,
		)
		for name, supplier in suppliers.items()
	]

	rows.sort(
		key=lambda row: (
			row["recommended_total"] is None,
			row["recommended_total"] if row["recommended_total"] is not None else 0,
			row["supplier"],
		)
	)
	if rows and rows[0]["recommended_total"] is not None:
		rows[0]["recommended"] = STAR
	return rows


def _build_supplier_row(
	name, supplier, demanded_qty, rules, quotes, prices, po_rates, company_currency, on_date
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
	quote = quotes.get(name)
	price = prices.get(name)

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
		"last_transaction_rate": po_rates[name]["rate"] if name in po_rates else None,
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
		if row["direct_total"] is None:
			notes.append(_("Demand matches no price tier"))
	elif quote and currency_ok(quote.get("currency")):
		quote_tiers = _quotation_tiers(quote)
		if quote_tiers:
			row.update(_best_purchase(quote_tiers, demanded_qty))
			row["price_source"] = _("Supplier Quotation")
			row["min_order_qty"] = min((tier["min_qty"] for tier in quote_tiers), default=None)
			if row["direct_total"] is None:
				notes.append(_("Demand matches no price tier"))
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

	row["note"] = "; ".join(notes)
	return row


# Source queries
# --------------


def _get_item_tier_rules(item_code, company, on_date):
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
		return []

	matched_parents = set(
		frappe.get_all(
			"Pricing Rule Item Code",
			filters={"parent": ("in", [rule.name for rule in rules]), "item_code": item_code},
			pluck="parent",
		)
	)
	return [rule for rule in rules if rule.name in matched_parents]


def _get_latest_quotations(item_code):
	"""Return the latest submitted Supplier Quotation per supplier, with all its rows for the item.

	Multiple rows for the same item in one quotation express the supplier's
	quantity price breaks (row qty = tier start, row rate = tier price).
	"""
	rows = frappe.db.sql(
		"""
		SELECT sq.supplier, sq.name AS quotation, sq.valid_till, sq.currency,
			sqi.idx, sqi.qty, sqi.rate
		FROM `tabSupplier Quotation` sq
		JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		WHERE sq.docstatus = 1 AND sqi.item_code = %s
		ORDER BY sq.transaction_date DESC, sq.modified DESC, sqi.idx ASC
		""",
		(item_code,),
		as_dict=True,
	)
	latest = {}
	for row in rows:
		entry = latest.get(row.supplier)
		if entry is None:
			entry = latest[row.supplier] = {
				"quotation": row.quotation,
				"valid_till": row.valid_till,
				"currency": row.currency,
				"rows": [],
			}
		if row.quotation != entry["quotation"]:
			continue
		entry["rows"].append(row)
	return latest


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


def _get_latest_item_prices(item_code, on_date):
	prices = frappe.get_all(
		"Item Price",
		filters={"item_code": item_code, "buying": 1, "supplier": ("is", "set")},
		fields=[
			"supplier",
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
		latest.setdefault(price.supplier, price)
	return latest


def _get_last_po_rates(item_code):
	rows = frappe.db.sql(
		"""
		SELECT po.supplier, poi.rate
		FROM `tabPurchase Order` po
		JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE po.docstatus = 1 AND poi.item_code = %s
		ORDER BY po.transaction_date DESC, po.modified DESC
		""",
		(item_code,),
		as_dict=True,
	)
	latest = {}
	for row in rows:
		latest.setdefault(row.supplier, row)
	return latest
