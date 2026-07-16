import frappe


ENGLISH_STANDING_NAMES = ["Very Poor", "Poor", "Average", "Excellent"]


def execute():
    remove_english_default_standings()
    create_scorecard_variable()
    create_scorecard_criteria()
    create_scorecard_standings()


def remove_english_default_standings():
    """Remove ERPNext's English default standings to avoid overlapping with A/B/C/D级."""
    for name in ENGLISH_STANDING_NAMES:
        if frappe.db.exists("Supplier Scorecard Standing", name):
            frappe.delete_doc("Supplier Scorecard Standing", name, ignore_permissions=True)


def create_scorecard_variable():
    """Create the custom avg_days_late variable if it does not exist."""
    if frappe.db.exists("Supplier Scorecard Variable", "Average Delay Days"):
        return

    frappe.get_doc(
        {
            "doctype": "Supplier Scorecard Variable",
            "variable_label": "Average Delay Days",
            "param_name": "avg_days_late",
            "path": "client_akivision.utils.supplier_scorecard.get_avg_days_late",
            "is_custom": 1,
            "description": "Average delay days per shipment for the period",
        }
    ).insert(ignore_permissions=True)


def create_scorecard_criteria():
    """Create default scoring criteria for delivery performance."""
    criteria = [
        {
            "criteria_name": "到货及时率",
            "max_score": 100,
            "weight": 60,
            "formula": "({on_time_shipment_num} / {total_shipments}) * 100",
        },
        {
            "criteria_name": "平均延迟天数",
            "max_score": 100,
            "weight": 40,
            "formula": "max(0, 100 - ({avg_days_late} * 10))",
        },
    ]

    for row in criteria:
        if frappe.db.exists("Supplier Scorecard Criteria", row["criteria_name"]):
            continue
        frappe.get_doc({"doctype": "Supplier Scorecard Criteria", **row}).insert(
            ignore_permissions=True
        )


def create_scorecard_standings():
    """Create Chinese supplier rating standings."""
    standings = [
        {
            "standing_name": "A级",
            "standing_color": "Blue",
            "min_grade": 90,
            "max_grade": 100,
        },
        {
            "standing_name": "B级",
            "standing_color": "Green",
            "min_grade": 80,
            "max_grade": 90,
        },
        {
            "standing_name": "C级",
            "standing_color": "Yellow",
            "min_grade": 60,
            "max_grade": 80,
        },
        {
            "standing_name": "D级",
            "standing_color": "Red",
            "min_grade": 0,
            "max_grade": 60,
            "warn_pos": 1,
        },
    ]

    for row in standings:
        if frappe.db.exists("Supplier Scorecard Standing", row["standing_name"]):
            continue
        frappe.get_doc({"doctype": "Supplier Scorecard Standing", **row}).insert(
            ignore_permissions=True
        )
