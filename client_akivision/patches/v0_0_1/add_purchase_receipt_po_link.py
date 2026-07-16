import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Purchase Receipt": [
                {
                    "fieldname": "custom_purchase_order",
                    "label": "采购订单号",
                    "fieldtype": "Link",
                    "options": "Purchase Order",
                    "insert_after": "supplier_name",
                    "read_only": 1,
                    "in_list_view": 0,
                    "translatable": 0,
                    "description": "该采购收货单关联的采购订单（取自明细行第一条采购订单）",
                }
            ]
        }
    )
