import frappe
from frappe import _


STOCK_ENTRY_TYPE_PURPOSES = {
	"组装领料": "Material Transfer for Manufacture",
	"组装退料": "Material Receipt",
	"生产补料": "Material Transfer for Manufacture",
	"生产制造": "Manufacture",
	"外发领料": "Send to Subcontractor",
	"产线借用": "Material Issue",
	"其它领用": "Material Issue",
	"Sample Loan In": "Material Receipt",
	"Sample Loan In Return": "Material Issue",
	"Sample Loan Out": "Material Transfer",
	"Sample Loan Out Return": "Material Transfer",
}


# The form exposes business language while Stock Entry keeps ERPNext's type and
# purpose model. These values are deliberately limited to the manual-stock
# workflows; sample-loan transactions continue to be created from their own
# documents because they carry additional traceability data.
STOCK_ENTRY_REASON_MAP = {
	"生产领料": {"direction": "出库", "stock_entry_type": "组装领料"},
	"生产补料": {"direction": "出库", "stock_entry_type": "生产补料"},
	"外发领料": {"direction": "出库", "stock_entry_type": "外发领料"},
	"产线借用": {"direction": "出库", "stock_entry_type": "产线借用"},
	"其它领用": {"direction": "出库", "stock_entry_type": "其它领用"},
	"生产退料": {"direction": "入库", "stock_entry_type": "组装退料"},
	"生产入库": {"direction": "入库", "stock_entry_type": "生产制造"},
}

PURCHASE_RECEIPT_REASON = "采购入库"
WORK_ORDER_REASONS = {"生产领料", "生产补料", "生产退料", "生产入库"}


def apply_stock_entry_reason(doc, _method=None):
	"""Validate the business selector and set the compatible Stock Entry Type.

	Legacy imports and integrations omit these fields, so they continue to use
	their existing ``stock_entry_type`` values unchanged.
	"""
	direction = doc.get("custom_stock_direction")
	reason = doc.get("custom_stock_reason")
	if not direction and not reason:
		return
	if not direction or not reason:
		frappe.throw(_("请同时选择出/入库方向和出入库原因"))
	if reason == PURCHASE_RECEIPT_REASON:
		frappe.throw(_("采购入库请使用采购收货单，不能保存为物料出/入库单"))

	mapping = STOCK_ENTRY_REASON_MAP.get(reason)
	if not mapping:
		frappe.throw(_("不支持的出入库原因：{0}").format(reason))
	if direction != mapping["direction"]:
		frappe.throw(_("出/入库方向与出入库原因不匹配"))
	if not frappe.db.exists("Stock Entry Type", mapping["stock_entry_type"]):
		frappe.throw(_("库存类型 {0} 不存在").format(mapping["stock_entry_type"]))
	if reason in WORK_ORDER_REASONS and not doc.get("work_order"):
		frappe.throw(_("{0}必须关联生产工单").format(reason))

	doc.stock_entry_type = mapping["stock_entry_type"]


def sync_stock_entry_types():
	"""Create missing Akivision Stock Entry Types and enforce their purposes."""
	for entry_type, purpose in STOCK_ENTRY_TYPE_PURPOSES.items():
		if frappe.db.exists("Stock Entry Type", entry_type):
			frappe.db.set_value("Stock Entry Type", entry_type, "purpose", purpose)
			continue

		frappe.get_doc(
			{
				"doctype": "Stock Entry Type",
				"name": entry_type,
				"purpose": purpose,
			}
		).insert(ignore_permissions=True)

	validate_stock_entry_types()
	frappe.clear_cache(doctype="Stock Entry Type")


def validate_stock_entry_types():
	invalid = []
	for entry_type, purpose in STOCK_ENTRY_TYPE_PURPOSES.items():
		actual_purpose = frappe.db.get_value("Stock Entry Type", entry_type, "purpose")
		if actual_purpose != purpose:
			invalid.append(f"{entry_type}: expected {purpose}, got {actual_purpose or 'missing'}")

	if invalid:
		frappe.throw("Invalid client_akivision Stock Entry Types:\n" + "\n".join(invalid))
