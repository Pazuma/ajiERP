import frappe


STOCK_ENTRY_TYPE_PURPOSES = {
	"组装领料": "Material Issue",
	"组装退料": "Material Receipt",
	"生产补料": "Material Issue",
	"外发领料": "Send to Subcontractor",
	"产线借用": "Material Issue",
	"其它领用": "Material Issue",
	"Sample Loan In": "Material Receipt",
	"Sample Loan In Return": "Material Issue",
	"Sample Loan Out": "Material Transfer",
	"Sample Loan Out Return": "Material Transfer",
}


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

