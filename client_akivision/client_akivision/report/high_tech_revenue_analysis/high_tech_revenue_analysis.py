from frappe import _
from frappe.utils import flt

from client_akivision.client_akivision.api.operations_kpi import get_high_tech_project_rows, normalise_filters


def execute(filters=None):
	data = get_high_tech_project_rows(normalise_filters(filters))
	total = sum(flt(row.high_tech_revenue) for row in data)
	for row in data:
		row.ratio = flt(row.high_tech_revenue) / total if total else 0
	return [
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("Project Name"), "fieldname": "project_name", "fieldtype": "Data", "width": 200},
		{"label": _("High-tech Revenue Amount"), "fieldname": "high_tech_revenue", "fieldtype": "Currency", "width": 160},
		{"label": _("Ratio"), "fieldname": "ratio", "fieldtype": "Percent", "width": 100},
	], data, None, None, [{"label": _("高新收入总额"), "value": total, "datatype": "Currency", "indicator": "Green"}]
