"""Automatic supplier rating engine.

Replaces the native Supplier Scorecard rating flow with a rule-driven,
zero-formula alternative: dimensions (on-time rate, delay days, actual lead
time, return rate) are scored against a "Supplier Rating Standard" resolved per
supplier (supplier-specific standard, else the default standard, else hardcoded
defaults), combined by weight and mapped to a grade (A级/B级/C级/D级) that is
written back to Supplier.custom_supplier_rating.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_months, cint, date_diff, flt, getdate, nowdate

RATING_DIMENSIONS = ("on_time", "delay", "lead_time", "return")

# 全套评分参数默认值：用于标准缺字段时兜底，以及无任何标准时构造兜底标准。
RATING_PARAM_DEFAULTS = {
    "weight_on_time": 40,
    "weight_delay": 20,
    "weight_lead_time": 15,
    "weight_return": 25,
    "on_time_full_score_rate": 100,
    "on_time_zero_score_rate": 0,
    "delay_full_score_days": 0,
    "delay_zero_score_days": 15,
    "lead_time_target_days": 7,
    "lead_time_zero_score_days": 30,
    "return_full_score_rate": 0,
    "return_zero_score_rate": 10,
    "delay_tolerance_ratio": 50,
    "delay_tolerance_floor_days": 0,
    "delay_tolerance_cap_days": 0,
    "grade_a_min": 90,
    "grade_b_min": 80,
    "grade_c_min": 60,
}

# 运行参数默认值（评级周期/窗口/最少样本/平滑权重）。
OPERATIONAL_DEFAULTS = {
    "rating_frequency": "Monthly",
    "evaluation_period_months": 3,
    "min_evaluated_orders": 3,
    "previous_score_weight": 30,
}


def get_settings():
    """Default rating config stored on Buying Settings (Supplier Rating tab).

    Returns a frappe._dict with unprefixed keys (custom_rating_* mapped back) so
    the scoring code reads the same field names as a rating standard. Reads via
    get_single_value to avoid stale doc/meta cache for the custom fields.
    """
    config = frappe._dict()
    # ``enabled`` is intentionally not a scoring parameter, but it is the
    # switch used by both scheduled and manual rating entry points.  Keep it
    # in the same configuration object after moving the settings to Buying
    # Settings; otherwise an enabled configuration is silently treated as off.
    for key in ("enabled", *RATING_PARAM_DEFAULTS, *OPERATIONAL_DEFAULTS):
        config[key] = frappe.db.get_single_value("Buying Settings", f"custom_rating_{key}")
    config.standard_name = None
    normalize_rating_params(config)
    for fieldname, default in OPERATIONAL_DEFAULTS.items():
        if config.get(fieldname) in (None, "", 0):
            config[fieldname] = default
    return config


def normalize_rating_params(doc):
    """Fill missing scoring params with hardcoded defaults (legacy/empty docs).

    Uses item assignment so it works for both Document and frappe._dict objects.
    """
    for fieldname, default in RATING_PARAM_DEFAULTS.items():
        if doc.get(fieldname) is None:
            doc[fieldname] = default


def validate_rating_params(doc):
    """Shared scoring-parameter validation for settings and standards."""
    if (doc.grade_a_min or 0) <= (doc.grade_b_min or 0) or (doc.grade_b_min or 0) <= (doc.grade_c_min or 0):
        frappe.throw(_("等级阈值必须满足 A级 > B级 > C级。"))
    if (doc.lead_time_zero_score_days or 0) <= (doc.lead_time_target_days or 0):
        frappe.throw(_("交期零分天数必须大于目标交期天数。"))
    if (doc.on_time_full_score_rate or 0) <= (doc.on_time_zero_score_rate or 0):
        frappe.throw(_("及时率满分线必须大于及时率零分线。"))
    if (doc.delay_full_score_days or 0) >= (doc.delay_zero_score_days or 0):
        frappe.throw(_("延迟满分天数必须小于延迟零分天数。"))
    if (doc.return_full_score_rate or 0) >= (doc.return_zero_score_rate or 0):
        frappe.throw(_("退货率满分线必须小于退货率零分线。"))
    if (doc.delay_tolerance_ratio or 0) < 0 or (doc.delay_tolerance_floor_days or 0) < 0:
        frappe.throw(_("延迟容差比例与保底天数不能为负。"))
    cap = doc.delay_tolerance_cap_days or 0
    if cap and cap <= (doc.delay_tolerance_floor_days or 0):
        frappe.throw(_("延迟容差封顶天数必须大于保底天数（0 表示不封顶）。"))


def get_rating_standard_for_supplier(supplier):
    """Resolve the full rating config for a supplier.

    Returns a frappe._dict with every scoring param plus the operational params
    (rating_frequency, evaluation_period_months, min_evaluated_orders,
    previous_score_weight) and `standard_name` (None when the global settings
    default config is used). Priority: supplier's linked standard -> global
    settings. A standard's blank operational params fall back to the settings
    defaults. Reads via the database so deleted standards are never served stale.
    """
    settings = get_settings()
    standard_name = None
    if supplier and frappe.db.has_column("Supplier", "custom_rating_standard"):
        standard_name = frappe.db.get_value("Supplier", supplier, "custom_rating_standard")
    row = (
        frappe.db.get_value("Supplier Rating Standard", standard_name, "*", as_dict=True)
        if standard_name
        else None
    )
    if row is None:
        # 未指定标准，或链接的标准已被删除（悬空链接）→ 采购设置里的默认配置兜底。
        return get_settings()
    else:
        config = frappe._dict(row)
        # 标准的运行参数留空时回退到全局默认。
        if not config.get("rating_frequency"):
            config.rating_frequency = settings.rating_frequency
        if not cint(config.get("evaluation_period_months")):
            config.evaluation_period_months = settings.evaluation_period_months
    normalize_rating_params(config)
    for fieldname, default in OPERATIONAL_DEFAULTS.items():
        if config.get(fieldname) in (None, "", 0):
            config[fieldname] = default
    return config


def get_supplier_return_rates(from_date, to_date, company=None):
    """Return {supplier: return rate %} based on submitted purchase receipts."""
    conditions = "pr.docstatus = 1 AND pr.posting_date BETWEEN %(from_date)s AND %(to_date)s"
    if company:
        conditions += " AND pr.company = %(company)s"
    rows = frappe.db.sql(
        f"""
        SELECT pr.supplier,
            SUM(CASE WHEN pr.is_return = 0 THEN pri.qty ELSE 0 END) AS received_qty,
            SUM(CASE WHEN pr.is_return = 1 THEN ABS(pri.qty) ELSE 0 END) AS returned_qty
        FROM `tabPurchase Receipt` pr
        INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
        WHERE {conditions}
        GROUP BY pr.supplier
        """,
        {"from_date": from_date, "to_date": to_date, "company": company},
        as_dict=True,
    )
    return {
        row.supplier: (flt(row.returned_qty) / flt(row.received_qty) * 100)
        for row in rows
        if flt(row.received_qty) > 0
    }


def _linear_score(value, full_threshold, zero_threshold):
    """Score a metric linearly between its full-score and zero-score thresholds.

    Works for both directions: full_threshold < zero_threshold (lower is better,
    e.g. delay days) or full_threshold > zero_threshold (higher is better, e.g.
    on-time rate). Values beyond either end clamp to 100 / 0.
    """
    if zero_threshold == full_threshold:
        return 100.0 if value <= min(full_threshold, zero_threshold) else 0.0
    return max(0.0, min(100.0, (zero_threshold - value) / (zero_threshold - full_threshold) * 100))


def score_supplier(metrics, standard):
    """Score one supplier's metrics dict against a rating standard.

    Every dimension is scored by linear interpolation between a full-score
    threshold and a zero-score threshold from the standard, so the four
    dimensions read consistently. Dimensions without data are excluded and
    weights renormalised.
    """
    scores = {}
    evaluated = flt(metrics.get("evaluated_order_count"))
    if evaluated:
        on_time_rate = flt(metrics.get("on_time_order_count")) / evaluated * 100
        scores["on_time"] = _linear_score(
            on_time_rate, cint(standard.on_time_full_score_rate), cint(standard.on_time_zero_score_rate)
        )
        zero_days = flt(standard.delay_zero_score_days) or 1
        scores["delay"] = _linear_score(
            _scoring_delay_days(metrics, zero_days),
            flt(standard.delay_full_score_days),
            zero_days,
        )

    avg_lead = metrics.get("average_lead_time_days")
    if avg_lead is not None:
        scores["lead_time"] = _linear_score(
            flt(avg_lead), flt(standard.lead_time_target_days), flt(standard.lead_time_zero_score_days)
        )

    return_rate = metrics.get("return_rate")
    if return_rate is not None:
        scores["return"] = _linear_score(
            flt(return_rate), flt(standard.return_full_score_rate), flt(standard.return_zero_score_rate)
        )

    weights = {
        "on_time": cint(standard.weight_on_time),
        "delay": cint(standard.weight_delay),
        "lead_time": cint(standard.weight_lead_time),
        "return": cint(standard.weight_return),
    }
    total_weight = sum(weights[dim] for dim in scores if weights[dim] > 0)
    composite = None
    if total_weight:
        composite = sum(scores[dim] * weights[dim] for dim in scores if weights[dim] > 0) / total_weight

    return frappe._dict(
        {f"{dim}_score": scores.get(dim) for dim in RATING_DIMENSIONS}
        | {"composite_score": composite, "grade": resolve_grade(composite, standard)}
    )


def _scoring_delay_days(metrics, cap_days):
    """Average delay used for scoring.

    Prefers the tolerance-adjusted average (each order line gets an allowance
    proportional to its promised lead time). Falls back to the capped raw
    average when the caller did not provide tolerance-adjusted metrics.
    """
    adjusted = metrics.get("tolerance_adjusted_avg_delay")
    if adjusted is not None:
        return flt(adjusted)
    delayed = flt(metrics.get("delayed_order_count"))
    if not delayed:
        return 0.0
    delivered_total = metrics.get("total_delivered_delay_days")
    open_days = metrics.get("open_overdue_days")
    if delivered_total is None and open_days is None:
        # 旧调用方仅提供均值时退回原口径。
        return flt(metrics.get("average_delay_days"))
    capped_total = flt(delivered_total) + sum(min(flt(days), cap_days) for days in (open_days or []))
    return capped_total / delayed


def _line_tolerance(promised_lead_days, standard):
    """Allowed delay for one order line: promised lead time x ratio, clamped to floor/cap.

    Promised lead time is floored at 0 so anomalous lines whose schedule date
    precedes the order date never yield a negative tolerance (which would
    inflate, rather than reduce, the adjusted delay).
    """
    floor = flt(standard.delay_tolerance_floor_days)
    cap = flt(standard.delay_tolerance_cap_days)
    if promised_lead_days is None:
        return floor
    promised = max(0.0, flt(promised_lead_days))
    tol = max(promised * flt(standard.delay_tolerance_ratio) / 100, floor)
    return min(tol, cap) if cap > 0 else tol


def _tolerance_adjusted_average_delay(item_rows, cutoff_date, delayed_order_count, standard):
    """Average delay per delayed order after subtracting each line's tolerance.

    Raw delay mirrors the report definition: delivered-late lines use receipt vs
    schedule date; open overdue lines use cutoff vs schedule date. Each line's
    raw delay is reduced by its promised-lead-time tolerance before aggregating,
    so long-lead equipment is judged more leniently than short-lead items.
    """
    if not delayed_order_count:
        return 0.0
    # 与状态判定保持一致：在途逾期只累计到今天，未来截止日不计未发生的时间。
    cutoff_date = min(getdate(cutoff_date), getdate(nowdate()))
    orders = defaultdict(lambda: {"supplier": None, "adjusted": 0.0})
    for row in item_rows:
        if not row.expected_date:
            continue
        expected = getdate(row.expected_date)
        fully_received = flt(row.received_qty) >= flt(row.qty)
        if fully_received and row.receipt_date:
            raw_delay = max(0, date_diff(row.receipt_date, expected))
        elif not fully_received and expected < cutoff_date:
            raw_delay = max(0, date_diff(cutoff_date, expected))
        else:
            continue
        promised = (
            date_diff(expected, row.order_date)
            if row.order_date
            else None
        )
        adjusted = max(0.0, raw_delay - _line_tolerance(promised, standard))
        entry = orders[row.purchase_order]
        entry["supplier"] = row.supplier
        entry["adjusted"] = max(entry["adjusted"], adjusted)

    totals = defaultdict(float)
    for entry in orders.values():
        if entry["adjusted"] > 0 and entry["supplier"]:
            totals[entry["supplier"]] += entry["adjusted"]
    return totals


def resolve_grade(composite, standard):
    if composite is None:
        return None
    if composite >= cint(standard.grade_a_min):
        return "A级"
    if composite >= cint(standard.grade_b_min):
        return "B级"
    if composite >= cint(standard.grade_c_min):
        return "C级"
    return "D级"


def calculate_final_rating_score(current_score, previous_score, previous_score_weight):
    """Apply the same previous-period smoothing used for the saved rating.

    ``previous_score`` is ``None`` for a supplier's first rating. A stored zero
    is a valid prior rating and must therefore not be treated as missing.
    """
    if current_score is None:
        return None
    weight = cint(previous_score_weight)
    if previous_score is None or not weight:
        return flt(current_score)
    return flt(current_score) * (100 - weight) / 100 + flt(previous_score) * weight / 100


def _aggregate_order_metrics(orders):
    """Aggregate order-level delay status into per-supplier metric accumulators."""
    metrics = {}
    for row in orders:
        entry = metrics.setdefault(
            row.supplier,
            frappe._dict(
                supplier=row.supplier,
                supplier_name=row.supplier_name,
                order_count=0,
                evaluated_order_count=0,
                on_time_order_count=0,
                delayed_order_count=0,
                pending_order_count=0,
                unevaluable_order_count=0,
                total_delay_days=0,
                total_delivered_delay_days=0,
                open_overdue_days=[],
                open_overdue_order_count=0,
                max_open_overdue_days=0,
                completed_order_count=0,
                total_lead_time_days=0,
                open_overdue_lead_days=0,
                max_lead_time_days=0,
            ),
        )
        entry.order_count += 1
        if row.status == "on_time":
            entry.on_time_order_count += 1
        elif row.status == "delayed":
            entry.delayed_order_count += 1
            entry.total_delay_days += row.delay_days
            entry.total_delivered_delay_days += row.delivered_delay_days
            if row.open_overdue_days > 0:
                entry.open_overdue_days.append(row.open_overdue_days)
                entry.open_overdue_order_count += 1
                entry.max_open_overdue_days = max(entry.max_open_overdue_days, row.open_overdue_days)
        elif row.status == "unevaluable":
            entry.unevaluable_order_count += 1
        else:
            entry.pending_order_count += 1
        entry.evaluated_order_count = entry.on_time_order_count + entry.delayed_order_count
        if row.lead_time_days is not None:
            entry.max_lead_time_days = max(entry.max_lead_time_days, row.lead_time_days)
            if row.open_overdue_days > 0:
                entry.open_overdue_lead_days += row.lead_time_days
            else:
                entry.completed_order_count += 1
                entry.total_lead_time_days += row.lead_time_days
    return metrics


def _compute_supplier_metrics(item_rows, orders, to_date, from_date, company=None):
    """Build per-supplier metrics (with derived fields) from pre-fetched rows.

    Reuses the exact three-state evaluation used by the delay reports so ratings
    agree with the reports. Tolerance is computed per supplier using that
    supplier's resolved rating config.
    """
    metrics = _aggregate_order_metrics(orders)
    return_rates = get_supplier_return_rates(from_date, to_date, company)
    rows_by_supplier = defaultdict(list)
    for row in item_rows:
        rows_by_supplier[row.supplier].append(row)
    for supplier, entry in metrics.items():
        standard = get_rating_standard_for_supplier(supplier)
        entry.rating_standard = standard.standard_name
        adjusted_totals = _tolerance_adjusted_average_delay(
            rows_by_supplier.get(supplier, []), to_date, entry.delayed_order_count, standard
        )
        entry.average_delay_days = (
            entry.total_delay_days / entry.delayed_order_count if entry.delayed_order_count else 0
        )
        entry.tolerance_adjusted_avg_delay = (
            adjusted_totals.get(supplier, 0.0) / entry.delayed_order_count
            if entry.delayed_order_count
            else 0.0
        )
        entry.average_lead_time_days = (
            (entry.total_lead_time_days + entry.open_overdue_lead_days)
            / (entry.completed_order_count + entry.open_overdue_order_count)
            if (entry.completed_order_count + entry.open_overdue_order_count)
            else None
        )
        entry.return_rate = return_rates.get(supplier)
    return metrics


def collect_supplier_metrics(from_date, to_date, company=None):
    """Aggregate order-level delay status and return rates per supplier for a window."""
    from client_akivision.client_akivision.api.operations_kpi import (
        get_purchase_delay_item_rows,
        get_purchase_order_delay_status,
    )

    companies = [company] if company else frappe.get_all("Company", pluck="name")
    item_rows = []
    for name in companies:
        item_rows += get_purchase_delay_item_rows(
            frappe._dict(company=name, from_date=from_date, to_date=to_date)
        )
    orders = get_purchase_order_delay_status(item_rows, to_date)
    return _compute_supplier_metrics(item_rows, orders, to_date, from_date, company)


def compute_supplier_scores(from_date, to_date, company=None):
    """Return {supplier: metrics + scores + grade} for the given period."""
    metrics = collect_supplier_metrics(from_date, to_date, company)
    for supplier, entry in metrics.items():
        standard = get_rating_standard_for_supplier(supplier)
        entry.update(score_supplier(entry, standard))
    return metrics


def _fetch_rating_item_rows(from_date, to_date, company=None):
    from client_akivision.client_akivision.api.operations_kpi import get_purchase_delay_item_rows

    companies = [company] if company else frappe.get_all("Company", pluck="name")
    item_rows = []
    for name in companies:
        item_rows += get_purchase_delay_item_rows(
            frappe._dict(company=name, from_date=from_date, to_date=to_date)
        )
    return item_rows


def update_all_supplier_ratings(company=None, force=False):
    """Rate suppliers on their own schedule.

    Each supplier is evaluated against its resolved rating config (linked
    standard or the global default). A supplier is rated only when its own
    frequency is due today, unless force=True (manual recalculate rates all).
    Smooths against the previous score, logs a record and writes the grade back.
    """
    from client_akivision.client_akivision.api.operations_kpi import (
        get_purchase_order_delay_status,
    )

    settings = get_settings()
    if not settings.enabled:
        return 0

    to_date = getdate(nowdate())
    configs = {}
    suppliers = frappe.get_all("Supplier", filters={"disabled": 0}, pluck="name")
    max_period = 0
    for supplier in suppliers:
        cfg = get_rating_standard_for_supplier(supplier)
        configs[supplier] = cfg
        max_period = max(max_period, cint(cfg.evaluation_period_months) or 3)
    if not suppliers:
        return 0

    # 一次取最大窗口数据，再按各供应商自身窗口过滤，避免重复查询。
    item_rows = _fetch_rating_item_rows(add_months(to_date, -max_period), to_date, company)

    updated = 0
    for supplier, cfg in configs.items():
        freq = cfg.rating_frequency or "Monthly"
        if not force and not is_rating_due(freq, to_date):
            continue
        period = cint(cfg.evaluation_period_months) or 3
        from_date = add_months(to_date, -period)
        sup_rows = [r for r in item_rows if r.supplier == supplier and getdate(r.order_date) >= from_date]
        orders = get_purchase_order_delay_status(sup_rows, to_date)
        metrics = _compute_supplier_metrics(sup_rows, orders, to_date, from_date, company)
        entry = metrics.get(supplier)
        if not entry:
            continue
        entry.update(score_supplier(entry, cfg))

        min_orders = cint(cfg.min_evaluated_orders)
        weight = cint(cfg.previous_score_weight)
        if entry.evaluated_order_count < min_orders or entry.composite_score is None:
            continue

        # 上期得分始终取“今天之前”的最近一条记录，同日重跑不会二次平滑。
        previous_score = frappe.db.get_value(
            "Supplier Rating Record",
            {"supplier": supplier, "rating_date": ("<", to_date)},
            "composite_score",
            order_by="rating_date desc, creation desc",
        )
        current_score = flt(entry.composite_score)
        final_score = calculate_final_rating_score(current_score, previous_score, weight)
        grade = resolve_grade(final_score, cfg)

        _upsert_rating_record(
            supplier,
            to_date,
            {
                "frequency": freq,
                "rating_standard": cfg.standard_name,
                "period_from": from_date,
                "period_to": to_date,
                "evaluated_order_count": entry.evaluated_order_count,
                "on_time_score": entry.on_time_score,
                "delay_score": entry.delay_score,
                "lead_time_score": entry.lead_time_score,
                "return_score": entry.return_score,
                "current_score": current_score,
                # Float 列非空：无历史时落库为 0，平滑判断以查询到的历史记录为准。
                "previous_score": flt(previous_score),
                "previous_score_weight": weight,
                "composite_score": final_score,
                "grade": grade,
            },
        )
        frappe.db.set_value(
            "Supplier", supplier, "custom_supplier_rating", grade, update_modified=False
        )
        updated += 1
    return updated


def _upsert_rating_record(supplier, rating_date, values):
    """One rating record per supplier per day; reruns update instead of duplicating."""
    existing = frappe.db.exists(
        "Supplier Rating Record", {"supplier": supplier, "rating_date": rating_date}
    )
    if existing:
        frappe.db.set_value("Supplier Rating Record", existing, values, update_modified=False)
        return
    frappe.get_doc(
        {
            "doctype": "Supplier Rating Record",
            "supplier": supplier,
            "rating_date": rating_date,
            **values,
        }
    ).insert(ignore_permissions=True)


def is_rating_due(frequency, date=None):
    """Weekly runs on Monday, monthly on the 1st, quarterly on Jan/Apr/Jul/Oct 1st."""
    date = getdate(date or nowdate())
    frequency = frequency or "Monthly"
    if frequency == "Weekly":
        return date.weekday() == 0
    if frequency == "Quarterly":
        return date.day == 1 and date.month in (1, 4, 7, 10)
    return date.day == 1


def scheduled_update_supplier_ratings():
    """Daily scheduler entry: rates each supplier whose own frequency is due."""
    settings = get_settings()
    if not settings.enabled:
        return 0
    return update_all_supplier_ratings()


@frappe.whitelist()
def recalculate_supplier_ratings():
    """Manual trigger from the report page."""
    frappe.only_for(("System Manager", "Purchase Manager"))
    settings = get_settings()
    if not settings.enabled:
        frappe.throw(_("请先在“采购设置”的“供应商评级”页签中启用自动评级。"))
    updated = update_all_supplier_ratings(force=True)
    return {"updated": updated}
