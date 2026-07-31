import frappe
from frappe import _
from frappe.utils import flt

from client_akivision.client_akivision.api.operations_kpi import normalise_filters
from client_akivision.utils.supplier_rating import (
	calculate_final_rating_score,
	collect_supplier_metrics,
	get_rating_standard_for_supplier,
	resolve_grade,
	score_supplier,
)


def execute(filters=None):
    filters = normalise_filters(filters)
    data = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_report_summary(data):
    purchase_order_count = sum(flt(row.purchase_order_count) for row in data)
    evaluated_order_count = sum(flt(row.evaluated_order_count) for row in data)
    pending_order_count = sum(flt(row.pending_order_count) for row in data)
    on_time_order_count = sum(flt(row.on_time_order_count) for row in data)
    delayed_order_count = sum(flt(row.delayed_order_count) for row in data)
    on_time_rate = (on_time_order_count / evaluated_order_count * 100) if evaluated_order_count else 0

    return [
        {"value": len(data), "label": _("供应商数"), "datatype": "Int", "indicator": "Blue"},
        {"value": purchase_order_count, "label": _("采购订单总数"), "datatype": "Int", "indicator": "Blue"},
        {"value": pending_order_count, "label": _("待评估订单数"), "datatype": "Int", "indicator": "Orange"},
        {"value": on_time_rate, "label": _("整体到货及时率"), "datatype": "Percent", "indicator": "Green"},
        {"value": delayed_order_count, "label": _("延迟订单数"), "datatype": "Int", "indicator": "Red"},
    ]


