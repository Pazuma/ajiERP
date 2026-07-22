"""Sync quantity-tier Pricing Rules from a Supplier Quote Import.

When an import quotes the same item at multiple quantities (price breaks), each
break becomes one buying Pricing Rule so ERPNext native picking and the Purchase
Recommendation report share the same tiered prices.
"""

import frappe
from frappe.utils import flt, getdate

TIER_RULE_MARKER = "由供应商报价导入"


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
		tiers = []
		for index, qty in enumerate(sorted_qtys):
			next_qty = sorted_qtys[index + 1] if index + 1 < len(sorted_qtys) else None
			tiers.append(
				{
					"min_qty": qty,
					"max_qty": (next_qty - 1) if next_qty is not None else 0,
					"rate": qty_rates[qty],
				}
			)
		tiers_by_item[item_code] = tiers
	return tiers_by_item


def _upsert_tier_rule(doc, item_code, tier):
	values = {
		"max_qty": tier["max_qty"],
		"rate": tier["rate"],
		"rate_or_discount": "Rate",
		"currency": doc.currency,
		"company": doc.company,
		"valid_from": getdate(doc.quote_date) if doc.get("quote_date") else None,
		"valid_upto": getdate(doc.valid_till) if doc.get("valid_till") else None,
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


def _find_tier_rule(supplier, item_code, min_qty):
	rules = frappe.get_all(
		"Pricing Rule",
		filters={"buying": 1, "disable": 0, "supplier": supplier, "min_qty": min_qty},
		fields=["name", "rule_description"],
	)
	for rule in rules:
		if not (rule.rule_description or "").startswith(TIER_RULE_MARKER):
			continue  # User-created rule; never overwrite it.
		if frappe.db.exists("Pricing Rule Item Code", {"parent": rule.name, "item_code": item_code}):
			return rule.name
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
		if not (rule.rule_description or "").startswith(TIER_RULE_MARKER):
			continue
		if not frappe.db.exists("Pricing Rule Item Code", {"parent": rule.name, "item_code": item_code}):
			continue
		frappe.db.set_value("Pricing Rule", rule.name, "disable", 1, update_modified=False)
