import frappe
from frappe import _

from china_finance.services.sales_order_finance_accounting import DOCTYPE, source_context
from china_finance.services.sales_order_finance_permissions import assert_finance_access


def execute(filters=None):
	assert_finance_access()
	filters = frappe._dict(filters or {})
	if not filters.company:
		frappe.throw(_("请选择公司，避免合计不同本位币。"))
	conditions = {"company": filters.company}
	for field in ("sales_order", "sales_invoice", "customer"):
		if filters.get(field):
			conditions[field] = filters[field]
	if filters.from_date and filters.to_date:
		conditions["posting_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.from_date:
		conditions["posting_date"] = [">=", filters.from_date]
	elif filters.to_date:
		conditions["posting_date"] = ["<=", filters.to_date]
	fields = ["name", "sales_order", "sales_invoice", "customer", "posting_date", "status", "company_currency",
		"base_revenue", "base_sales_cost", "base_tax", "base_gross_profit", "gross_margin", "complete", "source_hash", "active_key"]
	rows = frappe.get_list(DOCTYPE, filters=conditions, fields=fields, order_by="posting_date desc, creation desc", limit_page_length=0)
	data, counts = [], {"草稿": 0, "已确认": 0, "待复核": 0}
	for row in rows:
		if not frappe.has_permission("Sales Invoice", "read", doc=row.sales_invoice):
			continue
		if row.status == "已替代":
			continue
		if row.status == "已确认":
			try:
				context = source_context(row.sales_order, row.sales_invoice)
				if context["source_hash"] != row.source_hash or not row.active_key:
					row.status = "待复核"
			except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError):
				row.status = "待复核"
		counts[row.status] = counts.get(row.status, 0) + 1
		if row.status != "已确认":
			# Only effective confirmations contribute monetary totals.
			for field in ("base_revenue", "base_sales_cost", "base_tax", "base_gross_profit", "gross_margin"):
				row[field] = None
		if not filters.status or row.status == filters.status:
			data.append(row)
	columns = [
		dict(fieldname="name", label=_("核算版本"), fieldtype="Link", options=DOCTYPE, width=150),
		dict(fieldname="sales_order", label=_("销售订单"), fieldtype="Link", options="Sales Order", width=170),
		dict(fieldname="sales_invoice", label=_("销售发票"), fieldtype="Link", options="Sales Invoice", width=170),
		dict(fieldname="customer", label=_("客户"), fieldtype="Link", options="Customer", width=140),
		dict(fieldname="posting_date", label=_("核算日期"), fieldtype="Date", width=100),
		dict(fieldname="status", label=_("状态"), fieldtype="Data", width=100),
		dict(fieldname="company_currency", label=_("本位币"), fieldtype="Link", options="Currency", width=80),
		*[dict(fieldname=field, label=_(label), fieldtype="Currency", options="company_currency", width=140)
			for field, label in (("base_revenue", "已确认未税收入"), ("base_sales_cost", "已确认匹配成本"), ("base_tax", "已确认税费"), ("base_gross_profit", "已确认管理毛利"))],
		dict(fieldname="gross_margin", label=_("毛利率 (%)"), fieldtype="Percent", width=100),
	]
	summary = [dict(label=_(status), value=count, datatype="Int", indicator="Green" if status == "已确认" else "Orange") for status, count in counts.items()]
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	for field, label in (("base_revenue", "已确认未税收入"), ("base_sales_cost", "已确认匹配成本"), ("base_tax", "已确认税费"), ("base_gross_profit", "已确认管理毛利")):
		summary.append(dict(label=_(label), value=sum(row.get(field) or 0 for row in data), datatype="Currency", currency=currency))
	return columns, data, _("仅当前有效确认版本计入金额；草稿和待复核记录仅用于跟进。此表为管理核算，不替代正式账簿。"), None, summary
