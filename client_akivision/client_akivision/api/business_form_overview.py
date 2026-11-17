"""Permission-aware submitted business form overview for the KPI dashboard."""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from client_akivision.utils.kpi_page_permissions import check_business_form_overview_access

FINANCE_ROLES = {"System Manager", "Accounts Manager", "Accounts User"}

# Conservative first registry. More doctypes can be added without changing the API.
FORM_REGISTRY = [
	{"doctype": "Sales Order", "category": "销售", "label": "销售订单", "date": "transaction_date", "status": "status", "summary": "customer_name"},
	{"doctype": "Purchase Order", "category": "采购", "label": "采购订单", "date": "transaction_date", "status": "status", "summary": "supplier_name"},
	{"doctype": "Work Order", "category": "生产", "label": "生产工单", "date": "creation", "status": "status", "summary": "production_item"},
	{"doctype": "Stock Entry", "category": "库存", "label": "库存单", "date": "posting_date", "status": "docstatus", "summary": "stock_entry_type"},
	{"doctype": "Payment Entry", "category": "财务", "label": "收付款单", "date": "posting_date", "status": "docstatus", "summary": "party"},
	{"doctype": "Journal Entry", "category": "财务", "label": "会计凭证", "date": "posting_date", "status": "docstatus", "summary": "user_remark"},
]


def _can_see_finance():
	return bool(set(frappe.get_roles()) & FINANCE_ROLES)


def _registry():
	return [item for item in FORM_REGISTRY if item["category"] != "财务" or _can_see_finance()]


def _field_exists(doctype, field):
	return field in {df.fieldname for df in frappe.get_meta(doctype).fields}


def _duration(start_at, completed_at=None, status="进行中"):
	if not start_at:
		return {"duration_start_at": None, "duration_completed_at": completed_at, "duration_seconds": None, "duration_display": "无法计算", "duration_status": "缺少开始时间"}
	start = get_datetime(start_at)
	end = get_datetime(completed_at) if completed_at else now_datetime()
	seconds = max(int((end - start).total_seconds()), 0)
	days, remainder = divmod(seconds, 86400)
	hours, remainder = divmod(remainder, 3600)
	minutes = remainder // 60
	parts = []
	if days: parts.append(f"{days}天")
	if hours or days: parts.append(f"{hours}小时")
	parts.append(f"{minutes}分钟")
	return {"duration_start_at": start_at, "duration_completed_at": completed_at, "duration_seconds": seconds, "duration_display": "".join(parts), "duration_status": status}


def _latest_date(doctype, filters, field="posting_date"):
	if not frappe.db.exists(doctype, filters):
		return None
	rows = frappe.get_all(doctype, filters=filters, fields=[field], order_by=f"{field} desc", limit=1)
	return rows[0].get(field) if rows else None


def _business_duration(row, config):
	doctype, name = config["doctype"], row["name"]
	try:
		doc = frappe.get_doc(doctype, name)
		start = getattr(doc, "creation", None)
		completed = None
		status = "进行中"
		if doctype == "Sales Order":
			completed = _latest_date("Delivery Note", {"docstatus": 1, "against_sales_order": name})
			if completed and all(float(getattr(item, "delivered_qty", 0) or 0) >= float(getattr(item, "qty", 0) or 0) for item in doc.items): status = "已完成"
			else: completed = None
		elif doctype == "Purchase Order":
			completed = _latest_date("Purchase Receipt", {"docstatus": 1, "supplier": doc.supplier})
			if completed and all(float(getattr(item, "received_qty", 0) or 0) >= float(getattr(item, "qty", 0) or 0) for item in doc.items): status = "已完成"
			else: completed = None
		elif doctype == "Work Order":
			start = getattr(doc, "actual_start_date", None) or start
			if float(getattr(doc, "produced_qty", 0) or 0) >= float(getattr(doc, "qty", 0) or 0):
				completed = getattr(doc, "actual_end_date", None) or _latest_date("Stock Entry", {"docstatus": 1, "purpose": "Manufacture", "work_order": name})
				status = "已完成" if completed else "完成时间待补"
		return _duration(start, completed, status)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Business duration failed: {doctype} {name}")
		return _duration(None, None, "暂无法计算")


