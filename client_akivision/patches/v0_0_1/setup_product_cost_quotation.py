"""Only new costing schema and roles; no source business records are modified."""
import frappe


def execute():
    from client_akivision.patches.v0_0_1.ensure_product_cost_roles import execute as ensure_roles
    ensure_roles()
    for slug in ("product_cost_material", "product_cost_operation", "product_cost_investment", "product_cost_scenario", "product_cost_quotation"):
        frappe.reload_doc("client_akivision", "doctype", slug)
    from client_akivision.utils.product_cost_export import build_template
    build_template()
    frappe.clear_cache()
