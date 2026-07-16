import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_columns():
    return [
        {
            "label": _("Project No"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Project",
            "width": 140,
        },
        {
            "label": _("Project Name"),
            "fieldname": "project_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Technical Domain"),
            "fieldname": "custom_technical_domain",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": _("Expected Start Date"),
            "fieldname": "expected_start_date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "label": _("Expected End Date"),
            "fieldname": "expected_end_date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "label": _("Project Leader"),
            "fieldname": "custom_project_leader",
            "fieldtype": "Link",
            "options": "User",
            "width": 140,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Project Type"),
            "fieldname": "project_type",
            "fieldtype": "Link",
            "options": "Project Type",
            "width": 130,
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 140,
        },
        {
            "label": _("Percent Complete"),
            "fieldname": "percent_complete",
            "fieldtype": "Percent",
            "width": 140,
        },
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    rows = frappe.db.sql(
        f"""
        SELECT
            p.name,
            p.project_name,
            p.custom_technical_domain,
            p.expected_start_date,
            p.expected_end_date,
            p.custom_project_leader,
            p.status,
            p.project_type,
            p.company,
            p.percent_complete
        FROM `tabProject` p
        WHERE 1=1 {conditions}
        ORDER BY p.expected_start_date DESC, p.name DESC
        """,
        filters,
        as_dict=True,
    )

    for row in rows:
        row.percent_complete = flt(row.percent_complete)

    return rows


def get_report_summary(data):
    total = len(data)
    open_count = sum(1 for row in data if row.status == "Open")
    completed_count = sum(1 for row in data if row.status == "Completed")
    cancelled_count = sum(1 for row in data if row.status == "Cancelled")

    return [
        {"value": total, "label": _("Total Projects"), "datatype": "Int", "indicator": "Blue"},
        {"value": open_count, "label": _("Open"), "datatype": "Int", "indicator": "Orange"},
        {"value": completed_count, "label": _("Completed"), "datatype": "Int", "indicator": "Green"},
        {"value": cancelled_count, "label": _("Cancelled"), "datatype": "Int", "indicator": "Red"},
    ]


def get_conditions(filters):
    conditions = []
    if filters.get("company"):
        conditions.append("AND p.company = %(company)s")
    if filters.get("status"):
        conditions.append("AND p.status = %(status)s")
    if filters.get("project_type"):
        conditions.append("AND p.project_type = %(project_type)s")
    if filters.get("technical_domain"):
        conditions.append("AND p.custom_technical_domain LIKE %(technical_domain)s")
        filters.technical_domain = f"%{filters.technical_domain}%"
    if filters.get("project_leader"):
        conditions.append("AND p.custom_project_leader = %(project_leader)s")
    if filters.get("from_date"):
        conditions.append("AND p.expected_start_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("AND p.expected_start_date <= %(to_date)s")
    return " ".join(conditions)
