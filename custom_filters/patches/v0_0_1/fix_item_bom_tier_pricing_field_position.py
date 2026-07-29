import frappe


def execute():
    """修正 BOM 反查/阶梯价格自定义字段的位置与标签。

    早期版本用 Section Break + HTML 组合，Section Break 被 Frappe meta
    排序顺延到了下一个页签。改为仅 HTML 字段直接锚定在页签末字段之后：
    - 删除两个 Section Break 自定义字段（如存在）
    - 两个 HTML 字段重新锚定并更新标签（如已创建）
    幂等：字段不存在时跳过。
    """
    for fieldname in ("custom_cf_bom_where_used_section", "custom_cf_tier_pricing_section"):
        if frappe.db.exists("Custom Field", f"Item-{fieldname}"):
            frappe.delete_doc("Custom Field", f"Item-{fieldname}", force=1)

    for fieldname, anchor, label in (
        ("custom_cf_bom_where_used_html", "customer_code", "关联成品"),
        ("custom_cf_tier_pricing_html", "prices_html", "阶梯价格表"),
    ):
        if frappe.db.exists("Custom Field", f"Item-{fieldname}"):
            frappe.db.set_value(
                "Custom Field",
                f"Item-{fieldname}",
                {"insert_after": anchor, "label": label},
                update_modified=False,
            )

    frappe.clear_cache(doctype="Item")
