import frappe
from frappe import _


@frappe.whitelist()
def get_item_bom_where_used(item_code):
    validate_item_read_permission(item_code)

    if not frappe.has_permission("BOM", "read"):
        return {"no_permission": True, "rows": []}

    return {"no_permission": False, "rows": get_bom_where_used_rows(item_code)}


@frappe.whitelist()
def get_item_tier_pricing(item_code):
    validate_item_read_permission(item_code)

    if not frappe.has_permission("Pricing Rule", "read"):
        return {"no_permission": True, "rows": []}

    return {"no_permission": False, "rows": get_tier_pricing_rows(item_code)}


def validate_item_read_permission(item_code):
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("未找到物料 {0}").format(item_code or ""))

    if not frappe.has_permission("Item", "read", doc=item_code):
        frappe.throw(_("缺少 Item 读取权限"), frappe.PermissionError)


def get_bom_where_used_rows(item_code):
    return frappe.db.sql(
        """
        select
            bi.parent as bom_no,
            bi.idx as row_idx,
            bi.qty as component_qty,
            bi.uom as component_uom,
            b.item as finished_item,
            b.item_name as finished_item_name,
            b.quantity as bom_qty,
            b.uom as bom_uom,
            b.is_active as is_active,
            b.is_default as is_default,
            b.company as company
        from `tabBOM Item` bi
        inner join `tabBOM` b on b.name = bi.parent
        where
            bi.item_code = %s
            and bi.parenttype = 'BOM'
            and bi.docstatus = 1
            and b.docstatus = 1
        order by b.is_default desc, b.is_active desc, bi.parent asc, bi.idx asc
        limit 200
        """,
        (item_code,),
        as_dict=True,
    )


def get_tier_pricing_rows(item_code):
    return frappe.db.sql(
        """
        select
            pr.name as pricing_rule,
            pric.uom as uom,
            pr.for_price_list as price_list,
            pr.currency as currency,
            pr.min_qty as min_qty,
            pr.max_qty as max_qty,
            pr.rate_or_discount as rate_or_discount,
            pr.rate as rate,
            pr.discount_percentage as discount_percentage,
            pr.discount_amount as discount_amount,
            pr.valid_from as valid_from,
            pr.valid_upto as valid_upto,
            pr.priority as priority,
            pr.disable as disable,
            pr.selling as selling,
            pr.buying as buying,
            pr.applicable_for as applicable_for,
            pr.customer as customer,
            pr.supplier as supplier
        from `tabPricing Rule Item Code` pric
        inner join `tabPricing Rule` pr on pr.name = pric.parent
        where
            pric.item_code = %s
            and pric.parenttype = 'Pricing Rule'
        order by pr.disable asc, pr.valid_from desc, pr.priority desc, pr.name asc, pric.idx asc
        limit 200
        """,
        (item_code,),
        as_dict=True,
    )
