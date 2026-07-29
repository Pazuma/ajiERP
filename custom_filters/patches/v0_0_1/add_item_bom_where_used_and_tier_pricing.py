import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    # 注意：不使用 Section Break 自定义字段——Frappe 的 meta 排序会把
    # Section Break 类自定义字段“顺延到下一个 Section Break 之前”，
    # 导致其越过 Tab Break 落到下一个页签。HTML 字段无此行为，
    # 可精确落在锚点字段之后（页签内末尾）。
    create_custom_fields(
        {
            "Item": [
                # Manufacturing 页签末尾（页签最后字段为 customer_code，其后是 quality_tab）
                {
                    "fieldname": "custom_cf_bom_where_used_html",
                    "label": "关联成品",
                    "fieldtype": "HTML",
                    "insert_after": "customer_code",
                    "translatable": 0,
                },
                # Pricing 页签末尾（pricing_tab → item_prices_column → prices_html）
                {
                    "fieldname": "custom_cf_tier_pricing_html",
                    "label": "阶梯价格表",
                    "fieldtype": "HTML",
                    "insert_after": "prices_html",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Item")
