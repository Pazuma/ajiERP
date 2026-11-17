import frappe
from frappe import _


def execute(filters=None):
	if not {"Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader", "Sales Order Finance Editor", "System Manager"}.intersection(frappe.get_roles(frappe.session.user)):
		frappe.throw(_("无权查看订单生产成本。"), frappe.PermissionError)
	from client_akivision.utils.order_record_permissions import get_order_scope_condition, is_scoped_user
	owner_condition = ""
	if is_scoped_user("Sales Order"):
		owner_condition = f" AND ({get_order_scope_condition('Sales Order', alias='so')})"
	filters = frappe._dict(filters or {})
	conditions, values = ["so.docstatus = 1"], {}
	for field in ("company", "sales_order"):
		if filters.get(field):
			conditions.append(f"so.{('name' if field == 'sales_order' else field)} = %({field})s")
			values[field] = filters[field]
	if filters.get("from_date"):
		conditions.append("so.transaction_date >= %(from_date)s"); values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("so.transaction_date <= %(to_date)s"); values["to_date"] = filters.to_date
	data = frappe.db.sql(f"""select so.name sales_order, so.transaction_date, so.customer, so.company,
		so.base_net_total order_amount, so.custom_order_loss_rate loss_rate,
		coalesce(sum(wo.custom_normal_loss_qty),0) normal_loss_qty,
		coalesce(sum(wo.custom_abnormal_loss_qty),0) abnormal_loss_qty,
		so.custom_material_cost material_cost, so.custom_auxiliary_material_cost auxiliary_material_cost,
		so.custom_labor_cost labor_cost, so.custom_manufacturing_overhead manufacturing_overhead,
		so.custom_scrap_recovery scrap_recovery, so.custom_production_cost production_cost,
		so.custom_recognized_revenue recognized_revenue, so.custom_delivered_cost delivered_cost,
		so.custom_gross_profit gross_profit, so.custom_gross_margin gross_margin
		from `tabSales Order` so left join `tabWork Order` wo on wo.sales_order=so.name and wo.docstatus<2
		where {' and '.join(conditions)}{owner_condition} group by so.name order by so.transaction_date desc, so.name desc""", values, as_dict=True)
	return get_columns(), data


def get_columns():
	return [
		{"fieldname":"sales_order","label":_("销售订单"),"fieldtype":"Link","options":"Sales Order","width":170},
		{"fieldname":"transaction_date","label":_("订单日期"),"fieldtype":"Date","width":100},
		{"fieldname":"customer","label":_("客户"),"fieldtype":"Link","options":"Customer","width":160},
		{"fieldname":"order_amount","label":_("订单金额"),"fieldtype":"Currency","width":120},
		{"fieldname":"loss_rate","label":_("损耗率 %"),"fieldtype":"Percent","width":90},
		{"fieldname":"normal_loss_qty","label":_("正常损耗"),"fieldtype":"Float","width":100},
		{"fieldname":"abnormal_loss_qty","label":_("异常损耗"),"fieldtype":"Float","width":100},
		{"fieldname":"material_cost","label":_("材料成本"),"fieldtype":"Currency","width":120},
		{"fieldname":"auxiliary_material_cost","label":_("辅助材料"),"fieldtype":"Currency","width":110},
		{"fieldname":"labor_cost","label":_("人工成本"),"fieldtype":"Currency","width":110},
		{"fieldname":"manufacturing_overhead","label":_("制造费用"),"fieldtype":"Currency","width":110},
		{"fieldname":"scrap_recovery","label":_("废料回收"),"fieldtype":"Currency","width":110},
		{"fieldname":"production_cost","label":_("生产总成本"),"fieldtype":"Currency","width":120},
		{"fieldname":"recognized_revenue","label":_("已发货收入"),"fieldtype":"Currency","width":120},
		{"fieldname":"delivered_cost","label":_("已发货成本"),"fieldtype":"Currency","width":120},
		{"fieldname":"gross_profit","label":_("毛利"),"fieldtype":"Currency","width":120},
		{"fieldname":"gross_margin","label":_("毛利率 %"),"fieldtype":"Percent","width":100},
	]
