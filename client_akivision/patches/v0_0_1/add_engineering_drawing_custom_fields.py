import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Item": [
                {"fieldname": "custom_engineering_drawing", "label": "当前有效图纸", "fieldtype": "Link", "options": "Engineering Drawing", "insert_after": "image", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_no", "label": "当前图纸号", "fieldtype": "Data", "insert_after": "custom_engineering_drawing", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_revision", "label": "图纸版本", "fieldtype": "Data", "insert_after": "custom_engineering_drawing_no", "read_only": 1},
            ],
            "BOM": [
                {"fieldname": "custom_engineering_drawing", "label": "定稿图纸", "fieldtype": "Link", "options": "Engineering Drawing", "insert_after": "item"},
                {"fieldname": "custom_engineering_drawing_no", "label": "图纸号", "fieldtype": "Data", "insert_after": "custom_engineering_drawing", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_revision", "label": "图纸版本", "fieldtype": "Data", "insert_after": "custom_engineering_drawing_no", "read_only": 1},
            ],
            "BOM Item": [
                {"fieldname": "custom_engineering_drawing", "label": "组件定稿图纸", "fieldtype": "Link", "options": "Engineering Drawing", "insert_after": "item_code", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_no", "label": "组件图纸号", "fieldtype": "Data", "insert_after": "custom_engineering_drawing", "read_only": 1, "in_list_view": 1},
                {"fieldname": "custom_engineering_drawing_revision", "label": "组件图纸版本", "fieldtype": "Data", "insert_after": "custom_engineering_drawing_no", "read_only": 1, "in_list_view": 1},
            ],
            "Material Request": [
                {"fieldname": "custom_engineering_drawing", "label": "图纸", "fieldtype": "Link", "options": "Engineering Drawing", "insert_after": "company", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_no", "label": "图纸号", "fieldtype": "Data", "insert_after": "custom_engineering_drawing", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_revision", "label": "图纸版本", "fieldtype": "Data", "insert_after": "custom_engineering_drawing_no", "read_only": 1},
            ],
            "Work Order": [
                {"fieldname": "custom_engineering_drawing", "label": "图纸", "fieldtype": "Link", "options": "Engineering Drawing", "insert_after": "bom_no", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_no", "label": "图纸号", "fieldtype": "Data", "insert_after": "custom_engineering_drawing", "read_only": 1},
                {"fieldname": "custom_engineering_drawing_revision", "label": "图纸版本", "fieldtype": "Data", "insert_after": "custom_engineering_drawing_no", "read_only": 1},
            ],
        },
        update=True,
    )
