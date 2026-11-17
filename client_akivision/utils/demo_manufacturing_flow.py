"""Isolated manufacturing demo; never submit stock or accounting documents."""
import frappe
from frappe.utils import today, add_days


def create():
	marker = "生产完工回原订单演示-20261028"
	existing = frappe.db.get_value("Sales Order", {"po_no": marker}, "name")
	if existing:
		return describe(existing)
	company = "阿基视觉（东莞）"
	source = frappe.get_doc("Item", "演示物料-20261028")
	fg_code = "演示生产成品-20261028"
	if not frappe.db.exists("Item", fg_code):
		frappe.get_doc({"doctype": "Item", "item_code": fg_code, "item_name": "演示生产成品",
			"item_group": source.item_group, "stock_uom": source.stock_uom, "is_stock_item": 1,
			"is_sales_item": 1, "is_purchase_item": 0, "include_item_in_manufacturing": 1,
			"description": marker}).insert(ignore_permissions=True)
	operation = "演示装配工序-20261028"
	if not frappe.db.exists("Operation", operation):
		frappe.get_doc({"doctype": "Operation", "name": operation, "operation": operation,
			"description": "演示装配与完工检查"}).insert(ignore_permissions=True)
	station = "演示装配工位-20261028"
	if not frappe.db.exists("Workstation", station):
		frappe.get_doc({"doctype": "Workstation", "workstation_name": station,
			"production_capacity": 1, "hour_rate_labour": 30,
			"working_hours": [{"start_time": "00:00:00", "end_time": "23:59:00"}]}).insert(ignore_permissions=True)
	bom = frappe.get_doc({"doctype": "BOM", "item": fg_code, "company": company,
		"quantity": 1, "currency": "CNY", "with_operations": 1,
		"transfer_material_against": "Work Order", "items": [{"item_code": source.name,
		"qty": 2, "uom": source.stock_uom, "rate": 60}], "operations": [{"operation": operation,
		"workstation": station, "time_in_mins": 6, "hour_rate": 30}]})
	bom.insert(ignore_permissions=True)
	bom.submit()
	customer = frappe.db.get_value("Customer", {"customer_name": "演示客户-20261028"}, "name")
	so = frappe.get_doc({"doctype": "Sales Order", "company": company, "customer": customer,
		"transaction_date": today(), "delivery_date": add_days(today(), 7), "po_no": marker,
		"currency": "CNY", "items": [{"item_code": fg_code, "qty": 10, "rate": 200,
		"delivery_date": add_days(today(), 7), "warehouse": "成品 - T"}]})
	so.insert(ignore_permissions=True)
	so.submit()
	wo = frappe.get_doc({"doctype": "Work Order", "company": company, "production_item": fg_code,
		"bom_no": bom.name, "qty": 10, "sales_order": so.name, "sales_order_item": so.items[0].name,
		"source_warehouse": "仓库 - T", "wip_warehouse": "进行中 - T", "fg_warehouse": "成品 - T",
		"planned_start_date": today() + " 08:00:00", "use_multi_level_bom": 0,
		"transfer_material_against": "Work Order"})
	wo.get_items_and_operations_from_bom()
	wo.insert(ignore_permissions=True)
	wo.submit()
	cards = frappe.get_all("Job Card", {"work_order": wo.name}, pluck="name")
	if not cards:
		from erpnext.manufacturing.doctype.work_order.work_order import create_job_card
		card = create_job_card(wo, wo.operations[0])
		card.insert(ignore_permissions=True)
		cards = [card.name]
	for name in cards:
		card = frappe.get_doc("Job Card", name)
		card.append("time_logs", {"from_time": today() + " 09:00:00", "to_time": today() + " 10:00:00",
			"completed_qty": 10})
		card.save(ignore_permissions=True)
		card.submit()
	qi = frappe.get_doc({"doctype": "Quality Inspection", "company": company, "item_code": fg_code,
		"inspection_type": "In Process", "reference_type": "Work Order", "reference_name": wo.name,
		"custom_work_order": wo.name, "custom_inspection_qty": 10, "custom_accepted_qty": 10,
		"custom_rejected_qty": 0, "sample_size": 10, "inspected_by": "Administrator",
		"status": "Accepted", "remarks": "演示：完工10件，检验10件，合格10件；生产入库尚为草稿。"})
	qi.insert(ignore_permissions=True)
	qi.submit()
	from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry
	transfer = frappe.get_doc(make_stock_entry(wo.name, "Material Transfer for Manufacture", 10))
	transfer.items[0].qty = 22
	transfer.remarks = marker + "；计划领料22件，仅草稿，未实际出库。"
	transfer.insert(ignore_permissions=True)
	returned = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Transfer",
		"purpose": "Material Transfer", "company": company, "work_order": wo.name,
		"use_multi_level_bom": 0,
		"remarks": marker + "；计划余料退回2件，来源领料草稿：" + transfer.name,
		"items": [{"item_code": source.name, "qty": 2, "s_warehouse": "进行中 - T",
		"t_warehouse": "仓库 - T", "basic_rate": 60}]})
	returned.insert(ignore_permissions=True)
	manufacture = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", 10))
	manufacture.custom_quality_inspection = qi.name
	manufacture.remarks = marker + "；完工入库10件，仅草稿，不增加可用库存。"
	manufacture.insert(ignore_permissions=True)
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
	dn = make_delivery_note(so.name)
	dn.remarks = marker + "；回原订单计划送货10件，来源生产入库草稿：" + manufacture.name
	dn.insert(ignore_permissions=True)
	result = describe(so.name)
	for dt, name in (("Stock Entry", transfer.name), ("Stock Entry", returned.name),
		("Stock Entry", manufacture.name), ("Delivery Note", dn.name)):
		assert frappe.db.get_value(dt, name, "docstatus") == 0
		assert not frappe.db.exists("Stock Ledger Entry", {"voucher_type": dt, "voucher_no": name})
		assert not frappe.db.exists("GL Entry", {"voucher_type": dt, "voucher_no": name})
	frappe.db.commit()
	return result


