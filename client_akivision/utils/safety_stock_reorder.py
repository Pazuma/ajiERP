import frappe
from frappe.utils import flt

import erpnext.stock.reorder_item as reorder_module


_original_create_material_request = reorder_module.create_material_request
_original_get_items_for_reorder = reorder_module.get_items_for_reorder


def get_items_for_reorder_with_safety_stock():
    """Use Item safety stock as the reorder threshold for configured warehouses."""
    items = _original_get_items_for_reorder()
    safety_items = frappe.get_all(
        "Item",
        filters={"disabled": 0, "is_stock_item": 1, "safety_stock": [">", 0]},
        fields=[
            "name",
            "safety_stock",
            "min_order_qty",
            "item_name",
            "item_group",
            "brand",
            "description",
            "stock_uom",
            "purchase_uom",
            "lead_time_days",
        ],
    )

    for item in safety_items:
        threshold = flt(item.safety_stock)
        reorder_rows = items.get(item.name, [])
        for row in reorder_rows:
            row.warehouse_reorder_level = max(flt(row.warehouse_reorder_level), threshold)

        # A safety stock without a warehouse is not actionable. Use the item
        # default warehouse so the setting can work without duplicating the
        # threshold in Item Reorder.
        if reorder_rows:
            continue
        configured_warehouses = {row.warehouse for row in reorder_rows}
        defaults = frappe.get_all(
            "Item Default",
            filters={"parent": item.name, "default_warehouse": ["is", "set"]},
            fields=["default_warehouse"],
        )
        for default in defaults:
            if default.default_warehouse in configured_warehouses:
                continue
            configured_warehouses.add(default.default_warehouse)
            items.setdefault(item.name, []).append(
                frappe._dict(
                    {
                        "warehouse": default.default_warehouse,
                        "warehouse_group": None,
                        "material_request_type": "Purchase",
                        "warehouse_reorder_level": threshold,
                        "warehouse_reorder_qty": max(flt(item.min_order_qty), threshold),
                        "name": item.name,
                        "stock_uom": item.stock_uom,
                        "purchase_uom": item.purchase_uom,
                        "description": item.description,
                        "item_name": item.item_name,
                        "item_group": item.item_group,
                        "brand": item.brand,
                        "variant_of": None,
                        "has_variants": 0,
                        "lead_time_days": item.lead_time_days,
                    }
                )
            )

    return items


def create_material_request_with_max_cap(material_requests):
    """Wrap native MR creation and cap reorder quantities by max stock limit."""
    if not material_requests:
        return _original_create_material_request(material_requests)

    # Build lookup: {(item_code, warehouse): max_limit}
    item_warehouse_pairs = set()
    for request_type in material_requests:
        for company in material_requests[request_type]:
            for item in material_requests[request_type][company]:
                item_warehouse_pairs.add((item["item_code"], item["warehouse"]))

    max_limit_map = _get_max_stock_limits(item_warehouse_pairs)
    existing_requests = _get_open_reorder_requests(item_warehouse_pairs)

    for request_type in material_requests:
        for company in list(material_requests[request_type].keys()):
            filtered_items = []
            for item in material_requests[request_type][company]:
                pair = (item["item_code"], item["warehouse"])
                if pair in existing_requests:
                    continue
                max_limit = max_limit_map.get((item["item_code"], item["warehouse"]))
                if not max_limit:
                    filtered_items.append(item)
                    continue

                projected = flt(item.get("projected_on_hand", 0))
                reorder_qty = flt(item.get("reorder_qty", 0))
                max_allowed = max_limit - projected
                if max_allowed <= 0:
                    continue
                if reorder_qty > max_allowed:
                    item["reorder_qty"] = max_allowed
                filtered_items.append(item)

            if filtered_items:
                material_requests[request_type][company] = filtered_items
            else:
                del material_requests[request_type][company]

    return _original_create_material_request(material_requests)


def _get_open_reorder_requests(item_warehouse_pairs):
    """Avoid duplicate submitted reorder requests for the same item and warehouse."""
    if not item_warehouse_pairs:
        return set()

    rows = frappe.db.sql(
        """
        SELECT mri.item_code, mri.warehouse
        FROM `tabMaterial Request Item` mri
        INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
        WHERE mr.docstatus = 1
          AND mr.auto_created_via_reorder = 1
          AND mr.material_request_type = 'Purchase'
          AND COALESCE(mr.status, '') NOT IN ('Stopped', 'Cancelled', 'Completed')
          AND mri.item_code IN %(item_codes)s
          AND mri.warehouse IN %(warehouses)s
        """,
        {
            "item_codes": tuple({item_code for item_code, _ in item_warehouse_pairs}),
            "warehouses": tuple({warehouse for _, warehouse in item_warehouse_pairs}),
        },
        as_dict=True,
    )
    return {(row.item_code, row.warehouse) for row in rows}


def _get_max_stock_limits(item_warehouse_pairs):
    """Return {(item_code, warehouse): max_limit} for active Item Reorder rows."""
    if not item_warehouse_pairs:
        return {}

    # Item Reorder child table stores max limit
    item_reorder = frappe.qb.DocType("Item Reorder")
    item_table = frappe.qb.DocType("Item")

    query = (
        frappe.qb.from_(item_reorder)
        .inner_join(item_table)
        .on(item_reorder.parent == item_table.name)
        .select(
            item_reorder.parent.as_("item_code"),
            item_reorder.warehouse,
            item_reorder.custom_max_stock_limit,
        )
        .where(
            (item_table.disabled == 0)
            & (item_reorder.custom_max_stock_limit > 0)
        )
    )

    result = {}
    for row in query.run(as_dict=True):
        result[(row.item_code, row.warehouse)] = flt(row.custom_max_stock_limit)

    return result


def patch_reorder_module():
    """Apply monkey-patch to native reorder module."""
    reorder_module.get_items_for_reorder = get_items_for_reorder_with_safety_stock
    reorder_module.create_material_request = create_material_request_with_max_cap
