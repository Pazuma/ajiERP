import frappe


def execute():
    """根据 ERP 表格模板中的出库清单，创建常用的物料移动类型（Stock Entry Type）。"""
    movement_types = [
        {"name": "组装领料", "purpose": "Material Issue"},
        {"name": "组装退料", "purpose": "Material Issue"},
        {"name": "生产补料", "purpose": "Material Issue"},
        {"name": "外发领料", "purpose": "Send to Subcontractor"},
        {"name": "产线借用", "purpose": "Material Issue"},
        {"name": "其它领用", "purpose": "Material Issue"},
    ]

    for mt in movement_types:
        if frappe.db.exists("Stock Entry Type", mt["name"]):
            continue
        frappe.get_doc(
            {
                "doctype": "Stock Entry Type",
                "name": mt["name"],
                "purpose": mt["purpose"],
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache()
