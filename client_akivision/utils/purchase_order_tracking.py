"""Purchase-order delivery plans tied to individual purchase-order items."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def ensure_schema():
    create_custom_fields(
        {
            "Purchase Order": [
                {
                    "fieldname": "custom_delivery_plans",
                    "label": "交货计划",
                    "fieldtype": "Table",
                    "options": "Purchase Order Delivery Plan",
                    "insert_after": "items",
                    "description": "按采购订单明细维护供应商承诺的分批交货计划；实际收货以采购收货单为准。",
                }
            ]
        },
        update=True,
    )
    frappe.db.updatedb("Purchase Order")
    frappe.clear_cache(doctype="Purchase Order")


def validate_delivery_plans(doc, method=None):
    """Keep each plan linked to this PO's item and validate plan quantities."""
    items = {row.name: row for row in doc.get("items", []) if row.name}
    totals = {}
    seen_sequences = set()
    for row in doc.get("custom_delivery_plans", []) or []:
        item = items.get(row.get("purchase_order_item"))
        if not item:
            frappe.throw(_("交货计划第 {0} 行必须关联当前采购订单的物料明细。").format(row.idx))
        if row.get("item_code") and row.item_code != item.item_code:
            frappe.throw(_("交货计划第 {0} 行的物料编码与采购订单明细不一致。").format(row.idx))
        row.item_code = item.item_code
        if flt(row.get("sequence")) <= 0:
            frappe.throw(_("交货计划第 {0} 行的批次序号必须大于 0。").format(row.idx))
        sequence_key = (row.purchase_order_item, int(flt(row.sequence)))
        if sequence_key in seen_sequences:
            frappe.throw(_("物料 {0} 的交货计划批次序号 {1} 重复。").format(item.item_code, sequence_key[1]))
        seen_sequences.add(sequence_key)
        if flt(row.get("planned_qty")) <= 0:
            frappe.throw(_("交货计划第 {0} 行的计划数量必须大于 0。").format(row.idx))
        if not row.get("planned_date"):
            frappe.throw(_("交货计划第 {0} 行必须填写计划交货日期。").format(row.idx))
        totals[row.purchase_order_item] = totals.get(row.purchase_order_item, 0) + flt(row.planned_qty)

    for item_name, planned_qty in totals.items():
        item = items[item_name]
        if planned_qty > flt(item.qty) + 0.000001:
            frappe.throw(
                _("物料 {0} 的交货计划数量合计 {1} 超过订单数量 {2}。").format(
                    item.item_code, planned_qty, item.qty
                )
            )
