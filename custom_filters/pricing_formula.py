import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today


RULE_TYPES = {"Fixed Rate", "Quantity Range", "Step Discount", "Progressive Discount", "Tier Table"}


def _decimal(value, label, *, allow_zero=True):
	try:
		value = Decimal(str(value if value not in (None, "") else 0))
	except (InvalidOperation, ValueError):
		raise ValueError(_("{0} must be a number.").format(label))
	if value < 0 or (not allow_zero and value == 0):
		raise ValueError(_("{0} must be greater than {1}.").format(label, "or equal to zero" if allow_zero else "zero"))
	return value


def normalize_rule(payload):
	payload = frappe.parse_json(payload) if isinstance(payload, str) else (payload or {})
	rule_type = payload.get("rule_type")
	if rule_type not in RULE_TYPES:
		raise ValueError(_("Please select a supported pricing rule type."))
	params = frappe.parse_json(payload.get("parameters") or {})
	normalized = {}
	if rule_type == "Fixed Rate":
		normalized["rate"] = str(_decimal(params.get("rate"), _("Rate"), allow_zero=False))
	elif rule_type in ("Quantity Range", "Tier Table"):
		tiers = []
		for index, row in enumerate(params.get("tiers") or [], 1):
			minimum = _decimal(row.get("min_qty"), _("Tier {0} minimum quantity").format(index))
			maximum = _decimal(row.get("max_qty"), _("Tier {0} maximum quantity").format(index))
			rate = _decimal(row.get("rate"), _("Tier {0} rate").format(index), allow_zero=False)
			if maximum and maximum < minimum:
				raise ValueError(_("Tier {0} maximum quantity cannot be below its minimum.").format(index))
			tiers.append({"min_qty": str(minimum), "max_qty": str(maximum), "rate": str(rate)})
		if not tiers:
			raise ValueError(_("Please add at least one pricing tier."))
		tiers.sort(key=lambda row: Decimal(row["min_qty"]))
		for previous, current in zip(tiers, tiers[1:], strict=False):
			previous_max = Decimal(previous["max_qty"])
			if not previous_max or previous_max >= Decimal(current["min_qty"]):
				raise ValueError(_("Pricing tiers cannot overlap and only the last tier may have no maximum."))
		normalized["tiers"] = tiers
	else:
		base_rate = _decimal(params.get("base_rate"), _("Base Rate"), allow_zero=False)
		start_qty = _decimal(params.get("start_qty"), _("Start Quantity"))
		step_qty = _decimal(params.get("step_qty"), _("Step Quantity"), allow_zero=False)
		discount = _decimal(params.get("discount_percent"), _("Discount Percent"), allow_zero=False)
		minimum_rate = _decimal(params.get("minimum_rate"), _("Minimum Rate"))
		if discount > 100:
			raise ValueError(_("Discount Percent cannot exceed 100."))
		if minimum_rate > base_rate:
			raise ValueError(_("Minimum Rate cannot exceed Base Rate."))
		normalized = {"base_rate": str(base_rate), "start_qty": str(start_qty), "step_qty": str(step_qty), "discount_percent": str(discount), "minimum_rate": str(minimum_rate)}
	return {"rule_type": rule_type, "parameters": normalized}


def render_formula(rule):
	p = rule["parameters"]
	if rule["rule_type"] == "Fixed Rate":
		return _("固定单价 = {0}").format(p["rate"])
	if rule["rule_type"] in ("Quantity Range", "Tier Table"):
		parts = []
		for index, tier in enumerate(p["tiers"]):
			maximum = Decimal(tier["max_qty"])
			if maximum:
				suffix = f" 至 {tier['max_qty']}"
				if index == len(p["tiers"]) - 1:
					suffix += _("，超过此数量仍按此档")
			else:
				suffix = " 及以上"
			parts.append(_("数量 {0}{1}，单价 {2}").format(tier["min_qty"], suffix, tier["rate"]))
		return "; ".join(parts)
	if rule["rule_type"] == "Step Discount":
		return _("从数量 {0} 起，每增加 {1}，在基准单价上再降低 {2}%，最低不低于最低单价").format(p["start_qty"], p["step_qty"], p["discount_percent"])
	return _("从数量 {0} 起，每增加 {1}，按上一档单价继续降低 {2}%，最低不低于最低单价").format(p["start_qty"], p["step_qty"], p["discount_percent"])


