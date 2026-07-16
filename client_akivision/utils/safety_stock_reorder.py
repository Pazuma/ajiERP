import frappe
from frappe.utils import flt

import erpnext.stock.reorder_item as reorder_module


_original_create_material_request = reorder_module.create_material_request


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

    for request_type in material_requests:
        for company in list(material_requests[request_type].keys()):
            filtered_items = []
            for item in material_requests[request_type][company]:
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
    reorder_module.create_material_request = create_material_request_with_max_cap
