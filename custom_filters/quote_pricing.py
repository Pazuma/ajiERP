"""Sync quantity-tier Pricing Rules from supplier quotations.

When a quotation (or a Supplier Quote Import) prices the same item at multiple
quantities (price breaks), each break becomes one buying Pricing Rule so ERPNext
native picking, the Purchase Recommendation report, and the Purchase Comparison
document all share the same tiered prices.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

# Marker written to auto-generated rules' rule_description: "<marker> <doc name>".
# New rules use TIER_RULE_MARKER; older imports used the legacy marker, which is
# still recognized so deployed rules keep being maintained.
TIER_RULE_MARKER = "由供应商报价生成"
TIER_RULE_MARKER_PREFIXES = ("由供应商报价导入", "由供应商报价生成")


def sync_pricing_rules(doc):
	"""Create/update supplier tier Pricing Rules from the import's valid rows.

	Idempotent: rules are matched by (supplier, item, min_qty) and updated in
	place; stale auto-generated tiers are disabled, never deleted. User-created
	rules (without the import marker) are left untouched.
	"""
	tiers_by_item = _build_tiers(doc.get("items") or [])
	for item_code, tiers in tiers_by_item.items():
		_disable_stale_rules(doc, item_code, tiers)
		for tier in tiers:
			_upsert_tier_rule(doc, item_code, tier)
	if tiers_by_item:
		frappe.clear_cache(doctype="Pricing Rule")


def _build_tiers(rows):
	"""Group valid rows into per-item quantity tiers.

	Only items quoted at 2+ distinct quantities become tiers. Rows at the same
	quantity are overridden by the later row (mirrors quotation line order).
	max_qty of each tier is the next tier's min_qty - 1; the top tier is
	unlimited (max_qty = 0), which keeps ERPNext's `min <= qty <= max` picking
	unambiguous across tiers.
	"""
	by_item = {}
	for row in rows:
		item_code = (row.get("item_code") or "").strip()
		qty = flt(row.get("qty"))
		rate = flt(row.get("rate"))
		if not row.get("valid", 1) or not item_code or not qty or not rate:
			continue
		by_item.setdefault(item_code, {})[qty] = rate

	tiers_by_item = {}
	for item_code, qty_rates in by_item.items():
		if len(qty_rates) < 2:
			continue
		sorted_qtys = sorted(qty_rates)
		epsilon = _qty_epsilon(item_code)
		tiers = []
		for index, qty in enumerate(sorted_qtys):
			next_qty = sorted_qtys[index + 1] if index + 1 < len(sorted_qtys) else None
			tiers.append(
				{
					"min_qty": qty,
					"max_qty": (next_qty - epsilon) if next_qty is not None else 0,
					"rate": qty_rates[qty],
				}
			)
		tiers_by_item[item_code] = tiers
	return tiers_by_item


def _qty_epsilon(item_code):
	"""Gap between one tier's max and the next tier's min, by the item's stock UOM.

	Whole-number UOMs use a gap of 1; decimal UOMs (kg, m, …) use a small
	fraction so fractional quantities never fall into a pricing vacuum.
	"""
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	if stock_uom and frappe.get_cached_value("UOM", stock_uom, "must_be_whole_number"):
		return 1
	return 0.000001


def _upsert_tier_rule(doc, item_code, tier):
	valid_from = doc.get("quote_date") or doc.get("transaction_date")
	values = {
		"max_qty": tier["max_qty"],
		"rate": tier["rate"],
		"rate_or_discount": "Rate",
		"currency": doc.currency,
		"company": doc.company,
		"valid_from": getdate(valid_from) if valid_from else None,
		"valid_upto": getdate(doc.valid_till) if doc.get("valid_till") else None,
		# The marker always follows the last writer so cancel cleanup can find it.
		"rule_description": f"{TIER_RULE_MARKER} {doc.name}",
		"disable": 0,
	}
	existing = _find_tier_rule(doc.supplier, item_code, tier["min_qty"])
	if existing:
		frappe.db.set_value("Pricing Rule", existing, values, update_modified=False)
		return existing

	rule = frappe.get_doc(
		{
			"doctype": "Pricing Rule",
			"title": f"{doc.supplier} {item_code} {flt(tier['min_qty']):g}+",
			"apply_on": "Item Code",
			"items": [{"item_code": item_code}],
			"price_or_product_discount": "Price",
			"buying": 1,
			"selling": 0,
			"applicable_for": "Supplier",
			"supplier": doc.supplier,
			"min_qty": tier["min_qty"],
			"rule_description": f"{TIER_RULE_MARKER} {doc.name}",
			**values,
		}
	)
	rule.insert(ignore_permissions=True)
	return rule.name


def _is_auto_marker(description):
	return (description or "").startswith(TIER_RULE_MARKER_PREFIXES)


def _find_tier_rule(supplier, item_code, min_qty):
	rules = frappe.get_all(
		"Pricing Rule",
		filters={"buying": 1, "supplier": supplier, "min_qty": min_qty},
		fields=["name", "rule_description", "disable"],
	)
	for rule in rules:
		if not _is_auto_marker(rule.rule_description):
			continue  # User-created rule; never overwrite it.
		if rule.disable:
			continue
		if frappe.db.exists("Pricing Rule Item Code", {"parent": rule.name, "item_code": item_code}):
			return rule.name  # Active auto rule: update in place.
	for rule in rules:
		if not _is_auto_marker(rule.rule_description) or not rule.disable:
			continue
		if frappe.db.exists("Pricing Rule Item Code", {"parent": rule.name, "item_code": item_code}):
			return rule.name  # Disabled auto rule: revived by the upsert (disable resets to 0).
	return None


def _disable_stale_rules(doc, item_code, tiers):
	"""Disable auto-generated rules for this supplier+item that are not in the new tier set."""
	keep_min_qtys = {flt(tier["min_qty"]) for tier in tiers}
	rules = frappe.get_all(
		"Pricing Rule",
		filters={"buying": 1, "disable": 0, "supplier": doc.supplier},
		fields=["name", "min_qty", "rule_description"],
	)
	for rule in rules:
		if flt(rule.min_qty) in keep_min_qtys:
			continue
		if not _is_auto_marker(rule.rule_description):
			continue
		if not frappe.db.exists("Pricing Rule Item Code", {"parent": rule.name, "item_code": item_code}):
			continue
		frappe.db.set_value("Pricing Rule", rule.name, "disable", 1, update_modified=False)


# Supplier Quotation integration
# ------------------------------


def sync_quotation_tiers(doc):
	"""Sync a submitted Supplier Quotation's prices and stamp its sync status.

	Tier rows become buying Pricing Rules; flat (single-quantity) rows become
	supplier-specific Item Prices. The two price kinds are mutually exclusive
	per item: a tiered item loses its auto Item Prices, a flat item loses its
	auto tier rules — the latest quotation is the single price source. Returns
	the number of synced price points (0 = nothing synced).
	"""
	tiers_by_item = _build_tiers(doc.get("items") or [])
	flat_rows = _flat_price_rows(doc)
	flat_count = _sync_flat_item_prices(doc, flat_rows)
	if tiers_by_item:
		sync_pricing_rules(doc)
		_delete_item_prices_for_items(doc, tiers_by_item.keys())
	for row in flat_rows:
		_disable_stale_rules(doc, row.get("item_code"), tiers=[])
	if tiers_by_item or flat_count:
		doc.db_set("custom_tier_sync_status", "Synced", update_modified=False)
	return len(tiers_by_item) + flat_count


def _sync_flat_item_prices(doc, flat_rows):
	"""Upsert supplier Item Prices for rows whose item has no quantity tiers.

	Flat quote rows become one buying, supplier-specific Item Price each, so
	native price picking and the comparison engines share the same price. The
	`reference` field carries the document name as the ownership marker (used
	by cancel cleanup and by the tier-conversion cleanup below).
	"""
	price_list = _get_buying_price_list(doc)
	if not price_list:
		return 0
	valid_from = doc.get("quote_date") or doc.get("transaction_date")
	synced = 0
	for row in flat_rows:
		_upsert_item_price(doc, row, price_list, valid_from)
		synced += 1
	if synced:
		frappe.clear_cache(doctype="Item Price")
	return synced


def _flat_price_rows(doc):
	"""Rows whose item is quoted at a single quantity point (tier items are skipped)."""
	rows_by_item = {}
	for row in doc.get("items") or []:
		item_code = (row.get("item_code") or "").strip()
		if not row.get("valid", 1) or not item_code or not flt(row.get("rate")):
			continue
		rows_by_item.setdefault(item_code, []).append(row)

	flat = []
	for rows in rows_by_item.values():
		if len({flt(row.get("qty")) for row in rows}) != 1:
			continue
		flat.append(rows[-1])
	return flat


def _get_buying_price_list(doc):
	price_list = doc.get("buying_price_list")
	if price_list:
		return price_list
	price_list = frappe.db.get_single_value("Buying Settings", "default_buying_price_list")
	if price_list:
		return price_list
	return frappe.db.get_value("Price List", {"buying": 1, "enabled": 1}, "name")


def _upsert_item_price(doc, row, price_list, valid_from):
	item_code = row.get("item_code")
	uom = row.get("uom") or frappe.db.get_value("Item", item_code, "stock_uom")
	values = {
		"price_list_rate": flt(row.get("rate")),
		# Keep the supplier's quoted delivery lead time together with the
		# price.  ERPNext's buying price picker reads this field from Item
		# Price when building purchase recommendations and purchase orders.
		"lead_time_days": flt(row.get("lead_time_days")),
		"currency": doc.currency,
		"valid_from": getdate(valid_from) if valid_from else None,
		"valid_upto": getdate(doc.valid_till) if doc.get("valid_till") else None,
		"reference": doc.name,
	}
	existing = frappe.get_all(
		"Item Price",
		filters={
			"item_code": item_code,
			"price_list": price_list,
			"supplier": doc.supplier,
			"uom": uom,
		},
		fields=["name", "reference"],
		order_by="creation desc, name desc",
		limit=1,
	)
	if existing:
		reference = (existing[0].reference or "").strip()
		# ERPNext may populate ``reference`` with the supplier name when an
		# Item Price is created from a quotation.  Treat that value as an
		# application-owned price as well; otherwise a later, cheaper submitted
		# quotation would be incorrectly ignored as a user-maintained price.
		owned_reference = (
			not reference
			or reference == (doc.supplier or "").strip()
			or frappe.db.exists("Supplier Quotation", reference)
		)
		if not owned_reference:
			# Explicitly user-maintained price (reference is not one of our
			# quotation names): never overwrite, never create a duplicate.
			return None
		# Blank reference means unowned (adopted by the latest quote by design);
		# a quotation name means it is already ours.
		frappe.db.set_value("Item Price", existing[0].name, values, update_modified=False)
		return existing[0].name
	return frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"uom": uom,
			"price_list": price_list,
			"buying": 1,
			"supplier": doc.supplier,
			**values,
		}
	).insert(ignore_permissions=True).name


def _delete_item_prices_for_items(doc, item_codes):
	"""Delete auto-generated supplier Item Prices for the given items.

	Ownership is decided by the `reference` field: our sync only ever writes a
	Supplier Quotation name there, so a price whose reference is an existing
	quotation is ours; user-maintained prices (blank or anything else) stay.
	"""
	for item_code in item_codes:
		prices = frappe.get_all(
			"Item Price",
			filters={
				# ERPNext 原生由供应商报价生成的普通 Item Price 可能不带
				# supplier；同时兼容已经带当前供应商的记录。
				"supplier": ("in", ["", doc.supplier]),
				"buying": 1,
				"item_code": item_code,
			},
			fields=["name", "reference"],
		)
		for price in prices:
			reference = (price.reference or "").strip()
			# ERPNext 原生提交供应商报价时可能创建一条无 reference
			# 或以供应商名称为 reference 的 Item Price。阶梯报价的唯一
			# 价格来源是 Pricing Rule，因此这些原生平价记录必须清理；
			# 其他明确由用户维护的 reference 保留。
			if (
				not reference
				or reference == (doc.supplier or "").strip()
				or frappe.db.exists("Supplier Quotation", reference)
			):
				frappe.delete_doc("Item Price", price.name, ignore_permissions=True)
	frappe.clear_cache(doctype="Item Price")


def _delete_item_prices_for_doc(doc):
	"""Delete supplier Item Prices marked with this document's name."""
	for name in frappe.get_all(
		"Item Price",
		filters={"supplier": doc.supplier, "buying": 1, "reference": doc.name},
		pluck="name",
	):
		frappe.delete_doc("Item Price", name, ignore_permissions=True)
	frappe.clear_cache(doctype="Item Price")


