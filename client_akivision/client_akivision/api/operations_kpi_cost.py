"""Independent cost API; existing KPI endpoint remains unchanged."""
import frappe
from frappe.utils import cint, getdate

from client_akivision.utils.operations_kpi_cost_permissions import check_cost_company, check_cost_dashboard_access


def normalise_cost_filters(filters=None):
    values = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    result = frappe._dict({key: values.get(key) for key in ("company", "from_date", "to_date")})
    check_cost_company(result.company)
    if not result.from_date or not result.to_date:
        frappe.throw("请选择开始日期和截止日期。")
    result.from_date, result.to_date = getdate(result.from_date), getdate(result.to_date)
    if result.from_date > result.to_date:
        frappe.throw("开始日期不能晚于截止日期。")
    result.page = max(1, cint(values.get("page") or 1))
    result.page_length = min(100, max(1, cint(values.get("page_length") or 20)))
    return result


@frappe.whitelist()
def get_cost_dashboard_data(filters=None):
    check_cost_dashboard_access()
    from client_akivision.utils.operations_kpi_cost import build_cost_dashboard_data
    return build_cost_dashboard_data(normalise_cost_filters(filters))