def get_columns():
    return [
        {"label": "供应商", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"label": "供应商名称", "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
        {"label": "采购订单总数", "fieldname": "purchase_order_count", "fieldtype": "Int", "width": 110},
        {"label": "待评估订单数", "fieldname": "pending_order_count", "fieldtype": "Int", "width": 110},
        {"label": "无法评估订单数", "fieldname": "unevaluable_order_count", "fieldtype": "Int", "width": 120},
        {"label": "按时到货订单数", "fieldname": "on_time_order_count", "fieldtype": "Int", "width": 125},
        {"label": "到货及时率", "fieldname": "on_time_rate", "fieldtype": "Percent", "width": 110},
        {"label": "延迟订单数", "fieldname": "delayed_order_count", "fieldtype": "Int", "width": 100},
        {"label": "平均延迟天数", "fieldname": "average_delay_days", "fieldtype": "Float", "width": 120},
        {"label": "容差后平均延迟(天)", "fieldname": "tolerance_adjusted_avg_delay", "fieldtype": "Float", "width": 140},
        {"label": "在途逾期订单数", "fieldname": "open_overdue_order_count", "fieldtype": "Int", "width": 130},
        {"label": "最长在途逾期(天)", "fieldname": "max_open_overdue_days", "fieldtype": "Int", "width": 140},
        {"label": "平均实际交期(天)", "fieldname": "average_lead_time_days", "fieldtype": "Float", "width": 140},
        {"label": "最长实际交期(天)", "fieldname": "max_lead_time_days", "fieldtype": "Int", "width": 140},
        {"label": "退货率", "fieldname": "return_rate", "fieldtype": "Percent", "width": 100},
        {"label": "最终评级得分", "fieldname": "composite_score", "fieldtype": "Float", "width": 115},
        {"label": "上期评级得分", "fieldname": "last_rating_score", "fieldtype": "Float", "width": 120},
        {"label": "评级标准", "fieldname": "rating_standard", "fieldtype": "Data", "width": 120},
        {"label": "供应商评级", "fieldname": "supplier_rating", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    # 与“采购到货延迟分析”共用同一套订单三态（按时/延迟/待评估）口径，
    # 保证两个报表的及时率一致；未到需求日期的订单不再虚增及时率。
    metrics = collect_supplier_metrics(filters.from_date, filters.to_date, filters.company)
    rows = list(metrics.values())
    if filters.get("supplier"):
        rows = [row for row in rows if row.supplier == filters.supplier]

    ratings = get_supplier_ratings([row.supplier for row in rows])
    last_rating_scores = get_last_rating_scores([row.supplier for row in rows], filters.to_date)
    data = []
    for row in rows:
        evaluated = flt(row.evaluated_order_count)
        lead_time_order_count = row.completed_order_count + row.open_overdue_order_count
        return_rate = row.return_rate
        standard = get_rating_standard_for_supplier(row.supplier)
        scores = score_supplier(
            {
                "evaluated_order_count": row.evaluated_order_count,
                "on_time_order_count": row.on_time_order_count,
                "delayed_order_count": row.delayed_order_count,
                "average_delay_days": row.average_delay_days,
                "total_delivered_delay_days": row.total_delivered_delay_days,
                "open_overdue_days": row.open_overdue_days,
                "tolerance_adjusted_avg_delay": row.tolerance_adjusted_avg_delay,
                "average_lead_time_days": row.average_lead_time_days if lead_time_order_count else None,
                "return_rate": return_rate,
            },
            standard,
        )
        current_score = scores.composite_score
        previous_score = last_rating_scores.get(row.supplier)
        final_score = (
            calculate_final_rating_score(current_score, previous_score, standard.previous_score_weight)
            if evaluated >= flt(standard.min_evaluated_orders)
            else None
        )
        data.append(
            frappe._dict(
                {
                    "supplier": row.supplier,
                    "supplier_name": row.supplier_name,
                    "purchase_order_count": row.order_count,
                    "evaluated_order_count": row.evaluated_order_count,
                    "pending_order_count": row.pending_order_count,
                    "unevaluable_order_count": row.unevaluable_order_count,
                    "on_time_order_count": row.on_time_order_count,
                    "on_time_rate": (row.on_time_order_count / evaluated * 100) if evaluated else 0,
                    "delayed_order_count": row.delayed_order_count,
                    "average_delay_days": round(flt(row.average_delay_days), 2),
                    "tolerance_adjusted_avg_delay": round(flt(row.tolerance_adjusted_avg_delay), 2),
                    "open_overdue_order_count": row.open_overdue_order_count,
                    "max_open_overdue_days": row.max_open_overdue_days or None,
                    "average_lead_time_days": round(flt(row.average_lead_time_days), 2)
                    if lead_time_order_count
                    else None,
                    "max_lead_time_days": row.max_lead_time_days if lead_time_order_count else None,
                    "return_rate": round(flt(return_rate), 2) if return_rate is not None else None,
                    "composite_score": round(flt(final_score), 2) if final_score is not None else None,
                    "last_rating_score": previous_score,
                    # Buying Settings 中的评级参数就是系统默认标准；没有供应商专用标准时
                    # 明确显示“默认标准”，避免报表出现空白且误以为未配置评级。
                    "rating_standard": standard.standard_name or _("默认标准"),
                    "supplier_rating": resolve_grade(final_score, standard)
                    if final_score is not None
                    else ratings.get(row.supplier),
                }
            )
        )
    return sorted(data, key=lambda row: row.supplier_name or row.supplier)


def get_supplier_ratings(suppliers):
    if not suppliers or not frappe.db.has_column("Supplier", "custom_supplier_rating"):
        return {}
    return {
        row.name: row.custom_supplier_rating
        for row in frappe.get_all(
            "Supplier",
            filters={"name": ("in", suppliers)},
            fields=["name", "custom_supplier_rating"],
        )
    }


def get_last_rating_scores(suppliers, before_date):
    """Return each supplier's latest saved score strictly before this report period."""
    if not suppliers:
        return {}
    scores = {}
    for row in frappe.get_all(
        "Supplier Rating Record",
        filters={"supplier": ("in", suppliers), "rating_date": ("<", before_date)},
        fields=["supplier", "composite_score"],
        order_by="rating_date desc, creation desc",
    ):
        scores.setdefault(row.supplier, round(flt(row.composite_score), 2))
    return scores