def sync_quotation_tiers_on_submit(doc, method=None):
	"""doc_events hook: sync a Supplier Quotation's tier rows into Pricing Rules on submit.

	Sync failures never block the quotation's submission; they are logged, the
	sync status is stamped as failed, and a non-blocking alert is shown instead.
	"""
	try:
		sync_quotation_tiers(doc)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Supplier quotation tier price sync failed")
		doc.db_set("custom_tier_sync_status", "Sync Failed", update_modified=False)
		frappe.msgprint(
			_("Tier price sync failed; the quotation was submitted. Use the Sync Tier Prices button to retry."),
			indicator="orange",
			alert=True,
		)


def disable_quotation_tiers_on_cancel(doc, method=None):
	"""doc_events hook: remove this quotation's prices and roll back to the previous one."""
	disable_pricing_rules_for_doc(doc)
	_delete_item_prices_for_doc(doc)
	doc.db_set("custom_tier_sync_status", "", update_modified=False)
	_rollback_to_previous_quotation(doc)


def _rollback_to_previous_quotation(doc):
	"""Re-sync prices from the supplier's latest other submitted quotation, if any.

	Rollback failures never block the cancellation; they are logged and
	surfaced as a non-blocking alert instead.
	"""
	try:
		filters = {
			"supplier": doc.supplier,
			"docstatus": 1,
			"name": ("!=", doc.name),
		}
		# Never restore a price from another accounting context. Supplier
		# quotations can share a supplier while belonging to different
		# companies, currencies, or buying price lists.
		for fieldname in ("company", "currency", "buying_price_list"):
			value = doc.get(fieldname)
			if value:
				filters[fieldname] = value
		previous = frappe.get_all(
			"Supplier Quotation",
			filters=filters,
			pluck="name",
			order_by="transaction_date desc, creation desc",
			limit=1,
		)
		if not previous:
			return
		sync_quotation_tiers(frappe.get_doc("Supplier Quotation", previous[0]))
		frappe.msgprint(_("Prices rolled back to quotation {0}.").format(previous[0]), alert=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Supplier quotation price rollback failed")
		frappe.msgprint(
			_("Rollback to the previous quotation failed; only the cancelled quotation's prices were removed."),
			indicator="orange",
			alert=True,
		)


def disable_pricing_rules_for_doc(doc):
	"""Disable active auto-generated tier rules whose marker ends with this document's name."""
	rules = frappe.get_all(
		"Pricing Rule",
		filters={"buying": 1, "disable": 0, "supplier": doc.supplier},
		fields=["name", "rule_description"],
	)
	for rule in rules:
		description = rule.rule_description or ""
		if not _is_auto_marker(description) or not description.endswith(doc.name):
			continue
		frappe.db.set_value("Pricing Rule", rule.name, "disable", 1, update_modified=False)
	frappe.clear_cache(doctype="Pricing Rule")


@frappe.whitelist()
def sync_quotation_pricing_rules(sq_name):
	"""Manually (re)sync a Supplier Quotation's prices (tier rules + item prices). Idempotent."""
	doc = frappe.get_doc("Supplier Quotation", sq_name)
	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("Tier prices can only be synced for submitted quotations."))
	for doctype in ("Pricing Rule", "Item Price"):
		if not frappe.has_permission(doctype, "write"):
			frappe.throw(
				_("You do not have permission to write {0}.").format(doctype), frappe.PermissionError
			)
	synced = sync_quotation_tiers(doc)
	if not synced:
		frappe.throw(_("No price rows were found to sync in this quotation."))
	return synced
