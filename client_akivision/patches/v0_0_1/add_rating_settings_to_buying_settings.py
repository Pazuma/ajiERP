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

# 与“供应商评级标准”保持一致的字段说明；这些说明也显示在采购设置的
# 默认评级页签中，避免用户只看到数字而不清楚评分方向。
_RATING_DESCRIPTIONS = {
    "enabled": "启用后按本页签配置自动计算供应商评级。",
    "rating_frequency": "自动评级的执行周期。",
    "evaluation_period_months": "评级时向前统计的订单数据窗口（月）。",
    "min_evaluated_orders": "达到该数量的可评估订单后才计算评级。",
    "previous_score_weight": "最终得分中上期评级得分所占的权重；其余部分使用本期得分。",
    "weight_on_time": "到货及时率维度在总分中的权重。",
    "weight_delay": "延迟天数维度在总分中的权重。",
    "weight_lead_time": "实际交期维度在总分中的权重。",
    "weight_return": "退货率维度在总分中的权重。",
    "on_time_full_score_rate": "及时率达到该线即满分。",
    "on_time_zero_score_rate": "及时率低于该线记 0 分。",
    "delay_full_score_days": "平均延迟不超过该天数即满分。",
    "delay_zero_score_days": "平均延迟达到该天数记 0 分。",
    "delay_tolerance_ratio": "每个订单行的允许延迟 = 承诺交期 × 该比例；超出部分才计入评分延迟。",
    "delay_tolerance_floor_days": "每个订单行允许延迟的最低天数。",
    "delay_tolerance_cap_days": "每个订单行允许延迟的最高天数；0 表示不封顶。",
    "lead_time_target_days": "平均实际交期不超过该天数即满分。",
    "lead_time_zero_score_days": "平均实际交期达到该天数记 0 分。",
    "return_full_score_rate": "退货率不超过该线即满分。",
    "return_zero_score_rate": "退货率达到该线记 0 分。",
    "grade_a_min": "最终得分达到该值评为 A 级。",
    "grade_b_min": "最终得分达到该值评为 B 级。",
    "grade_c_min": "最终得分达到该值评为 C 级；低于该值评为 D 级。",
}


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

    def add_layout(fieldname, fieldtype, label=None, hidden=False):
        nonlocal previous_field
        field = {
            "fieldname": fieldname,
            "fieldtype": fieldtype,
            "insert_after": previous_field,
        }
        if label:
            field["label"] = label
        if hidden:
            field["hidden"] = 1
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
        if suffix in _RATING_DESCRIPTIONS:
            field["description"] = _RATING_DESCRIPTIONS[suffix]
        fields.append(field)
        previous_field = field["fieldname"]

    # Start after the complete native document-naming tab so the rating tab is
    # isolated from every native Buying Settings layout group.
    add_layout("custom_rating_section", "Tab Break", "Supplier Rating")

    add_layout("custom_rating_operation_section", "Section Break", "Rating Operation")
    add_rating_field("enabled")
    add_rating_field("rating_frequency")
    add_rating_field("min_evaluated_orders")
    add_layout("custom_rating_operation_column", "Column Break")
    add_rating_field("evaluation_period_months")
    add_rating_field("previous_score_weight")

    add_layout("custom_rating_weights_section", "Section Break", "Dimension Weights")
    add_rating_field("weight_on_time")
    add_rating_field("weight_delay")
    add_layout("custom_rating_weights_column", "Column Break")
    add_rating_field("weight_lead_time")
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
    add_rating_field("delay_tolerance_floor_days")
    add_layout("custom_rating_tolerance_column", "Column Break")
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
    add_rating_field("grade_c_min")

    # These breaks were used by the first, over-segmented version of the tab.
    # Keep their Custom Field records for idempotent upgrades, but hide them so
    # they cannot introduce empty rows or extra separators in existing sites.
    for fieldname, fieldtype in (
        ("custom_rating_sampling_section", "Section Break"),
        ("custom_rating_sampling_column", "Column Break"),
        ("custom_rating_weights_second_section", "Section Break"),
        ("custom_rating_weights_second_column", "Column Break"),
        ("custom_rating_tolerance_cap_section", "Section Break"),
        ("custom_rating_grades_last_section", "Section Break"),
    ):
        add_layout(fieldname, fieldtype, hidden=True)
    create_custom_fields({"Buying Settings": fields}, update=True)
    # create_custom_fields 的 update 行为在不同 Frappe 版本中不会覆盖已有
    # Custom Field 的描述，因此显式幂等回写，保证已部署站点也能补齐注释。
    for suffix, description in _RATING_DESCRIPTIONS.items():
        fieldname = f"custom_rating_{suffix}"
        if frappe.db.exists("Custom Field", {"dt": "Buying Settings", "fieldname": fieldname}):
            frappe.db.set_value(
                "Custom Field",
                {"dt": "Buying Settings", "fieldname": fieldname},
                "description",
                description,
                update_modified=False,
            )

    # Unhide section/column breaks that are now used as visible layout elements
    # (they may have been created as hidden by an earlier version of this patch).
    _unhide_layout_fields()

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
    _reorder_rating_fields()


