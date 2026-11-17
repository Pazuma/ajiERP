import frappe
from frappe import _
from frappe.model.document import Document

from custom_filters.pricing_formula import normalize_rule, render_formula


class ItemSupplierPricingRule(Document):
	def validate(self):
		if self.rule_type not in ("Quantity Range", "Tier Table"):
			self.set("tiers", [])
		if self.valid_from and self.valid_upto and self.valid_from > self.valid_upto:
			frappe.throw(_("Valid Until cannot be before Valid From."))
		payload = self.as_formula_payload()
		normalized = normalize_rule(payload)
		self.rule_parameters = frappe.as_json(normalized["parameters"])
		self.formula = render_formula(normalized)
		self.summary = self.formula[:140]

	def as_formula_payload(self):
		parameters = frappe.parse_json(self.rule_parameters or "{}")
		if self.rule_type in ("Quantity Range", "Tier Table"):
			parameters["tiers"] = [
				{
					"min_qty": row.min_qty,
					"max_qty": row.max_qty,
					"rate": row.rate,
					"discount_percent": row.discount_percent,
				}
				for row in self.tiers
			]
		return {"rule_type": self.rule_type, "parameters": parameters}

	def on_update(self):
		if not self.disabled:
			_disable_other_versions(self)


def _disable_other_versions(doc):
	filters = {
		"item_code": doc.item_code,
		"supplier": doc.supplier,
		"company": doc.company or "",
		"currency": doc.currency,
		"disabled": 0,
		"name": ("!=", doc.name),
	}
	for name in frappe.get_all("Item Supplier Pricing Rule", filters=filters, pluck="name"):
		frappe.db.set_value("Item Supplier Pricing Rule", name, "disabled", 1, update_modified=False)
