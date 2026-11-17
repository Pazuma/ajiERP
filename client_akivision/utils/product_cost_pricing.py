"""Read-only bridge to the existing supplier pricing engine."""
import frappe
from frappe.utils import getdate

from client_akivision.utils.product_cost_permissions import read_source


def make_resolver(doc):
    cache = {}

    def resolve(row, qty):
        if row.get("price_basis") == "Manual":
            if not row.get("manual_reason"):
                raise ValueError("手工价格须填写依据")
            currency = row.get("price_currency")
            if not currency:
                raise ValueError("请填写价格币种")
            if currency == doc.currency and float(row.get("price_exchange_rate") or 0) != 1:
                raise ValueError("同币种价格汇率必须为1")
            return {"rate": row.get("manual_rate"), "basis": "Manual", "reason": row.get("manual_reason"), "currency": currency}
        if not row.get("item_code") or not row.get("pricing_rule") or not row.get("supplier"):
            raise ValueError("请选择供应商和阶梯价格规则")
        from custom_filters.item_supplier_pricing import get_item_supplier_pricing_overview
        from custom_filters.pricing_formula import evaluate_rule
        if row["item_code"] not in cache:
            try:
                cache[row["item_code"]] = get_item_supplier_pricing_overview(row["item_code"])
            except frappe.PermissionError:
                raise ValueError("当前用户没有物料供应商阶梯价读取权限")
        overview = cache[row["item_code"]]
        rule = overview["rules"].get(row["pricing_rule"])
        if overview.get("no_permission") or not rule:
            raise ValueError("无权读取规则或规则未关联该物料供应商")
        read_source("Supplier", row["supplier"])
        date = getdate(doc.quotation_date)
        if rule.get("disabled") or rule["supplier"] != row["supplier"]:
            raise ValueError("价格规则已禁用或供应商不匹配")
        if rule.get("company") and rule["company"] != doc.company:
            raise ValueError("价格规则公司不匹配")
        if (rule.get("valid_from") and getdate(rule["valid_from"]) > date) or (rule.get("valid_upto") and getdate(rule["valid_upto"]) < date):
            raise ValueError("价格规则不在有效期")
        if rule.get("uom") != row.get("purchase_uom"):
            raise ValueError("采购单位与规则单位不一致")
        if rule.get("currency") != row.get("price_currency"):
            raise ValueError("价格币种与规则币种不一致")
        if rule["currency"] == doc.currency and float(row.get("price_exchange_rate") or 0) != 1:
            raise ValueError("同币种价格汇率必须为1")
        if float(qty) < float(rule.get("minimum_order_qty") or 0):
            raise ValueError("本行采购MOQ低于规则MOQ，请刷新来源或修正")
        result = evaluate_rule({"rule_type": rule["rule_type"], "parameters": rule["parameters"]}, qty)
        return {**result, "pricing_rule": rule["name"], "supplier": rule["supplier"],
                "currency": rule["currency"], "valid_from": str(rule.get("valid_from") or ""),
                "valid_upto": str(rule.get("valid_upto") or "")}

    return resolve
