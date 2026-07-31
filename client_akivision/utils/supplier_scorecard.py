import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


@frappe.whitelist()
def preview_supplier_scorecard(scorecard, start_date, end_date):
    """Preview a scorecard period without creating any records or changing the supplier rating."""
    scorecard_doc = frappe.get_doc("Supplier Scorecard", scorecard)
    scorecard_doc.check_permission("read")

    start_date = getdate(start_date)
    end_date = getdate(end_date)
    if start_date > end_date:
        frappe.throw(_("开始日期不能晚于截止日期"))
    if end_date > getdate(nowdate()):
        frappe.throw(_("评分测试的截止日期不能晚于今天"))

    from erpnext.buying.doctype.supplier_scorecard_period.supplier_scorecard_period import (
        make_supplier_scorecard,
    )

    period = make_supplier_scorecard(scorecard_doc.name)
    period.start_date = start_date
    period.end_date = end_date
    period.validate()

    return {
        "supplier": scorecard_doc.supplier,
        "start_date": start_date,
        "end_date": end_date,
        "total_score": period.total_score,
        "criteria": [
            {
                "name": row.criteria_name,
                "score": row.score,
                "max_score": row.max_score,
                "weight": row.weight,
            }
            for row in period.criteria
        ],
        "variables": [
            {
                "label": row.variable_label,
                "value": row.value,
            }
            for row in period.variables
        ],
    }


def get_avg_days_late(scorecard):
    """Return the average delay days per shipment for the scorecard period.

    Reuses ERPNext's native get_total_days_late and get_total_shipments.
    """
    from erpnext.buying.doctype.supplier_scorecard_variable.supplier_scorecard_variable import (
        get_total_days_late,
        get_total_shipments,
    )

    total_late = flt(get_total_days_late(scorecard))
    total = flt(get_total_shipments(scorecard))
    return total_late / total if total else 0


def update_supplier_rating(doc, method=None):
    """Write a formally evaluated scorecard standing back to the Supplier master."""
    if not doc.supplier:
        return

    # 自动评级引擎启用后，评级字段由 supplier_rating.update_all_supplier_ratings 维护，
    # 原生记分卡不再回写，避免两条链路互相覆盖。默认配置已迁入
    # Buying Settings；旧的 Supplier Rating Settings DocType 会在迁移中被删除。
    from client_akivision.utils.supplier_rating import get_settings

    if get_settings().get("enabled"):
        return

    has_formal_period = frappe.db.exists(
        "Supplier Scorecard Period", {"scorecard": doc.name, "docstatus": 1}
    )
    rating = doc.status if has_formal_period else ""
    frappe.db.set_value("Supplier", doc.supplier, "custom_supplier_rating", rating)


def refresh_supplier_rating_from_period(doc, method=None):
    """Recalculate the parent scorecard after a formal period is submitted or cancelled."""
    if not doc.scorecard or not frappe.db.exists("Supplier Scorecard", doc.scorecard):
        return

    scorecard = frappe.get_doc("Supplier Scorecard", doc.scorecard)
    # Native validation recalculates the weighted score and resolves its standing.
    scorecard.save(ignore_permissions=True)
    update_supplier_rating(scorecard)


def create_supplier_scorecard(doc, method=None):
    """Create a default Supplier Scorecard for a new supplier.

    This hook is optional. It requires that the default standings and criteria
    already exist in the system (created by patches).
    """
    if frappe.db.exists("Supplier Scorecard", doc.name):
        return

    criteria = get_default_criteria()
    standings = get_default_standings()

    if not criteria or not standings:
        return

    scorecard = frappe.get_doc(
        {
            "doctype": "Supplier Scorecard",
            "supplier": doc.name,
            "period": "Per Month",
            "weighting_function": "{total_score} * max(0, min(1, (12 - {period_number}) / 12))",
            "criteria": criteria,
            "standings": standings,
        }
    )
    scorecard.insert(ignore_permissions=True)


def get_default_criteria():
    """Return a list of scoring criteria rows for the default scorecard."""
    criteria_names = ["到货及时率", "平均延迟天数"]
    rows = []
    for name in criteria_names:
        if not frappe.db.exists("Supplier Scorecard Criteria", name):
            return []
        max_score, formula, weight = frappe.db.get_value(
            "Supplier Scorecard Criteria", name, ["max_score", "formula", "weight"]
        )
        rows.append(
            {
                "criteria_name": name,
                "max_score": max_score,
                "formula": formula,
                "weight": weight,
            }
        )
    return rows


def get_default_standings():
    """Return a list of standing rows for the default scorecard."""
    standings = frappe.get_all(
        "Supplier Scorecard Standing",
        filters={"standing_name": ["in", ["A级", "B级", "C级", "D级"]]},
        fields=[
            "standing_name",
            "standing_color",
            "min_grade",
            "max_grade",
            "warn_rfqs",
            "warn_pos",
            "prevent_rfqs",
            "prevent_pos",
        ],
    )
    return standings