def evaluate_rule(payload, qty, precision=6):
	rule = normalize_rule(payload)
	quantity = _decimal(qty, _("Quantity"), allow_zero=False)
	p = rule["parameters"]
	matched = ""
	if rule["rule_type"] == "Fixed Rate":
		rate = Decimal(p["rate"])
		matched = _("固定单价")
	elif rule["rule_type"] in ("Quantity Range", "Tier Table"):
		rate = None
		for tier_index, tier in enumerate(p["tiers"]):
			minimum, maximum = Decimal(tier["min_qty"]), Decimal(tier["max_qty"])
			if quantity >= minimum and (not maximum or quantity <= maximum):
				rate = Decimal(tier["rate"])
				matched = f"{minimum:g}+" if not maximum else f"{minimum:g}-{maximum:g}"
				break
			# Once quantity exceeds the final configured tier, keep using the
			# final tier's price. This supports open-ended purchasing without
			# requiring a placeholder upper bound in the dialog.
			if tier_index == len(p["tiers"]) - 1 and maximum and quantity > maximum:
				rate = Decimal(tier["rate"])
				matched = _("{0} 以上（按最后一档）").format(minimum)
				break
		if rate is None:
			raise ValueError(_("Quantity does not match any pricing tier."))
	else:
		base = Decimal(p["base_rate"])
		start = Decimal(p["start_qty"])
		step = Decimal(p["step_qty"])
		discount = Decimal(p["discount_percent"]) / Decimal("100")
		minimum = Decimal(p["minimum_rate"])
		steps = 0 if quantity < start else int((quantity - start) // step) + 1
		if rule["rule_type"] == "Step Discount":
			rate = base * (Decimal("1") - discount * steps)
		else:
			rate = base * ((Decimal("1") - discount) ** steps)
		rate = max(rate, minimum)
		matched = _("命中 {0} 个降价阶梯").format(steps)
	quantum = Decimal("1").scaleb(-precision)
	rate = rate.quantize(quantum, rounding=ROUND_HALF_UP)
	return {"rate": float(rate), "total": float((rate * quantity).quantize(quantum, rounding=ROUND_HALF_UP)), "matched_tier": matched, "formula": render_formula(rule), "rule": rule}


@frappe.whitelist()
def preview_pricing_formula(rule_type, parameters, test_qty):
	try:
		return evaluate_rule({"rule_type": rule_type, "parameters": parameters}, test_qty)
	except ValueError as exc:
		frappe.throw(str(exc))


def get_active_rule(item_code, supplier, company=None, pricing_date=None):
	pricing_date = getdate(pricing_date or today())
	filters = {"item_code": item_code, "supplier": supplier, "disabled": 0, "valid_from": ("<=", pricing_date)}
	if company:
		filters["company"] = ("in", ["", company])
	rows = frappe.get_all("Item Supplier Pricing Rule", filters=filters, fields=["name", "valid_upto"], order_by="valid_from desc, creation desc")
	for row in rows:
		if not row.valid_upto or getdate(row.valid_upto) >= pricing_date:
			return frappe.get_doc("Item Supplier Pricing Rule", row.name)
	return None


def evaluate_supplier_rule(doc, qty):
	calculation_qty = max(Decimal(str(qty)), Decimal(str(doc.minimum_order_qty or 0)))
	result = evaluate_rule(doc.as_formula_payload(), calculation_qty)
	result.update({"pricing_rule": doc.name, "supplier_quotation": doc.source_supplier_quotation, "source_currency": doc.currency, "calculation_qty": float(calculation_qty), "rule_type": doc.rule_type, "calculated_at": now_datetime()})
	return result
