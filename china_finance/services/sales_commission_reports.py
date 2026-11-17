"""Manager reports and a strict personal projection, including exports."""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from china_finance.services.sales_commission_permissions import SHEET, PAYMENT, assert_access, own_sales_person
from china_finance.services.sales_commission_payments import release_rows


def in_period(day, filters):
	return bool(day) and (not filters.from_date or getdate(day) >= getdate(filters.from_date)) and (not filters.to_date or getdate(day) <= getdate(filters.to_date))


def execute(filters=None, personal=False):
	filters = frappe._dict(filters or {})
	person = own_sales_person() if personal else None
	if not personal:
		assert_access()
	else:
		if not (frappe.session.user == "Administrator" or {"Sales User", "Sales Manager"} & set(frappe.get_roles())):
			frappe.throw(_("没有个人提成查询授权。"), frappe.PermissionError)
	if not filters.company:
		frappe.throw(_("请选择公司，避免混合不同本位币。"))
	if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("开始日期不能晚于结束日期。"))
	mode = "当前累计" if personal else (filters.mode or "当前累计")
	if mode not in ("当前累计", "期间计提变动", "期间实际发放"):
		frappe.throw(_("无效统计口径。"))
	if mode != "当前累计" and not (filters.from_date and filters.to_date):
		frappe.throw(_("期间统计必须填写开始和结束日期。"))
	conditions = {"company": filters.company}
	for field in ("sales_order", "customer"):
		if filters.get(field):
			conditions[field] = filters[field]
	data = []
	if mode == "期间实际发放":
		conditions.update(status="已确认", posting_date=["between", [filters.from_date, filters.to_date]])
		rows = frappe.get_list(PAYMENT, filters=conditions, fields=["name", "sales_order", "customer", "sales_person", "amount", "direction", "posting_date", "company_currency"], limit_page_length=0)
		for row in rows:
			if filters.sales_person and filters.sales_person != row.sales_person:
				continue
			data.append(dict(sales_order=row.sales_order, customer=row.customer, sales_person=row.sales_person,
				company_currency=row.company_currency, status="已确认", posting_date=row.posting_date,
				period_amount=flt(row.amount) * (1 if row.direction == "发放" else -1)))
	else:
		conditions["status"] = ["in", ["已确认", "待复核", "已作废"] if mode == "当前累计" else ["已确认", "已替代", "待复核", "已作废"]]
		# Personal users deliberately have no read permission on the source table.
		# Restrict candidate documents by their own Sales Person first, then project
		# just that person's result after checking the underlying order access.
		if personal:
			parents = frappe.get_all("Sales Commission Sheet Item", filters={"sales_person": person, "parenttype": SHEET}, pluck="parent")
			orders = frappe.get_all(SHEET, filters={"name": ["in", parents or ["__none__"]]}, pluck="sales_order")
			if conditions.get("sales_order"):
				if conditions["sales_order"] not in orders:
					orders = []
				else:
					orders = [conditions["sales_order"]]
			conditions["sales_order"] = ["in", orders or ["__none__"]]
			rows = frappe.get_all(SHEET, filters=conditions, pluck="name", order_by="creation desc")
		else:
			rows = frappe.get_list(SHEET, filters=conditions, pluck="name", order_by="creation desc", limit_page_length=0)
		for name in rows:
			doc = frappe.get_doc(SHEET, name)
			if not frappe.has_permission("Sales Order", "read", doc=doc.sales_order):
				continue
			if mode == "期间计提变动":
				previous = frappe.get_doc(SHEET, doc.previous_version) if doc.previous_version else None
				old = {r.sales_person: flt(r.commission_amount) for r in previous.sales_people} if previous else {}
				current = {r.sales_person: flt(r.commission_amount) for r in doc.sales_people}
				for p in sorted(set(old) | set(current)):
					if filters.sales_person and filters.sales_person != p:
						continue
					if in_period(doc.confirmed_date, filters):
						data.append(dict(sales_order=doc.sales_order, customer=doc.customer, sales_person=p,
							status=doc.status, company_currency=doc.company_currency, posting_date=doc.confirmed_date,
							period_amount=current.get(p, 0) - old.get(p, 0)))
					if doc.status == "已作废" and in_period(doc.voided_date, filters):
						data.append(dict(sales_order=doc.sales_order, customer=doc.customer, sales_person=p,
							status="已作废", company_currency=doc.company_currency, posting_date=doc.voided_date,
							period_amount=-current.get(p, 0)))
				continue
			if not doc.active_key:
				continue
			for row in release_rows(doc, internal=personal):
				if (person and row.sales_person != person) or (not personal and filters.sales_person and filters.sales_person != row.sales_person):
					continue
				# Explicit whitelist: no rates, bases, names of colleagues or snapshots.
				data.append({field: row.get(field) for field in ("sales_person", "commission_amount", "eligible_amount", "paid_amount", "available_amount", "unreleased_amount", "recoverable_amount", "status")}
					| dict(sales_order=doc.sales_order, customer=doc.customer, company_currency=doc.company_currency))
	columns = [dict(fieldname="sales_order", label=_("销售订单"), fieldtype="Link", options="Sales Order", width=170),
		dict(fieldname="customer", label=_("客户"), fieldtype="Data", width=140),
		dict(fieldname="sales_person", label=_("业务人员"), fieldtype="Data", width=120),
		dict(fieldname="status", label=_("状态"), fieldtype="Data", width=90),
		dict(fieldname="company_currency", label=_("本位币"), fieldtype="Data", width=70)]
	amounts = (("commission_amount", "有效累计提成"), ("eligible_amount", "累计可发放"), ("paid_amount", "累计净发放"),
		("available_amount", "本次可再发放"), ("unreleased_amount", "尚未满足条件"), ("recoverable_amount", "待追回")) if mode == "当前累计" else (("period_amount", mode),)
	columns.extend(dict(fieldname=field, label=_(label), fieldtype="Currency", options="company_currency", width=140) for field, label in amounts)
	if mode != "当前累计":
		columns.append(dict(fieldname="posting_date", label=_("发生日期"), fieldtype="Date", width=110))
	# Frozen snapshots stay visible, but do not contribute effective entitlement.
	for row in data:
		if row["status"] == "待复核" and mode == "当前累计":
			row["frozen_commission"] = row.pop("commission_amount", None)
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	summary = [dict(label=_(label), value=sum(flt(r.get(field)) for r in data), datatype="Currency", currency=currency) for field, label in amounts]
	message = _("当前累计按最新版本计算；待复核暂停新增发放，历史支付保留。期间计提为版本差额，期间支付按实际发生日期。此为管理台账，不生成总账或工资。")
	return columns, data, message, None, summary
