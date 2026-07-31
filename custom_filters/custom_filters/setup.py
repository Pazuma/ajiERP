import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
	"""Create custom fields owned by custom_filters (idempotent)."""
	create_custom_fields(
		{
			"Buying Settings": [
				{
					"fieldname": "custom_supplier_quotation_warehouse",
					"fieldtype": "Link",
					"label": "Default Supplier Quotation Warehouse",
					"options": "Warehouse",
					"insert_after": "supplier_group",
				}
			],
			"Supplier Quotation": [
				{
					"fieldname": "custom_tier_sync_status",
					"fieldtype": "Select",
					"label": "Tier Price Sync Status",
					"options": "\nSynced\nSync Failed",
					"read_only": 1,
					"in_list_view": 1,
					"insert_after": "supplier",
				}
			]
		},
		update=True,
	)
	# 同步状态用于替换列表状态指示器，不单独占用一列；显式回写兼容
	# 已由旧版本创建且 in_list_view=1 的站点。
	if frappe.db.exists("Custom Field", {"dt": "Supplier Quotation", "fieldname": "custom_tier_sync_status"}):
		frappe.db.set_value(
			"Custom Field",
			{"dt": "Supplier Quotation", "fieldname": "custom_tier_sync_status"},
			"in_list_view",
			0,
			update_modified=False,
		)
	frappe.clear_cache(doctype="Supplier Quotation")
	_backfill_unsynced_quotations()


def _backfill_unsynced_quotations():
	"""Idempotently populate sync status for quotations created before migration."""
	if not frappe.db.exists("Custom Field", {"dt": "Supplier Quotation", "fieldname": "custom_tier_sync_status"}):
		return
	from custom_filters import quote_pricing

	# Frappe stores an empty Select as either NULL or an empty string depending
	# on the database/version.  Query both forms so existing quotations are
	# backfilled reliably and the hook remains idempotent.
	for name in frappe.db.sql(
		"""select name from `tabSupplier Quotation`
		where docstatus = 1 and coalesce(custom_tier_sync_status, '') = ''""",
		pluck="name",
	):
		doc = frappe.get_doc("Supplier Quotation", name)
		try:
			quote_pricing.sync_quotation_tiers(doc)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Supplier quotation status backfill failed: {name}")
			frappe.db.set_value("Supplier Quotation", name, "custom_tier_sync_status", "Sync Failed", update_modified=False)
