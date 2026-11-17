import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("年份"), "fieldname": "year", "fieldtype": "Int", "width": 70},
		{"label": _("月份"), "fieldname": "month", "fieldtype": "Int", "width": 70},
		{"label": _("客户"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("客户代码"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
		{"label": _("日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("业务员"), "fieldname": "sales_person", "fieldtype": "Data", "width": 110},
		{"label": _("客户订单号"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 150},
		{"label": _("产品代码"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("货物名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("型号"), "fieldname": "model", "fieldtype": "Data", "width": 110},
		{"label": _("单位"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("数量"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("含税单价"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
		{"label": _("订单金额"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("送货单号"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 160},
		{"label": _("发票号"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 160},
		{"label": _("开票日期"), "fieldname": "invoice_date", "fieldtype": "Date", "width": 100},
		{"label": _("订单状态"), "fieldname": "order_status", "fieldtype": "Data", "width": 100},
		{"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
	]


def get_data(filters):
	conditions = ["dn.docstatus = 1", "dn.posting_date BETWEEN %(from_date)s AND %(to_date)s"]
	from client_akivision.utils.order_record_permissions import get_order_scope_condition, is_scoped_user

	if is_scoped_user("Sales Order"):
		conditions.append(f"({get_order_scope_condition('Sales Order', alias='so')})")
	params = {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}
	for field in ("customer", "item_code"):
		if filters.get(field):
			conditions.append(f"dn.{field} = %({field})s" if field == "customer" else f"dni.{field} = %({field})s")
			params[field] = filters.get(field)
	if filters.get("company"):
		conditions.append("dn.company = %(company)s")
		params["company"] = filters.company
	if filters.get("sales_order"):
		conditions.append("dni.against_sales_order = %(sales_order)s")
		params["sales_order"] = filters.sales_order

	return frappe.db.sql(
		f"""
		SELECT
			COALESCE(dn.custom_excel_year, YEAR(dn.posting_date)) AS year,
			COALESCE(dn.custom_excel_month, MONTH(dn.posting_date)) AS month,
			COALESCE(dn.custom_excel_customer_name, dn.customer_name) AS customer_name,
			dn.customer,
			dn.posting_date,
			COALESCE(dn.custom_excel_sales_person, (
				SELECT GROUP_CONCAT(DISTINCT st.sales_person ORDER BY st.idx SEPARATOR ', ')
				FROM `tabSales Team` st
				WHERE st.parent = dn.name AND st.parenttype = 'Delivery Note'
			)) AS sales_person,
			dn.name AS delivery_note,
			dn.custom_remarks AS remarks,
			dni.item_code,
			dni.item_name,
			COALESCE(dni.custom_excel_unit, dni.uom) AS uom,
			dni.qty,
			dni.rate,
			COALESCE(dni.custom_excel_order_amount, dni.amount) AS amount,
			dni.against_sales_order AS sales_order,
			COALESCE(dni.custom_excel_model, item.custom_external_model) AS model,
			COALESCE(dn.custom_excel_order_status, so.status) AS order_status,
			COALESCE(dn.custom_excel_invoice_no, GROUP_CONCAT(DISTINCT si.name ORDER BY si.name SEPARATOR ', ')) AS invoice_no,
			COALESCE(dn.custom_excel_invoice_date, MAX(si.posting_date)) AS invoice_date
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		LEFT JOIN `tabItem` item ON item.name = dni.item_code
		LEFT JOIN `tabSales Order` so ON so.name = dni.against_sales_order
		LEFT JOIN `tabSales Invoice Item` sii ON sii.dn_detail = dni.name
		LEFT JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
		WHERE {' AND '.join(conditions)}
		GROUP BY dni.name
		ORDER BY dn.posting_date DESC, dn.name DESC, dni.idx
		""",
		params,
		as_dict=True,
	)