def describe(sales_order):
	wo = frappe.db.get_value("Work Order", {"sales_order": sales_order}, "name")
	return {"sales_order": sales_order, "work_order": wo,
		"work_order_details": frappe.db.get_value("Work Order", wo,
			["bom_no", "qty", "produced_qty", "status"], as_dict=True),
		"job_cards": frappe.get_all("Job Card", {"work_order": wo}, ["name", "docstatus", "total_completed_qty", "status"]),
		"quality": frappe.get_all("Quality Inspection", {"custom_work_order": wo},
			["name", "docstatus", "custom_inspection_qty", "custom_accepted_qty"]),
		"stock_drafts": frappe.get_all("Stock Entry", {"work_order": wo},
			["name", "purpose", "docstatus", "fg_completed_qty"]),
		"delivery": frappe.get_all("Delivery Note Item", {"against_sales_order": sales_order},
			["parent", "qty", "docstatus"])}


def create_invoice_draft():
	"""Link a non-posting invoice draft to the demo order and delivery draft."""
	so = frappe.get_doc("Sales Order", "SAL-ORD-2026-00022")
	dn = frappe.get_doc("Delivery Note", "MAT-DN-2026-00051")
	marker = "生产演示销售发票核对-20261028"
	existing = frappe.db.get_value("Sales Invoice", {"remarks": marker, "docstatus": 0}, "name")
	if existing:
		doc = frappe.get_doc("Sales Invoice", existing)
	else:
		row = dn.items[0]
		assert row.against_sales_order == so.name
		doc = frappe.get_doc({"doctype": "Sales Invoice", "company": so.company,
			"customer": so.customer, "currency": so.currency, "posting_date": today(),
			"due_date": add_days(today(), 30), "update_stock": 0, "remarks": marker,
			"items": [{"item_code": row.item_code, "qty": row.qty, "rate": row.rate,
			"uom": row.uom, "warehouse": row.warehouse, "sales_order": so.name,
			"so_detail": row.so_detail, "delivery_note": dn.name, "dn_detail": row.name}]})
		doc.insert(ignore_permissions=True)
	assert doc.docstatus == 0 and doc.company == so.company and doc.customer == so.customer
	assert doc.items[0].qty == 10 and doc.items[0].rate == 200
	assert not frappe.db.exists("GL Entry", {"voucher_type": doc.doctype, "voucher_no": doc.name})
	assert not frappe.db.exists("Stock Ledger Entry", {"voucher_type": doc.doctype, "voucher_no": doc.name})
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status,
		"customer": doc.customer, "company": doc.company, "qty": doc.items[0].qty,
		"rate": doc.items[0].rate, "net_total": doc.net_total,
		"tax": doc.total_taxes_and_charges, "grand_total": doc.grand_total,
		"sales_order": doc.items[0].sales_order, "delivery_note": doc.items[0].delivery_note}