def _reorder_rating_fields():
    """Idempotently set idx for custom_rating_* fields so same-dimension params
    are horizontally aligned (full-score left, zero-score right)."""
    layout_order = [
        "custom_rating_section",
        "custom_rating_operation_section",
        "custom_rating_enabled",
        "custom_rating_rating_frequency",
        "custom_rating_min_evaluated_orders",
        "custom_rating_operation_column",
        "custom_rating_evaluation_period_months",
        "custom_rating_previous_score_weight",
        "custom_rating_weights_section",
        "custom_rating_weight_on_time",
        "custom_rating_weight_delay",
        "custom_rating_weights_column",
        "custom_rating_weight_lead_time",
        "custom_rating_weight_return",
        # On-time Rate Scoring
        "custom_rating_on_time_section",
        "custom_rating_on_time_full_score_rate",
        "custom_rating_on_time_column",
        "custom_rating_on_time_zero_score_rate",
        # Delay Days Scoring
        "custom_rating_delay_section",
        "custom_rating_delay_full_score_days",
        "custom_rating_delay_column",
        "custom_rating_delay_zero_score_days",
        # Delay Tolerance
        "custom_rating_tolerance_section",
        "custom_rating_delay_tolerance_ratio",
        "custom_rating_delay_tolerance_floor_days",
        "custom_rating_tolerance_column",
        "custom_rating_delay_tolerance_cap_days",
        # Lead Time Scoring
        "custom_rating_lead_time_section",
        "custom_rating_lead_time_target_days",
        "custom_rating_lead_time_column",
        "custom_rating_lead_time_zero_score_days",
        # Return Rate Scoring
        "custom_rating_return_section",
        "custom_rating_return_full_score_rate",
        "custom_rating_return_column",
        "custom_rating_return_zero_score_rate",
        # Rating Grades
        "custom_rating_grades_section",
        "custom_rating_grade_a_min",
        "custom_rating_grades_column",
        "custom_rating_grade_b_min",
        "custom_rating_grade_c_min",
    ]
    for idx, fieldname in enumerate(layout_order, start=1):
        frappe.db.set_value(
            "Custom Field",
            {"dt": "Buying Settings", "fieldname": fieldname},
            "idx",
            idx,
            update_modified=False,
        )


def _unhide_layout_fields():
    """Restore visible breaks from the first version that hid all layout rows.

    The patch is executed from ``after_migrate``. Existing sites may therefore
    already have the visible breaks as hidden Custom Fields; always repair them
    idempotently instead of relying on ``create_custom_fields(update=True)`` to
    overwrite their old hidden flag.
    """
    visible_fields = {
        "custom_rating_section",
        "custom_rating_operation_section",
        "custom_rating_operation_column",
        "custom_rating_weights_section",
        "custom_rating_weights_column",
        "custom_rating_on_time_section",
        "custom_rating_on_time_column",
        "custom_rating_delay_section",
        "custom_rating_delay_column",
        "custom_rating_tolerance_section",
        "custom_rating_tolerance_column",
        "custom_rating_lead_time_section",
        "custom_rating_lead_time_column",
        "custom_rating_return_section",
        "custom_rating_return_column",
        "custom_rating_grades_section",
        "custom_rating_grades_column",
    }
    for fieldname in visible_fields:
        if frappe.db.exists("Custom Field", {"dt": "Buying Settings", "fieldname": fieldname}):
            frappe.db.set_value(
                "Custom Field",
                {"dt": "Buying Settings", "fieldname": fieldname},
                "hidden",
                0,
                update_modified=False,
            )
