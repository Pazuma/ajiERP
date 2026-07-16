import frappe
from frappe.model.naming import make_autoname
from frappe.model.rename_doc import rename_doc


def execute():
	"""Replace legacy composite KPI Target names with stable, neutral numbers."""
	if not frappe.db.exists("DocType", "KPI Target"):
		return

	for name in frappe.get_all("KPI Target", pluck="name"):
		if name.startswith("KPI-TGT-"):
			continue
		rename_doc(
			"KPI Target",
			name,
			make_autoname("KPI-TGT-.#####"),
			force=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=False,
		)
