import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# fieldname suffix -> (fieldtype, label, options)
_RATING_FIELDS = [
    ("enabled", "Check", "Enable Auto Rating", None),
    ("rating_frequency", "Select", "Rating Frequency", "\nWeekly\nMonthly\nQuarterly"),
    ("evaluation_period_months", "Int", "Evaluation Period (Months)", None),
    ("min_evaluated_orders", "Int", "Minimum Evaluated Orders", None),
    ("previous_score_weight", "Int", "Previous Score Weight (%)", None),
    ("weight_on_time", "Int", "On-time Rate Weight (%)", None),
    ("weight_delay", "Int", "Delay Days Weight (%)", None),
    ("weight_lead_time", "Int", "Lead Time Weight (%)", None),
    ("weight_return", "Int", "Return Rate Weight (%)", None),
    ("on_time_full_score_rate", "Int", "On-time Full Score Rate (%)", None),
    ("on_time_zero_score_rate", "Int", "On-time Zero Score Rate (%)", None),
    ("delay_full_score_days", "Int", "Delay Full Score Days", None),
    ("delay_zero_score_days", "Int", "Delay Zero Score Days", None),
    ("delay_tolerance_ratio", "Int", "Delay Tolerance Ratio (%)", None),
    ("delay_tolerance_floor_days", "Int", "Delay Tolerance Floor (Days)", None),
    ("delay_tolerance_cap_days", "Int", "Delay Tolerance Cap (Days)", None),
    ("lead_time_target_days", "Int", "Lead Time Full Score Days", None),
    ("lead_time_zero_score_days", "Int", "Lead Time Zero Score Days", None),
    ("return_full_score_rate", "Float", "Return Full Score Rate (%)", None),
    ("return_zero_score_rate", "Float", "Return Zero Score Rate (%)", None),
    ("grade_a_min", "Int", "Grade A Minimum Score", None),
    ("grade_b_min", "Int", "Grade B Minimum Score", None),
    ("grade_c_min", "Int", "Grade C Minimum Score", None),
]


def execute():
    """Move the default supplier rating config into Buying Settings as a tab.

    Idempotent: create_custom_fields(update=True) only adds missing fields, and
    values are migrated from the legacy Supplier Rating Settings single only
    while it still exists.
    """
    field_definitions = {suffix: (fieldtype, label, options) for suffix, fieldtype, label, options in _RATING_FIELDS}
    fields = []
    # ``document_naming_tab`` is only the beginning of the native tab. Its
    # naming-series controls follow it, and ERPNext's runtime field order puts
    # ``transaction_naming_html`` last (after ``column_break_kdcm``). Insert
    # after that final native field so no standard field can leak into this tab.
    previous_field = "transaction_naming_html"

    def add_layout(fieldname, fieldtype, label=None):
        nonlocal previous_field
        field = {
            "fieldname": fieldname,
            "fieldtype": fieldtype,
            "insert_after": previous_field,
        }
        if label:
            field["label"] = label
        fields.append(field)
        previous_field = fieldname

    def add_rating_field(suffix):
        nonlocal previous_field
        fieldtype, label, options = field_definitions[suffix]
        field = {
            "fieldname": f"custom_rating_{suffix}",
            "fieldtype": fieldtype,
            "label": label,
            "insert_after": previous_field,
        }
        if options:
            field["options"] = options
        fields.append(field)
        previous_field = field["fieldname"]

    # Start after the complete native document-naming tab so the rating tab is
    # isolated from every native Buying Settings layout group.
    add_layout("custom_rating_section", "Tab Break", "Supplier Rating")

    add_layout("custom_rating_operation_section", "Section Break", "Rating Operation")
    add_rating_field("enabled")
    add_rating_field("rating_frequency")
    add_layout("custom_rating_operation_column", "Column Break")
    add_rating_field("evaluation_period_months")
    add_layout("custom_rating_sampling_section", "Section Break")
    add_rating_field("min_evaluated_orders")
    add_layout("custom_rating_sampling_column", "Column Break")
    add_rating_field("previous_score_weight")

    add_layout("custom_rating_weights_section", "Section Break", "Dimension Weights")
    add_rating_field("weight_on_time")
    add_layout("custom_rating_weights_column", "Column Break")
    add_rating_field("weight_lead_time")
    add_layout("custom_rating_weights_second_section", "Section Break")
    add_rating_field("weight_delay")
    add_layout("custom_rating_weights_second_column", "Column Break")
    add_rating_field("weight_return")

    add_layout("custom_rating_on_time_section", "Section Break", "On-time Rate Scoring")
    add_rating_field("on_time_full_score_rate")
    add_layout("custom_rating_on_time_column", "Column Break")
    add_rating_field("on_time_zero_score_rate")

    add_layout("custom_rating_delay_section", "Section Break", "Delay Days Scoring")
    add_rating_field("delay_full_score_days")
    add_layout("custom_rating_delay_column", "Column Break")
    add_rating_field("delay_zero_score_days")
    add_layout("custom_rating_tolerance_section", "Section Break", "Delay Tolerance")
    add_rating_field("delay_tolerance_ratio")
    add_layout("custom_rating_tolerance_column", "Column Break")
    add_rating_field("delay_tolerance_floor_days")
    add_layout("custom_rating_tolerance_cap_section", "Section Break")
    add_rating_field("delay_tolerance_cap_days")

    add_layout("custom_rating_lead_time_section", "Section Break", "Lead Time Scoring")
    add_rating_field("lead_time_target_days")
    add_layout("custom_rating_lead_time_column", "Column Break")
    add_rating_field("lead_time_zero_score_days")

    add_layout("custom_rating_return_section", "Section Break", "Return Rate Scoring")
    add_rating_field("return_full_score_rate")
    add_layout("custom_rating_return_column", "Column Break")
    add_rating_field("return_zero_score_rate")

    add_layout("custom_rating_grades_section", "Section Break", "Rating Grades")
    add_rating_field("grade_a_min")
    add_layout("custom_rating_grades_column", "Column Break")
    add_rating_field("grade_b_min")
    add_layout("custom_rating_grades_last_section", "Section Break")
    add_rating_field("grade_c_min")
    create_custom_fields({"Buying Settings": fields}, update=True)

    if frappe.db.exists("DocType", "Supplier Rating Settings"):
        for suffix, _fieldtype, _label, _options in _RATING_FIELDS:
            try:
                value = frappe.db.get_single_value("Supplier Rating Settings", suffix)
            except Exception:
                value = None
            if value is not None:
                frappe.db.set_single_value(
                    "Buying Settings", f"custom_rating_{suffix}", value
                )

    frappe.db.updatedb("Buying Settings")
    frappe.clear_cache(doctype="Buying Settings")