@frappe.whitelist()
def get_business_form_overview(filters=None, page=1, page_size=20):
	check_business_form_overview_access()
	filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else (filters or {}))
	page = max(cint(page), 1)
	page_size = min(max(cint(page_size) or 20, 1), 100)
	category = filters.get("category")
	doctype_filter = filters.get("doctype")
	view = filters.get("view") or "all"
	rows = []
	for config in _registry():
		if category and config["category"] != category:
			continue
		if doctype_filter and config["doctype"] != doctype_filter:
			continue
		if not frappe.has_permission(config["doctype"], "read"):
			continue
		meta = frappe.get_meta(config["doctype"])
		date_field = config["date"] if _field_exists(config["doctype"], config["date"]) else "creation"
		status_field = config["status"] if _field_exists(config["doctype"], config["status"]) else "docstatus"
		summary_field = config["summary"] if _field_exists(config["doctype"], config["summary"]) else "name"
		query_filters = {"docstatus": 1} if _field_exists(config["doctype"], "docstatus") else {}
		if filters.get("from_date"):
			query_filters[date_field] = [">=", filters.from_date]
		if filters.get("to_date"):
			query_filters.setdefault(date_field, ["<=", filters.to_date])
			if query_filters[date_field][0] == ">=":
				query_filters[date_field] = ["between", [filters.from_date, filters.to_date]]
		if view == "mine":
			query_filters["owner"] = frappe.session.user
		if filters.get("status"):
			query_filters[status_field] = filters.status
		if filters.get("text"):
			query_filters["name"] = ["like", f"%{filters.text}%"]
		or_filters = None
		if view == "assigned":
			or_filters = {"owner": frappe.session.user, "modified_by": frappe.session.user}
		try:
			for row in frappe.get_list(
				config["doctype"],
				filters=query_filters,
				or_filters=or_filters,
				fields=[
					"name", "owner", "modified",
					f"{date_field} as submitted_at",
					f"{status_field} as business_status",
					f"{summary_field} as summary",
				],
				order_by="modified desc",
				limit_page_length=101,
			):
				row.update(_business_duration(row, config))
				row.update({"doctype": config["doctype"], "form_label": config["label"], "category": config["category"]})
				rows.append(row)
		except Exception:
			# A missing optional field or unavailable table must not break the existing dashboard.
			continue
	rows.sort(key=lambda row: str(row.get("modified") or ""), reverse=True)
	start = (page - 1) * page_size
	statuses = [
		{"value": "1", "label": _("已提交")},
		{"value": "Completed", "label": _("已完成")},
		{"value": "To Deliver and Bill", "label": _("待交付和开票")},
	]
	return {
		"rows": rows[start : start + page_size],
		"total": len(rows),
		"has_more": len(rows) > start + page_size,
		"categories": sorted({x["category"] for x in _registry()}),
		"forms": [{"doctype": x["doctype"], "label": x["label"], "category": x["category"]} for x in _registry()],
		"statuses": statuses,
	}


@frappe.whitelist()
def export_business_form_overview(filters=None):
	"""Export only the same permission-filtered rows exposed by the list API."""
	check_business_form_overview_access()
	data = get_business_form_overview(filters=filters, page=1, page_size=100)
	columns = ["提交时间", "持续时间", "完成时间", "分类", "具体表单", "单据编号", "提交人", "状态", "最后更新时间"]
	rows = [[r.get("submitted_at"), r.get("duration_display"), r.get("duration_completed_at"), r.get("category"), r.get("form_label"), r.get("name"), r.get("owner"), r.get("business_status"), r.get("modified")] for r in data["rows"]]
	from frappe.utils.response import build_response
	frappe.response["filename"] = "业务表单总表.csv"
	frappe.response["filecontent"] = "\ufeff" + "\n".join([",".join(map(str, columns))] + [",".join(map(lambda x: str(x or ""), row)) for row in rows])
	frappe.response["type"] = "download"
	return build_response("download")
