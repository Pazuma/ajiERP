"""Create a traceable, draft-only sales-to-invoice demonstration chain."""

import frappe
from frappe.utils import add_days, today


def _first(doctype, filters=None, order_by="modified asc"):
	return frappe.db.get_value(doctype, filters or {}, "name", order_by=order_by)


def _master(doctype, name, values):
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	doc = frappe.get_doc({"doctype": doctype, "name": name, **values})
	doc.insert(ignore_permissions=True)
	return doc


def create():
	company = _first("Company", {"name": "阿基视觉（东莞）"}) or _first("Company")
	if not company:
		frappe.throw("没有可用公司")
	currency = frappe.db.get_value("Company", company, "default_currency") or "CNY"
	warehouse = _first("Warehouse", {"company": company, "is_group": 0}, "name asc")
	item_group = _first("Item Group", {"is_group": 0}, "name asc")
	uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
	customer_group = _first("Customer Group", {"is_group": 0}, "name asc")
	territory = _first("Territory", {"is_group": 0}, "name asc")
	supplier_group = _first("Supplier Group", {"is_group": 0}, "name asc")
	if not all([warehouse, item_group, customer_group, territory, supplier_group]):
		frappe.throw("缺少客户组、供应商组、客户区域、物料组或仓库基础资料")

	stamp = "20261028"
	customer = _master("Customer", f"演示客户-{stamp}", {"customer_name": f"演示客户-{stamp}", "customer_group": customer_group, "territory": territory, "customer_type": "Company"})
	supplier = _master("Supplier", f"演示供应商-{stamp}", {"supplier_name": f"演示供应商-{stamp}", "supplier_group": supplier_group, "supplier_type": "Company"})
	item = _master("Item", f"演示物料-{stamp}", {"item_code": f"演示物料-{stamp}", "item_name": "演示采购补料物料", "item_group": item_group, "stock_uom": uom, "is_stock_item": 1, "is_sales_item": 1, "is_purchase_item": 1, "description": "销售到采购补料全流程演示物料"})
	# Safety stock/reorder rule: this only changes the item master; no stock transaction is posted.
	if not any(r.warehouse == warehouse for r in item.get("reorder_levels", [])):
		item.append("reorder_levels", {"warehouse": warehouse, "warehouse_reorder_level": 10, "warehouse_reorder_qty": 20, "material_request_type": "Purchase"})
		item.save(ignore_permissions=True)
	qty = 5
	date = add_days(today(), 7)

	so = frappe.get_doc({"doctype": "Sales Order", "customer": customer.name, "company": company, "transaction_date": today(), "delivery_date": date, "currency": currency, "items": [{"item_code": item.name, "qty": qty, "uom": uom, "delivery_date": date, "warehouse": warehouse, "rate": 100, "schedule_date": date}]})
	so.insert(ignore_permissions=True)
	so_item = so.items[0].name
	mr = frappe.get_doc({"doctype": "Material Request", "material_request_type": "Purchase", "company": company, "transaction_date": today(), "schedule_date": date, "set_warehouse": warehouse, "items": [{"item_code": item.name, "qty": 20, "schedule_date": date, "warehouse": warehouse, "uom": uom, "description": "来源：演示销售订单补料"}]})
	mr.insert(ignore_permissions=True)
	po = frappe.get_doc({"doctype": "Purchase Order", "supplier": supplier.name, "company": company, "transaction_date": today(), "schedule_date": date, "currency": currency, "items": [{"item_code": item.name, "qty": 20, "schedule_date": date, "warehouse": warehouse, "uom": uom, "rate": 60, "material_request": mr.name}]})
	po.insert(ignore_permissions=True)
	pr = frappe.get_doc({"doctype": "Purchase Receipt", "supplier": supplier.name, "company": company, "posting_date": today(), "currency": currency, "items": [{"item_code": item.name, "qty": 20, "received_qty": 20, "uom": uom, "stock_uom": uom, "conversion_factor": 1, "rate": 60, "warehouse": warehouse, "purchase_order": po.name, "purchase_order_item": po.items[0].name}]})
	pr.insert(ignore_permissions=True)
	dn = frappe.get_doc({"doctype": "Delivery Note", "customer": customer.name, "company": company, "posting_date": today(), "currency": currency, "items": [{"item_code": item.name, "qty": qty, "uom": uom, "stock_uom": uom, "conversion_factor": 1, "rate": 100, "warehouse": warehouse, "against_sales_order": so.name, "so_detail": so_item}]})
	dn.insert(ignore_permissions=True)
	si = frappe.get_doc({"doctype": "Sales Invoice", "customer": customer.name, "company": company, "posting_date": today(), "due_date": date, "currency": currency, "items": [{"item_code": item.name, "qty": qty, "uom": uom, "stock_uom": uom, "conversion_factor": 1, "rate": 100, "warehouse": warehouse, "sales_order": so.name, "so_detail": so_item, "delivery_note": dn.name, "dn_detail": dn.items[0].name}]})
	si.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"company": company, "customer": customer.name, "supplier": supplier.name, "item": item.name, "warehouse": warehouse, "safety_stock": {"reorder_level": 10, "reorder_qty": 20}, "drafts": {"sales_order": so.name, "material_request": mr.name, "purchase_order": po.name, "purchase_receipt": pr.name, "delivery_note": dn.name, "sales_invoice": si.name}}


def link_purchase_demand():
	"""Mark the existing demo Material Request as the visible purchase demand."""
	mr = frappe.get_doc("Material Request", "MAT-MR-2026-00219")
	mr.update({"title": "采购需求-演示销售订单补料", "custom_purchase_scene": "常规采购",
		"custom_production_shortage_request": 1, "custom_shortage_source_sales_order": "SAL-ORD-2026-00021",
		"custom_preferred_supplier": frappe.db.get_value("Supplier", {"supplier_name": "演示供应商-20261028"}, "name")})
	mr.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": mr.name, "status": mr.docstatus, "source_sales_order": mr.custom_shortage_source_sales_order,
		"supplier": mr.custom_preferred_supplier}


def create_comparison_draft():
	"""Create one idempotent demonstration comparison, without ordering or posting."""
	from frappe.utils import now_datetime
	from client_akivision.utils.purchase_comparison import _rebuild_supplier_summary

	marker = "演示供应商比价-20261028；价格为模拟数据，不代表供应商实际报价。"
	mr = frappe.get_doc("Material Request", "MAT-MR-2026-00219")
	existing = frappe.db.get_value("Purchase Comparison", {"material_request": mr.name, "remarks": marker}, "name")
	if existing:
		return {"name": existing, "already_exists": True}
	base = frappe.get_doc("Supplier", "AS00002")
	suppliers = [base]
	for label in ("乙", "丙"):
		name = f"演示比价供应商{label}-20261028"
		supplier_id = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
		if supplier_id:
			suppliers.append(frappe.get_doc("Supplier", supplier_id))
		else:
			supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": name,
				"supplier_group": base.supplier_group, "supplier_type": "Company"})
			supplier.insert(ignore_permissions=True)
			suppliers.append(supplier)
	doc = frappe.get_doc({"doctype": "Purchase Comparison", "naming_series": "PC-.YY.-.#####",
		"company": mr.company, "date": today(), "status": "Draft", "material_request": mr.name,
		"remarks": marker})
	for item in mr.items:
		doc.append("items", {"item_code": item.item_code, "item_name": item.item_name,
			"qty": item.qty, "uom": item.uom, "warehouse": item.warehouse, "material_request_item": item.name})
		for supplier, rate in zip(suppliers, (60, 58, 63)):
			doc.append("rows", {"selected": 0, "is_best_item": int(rate == 58),
				"item_code": item.item_code, "item_name": item.item_name, "material_request_item": item.name,
				"supplier": supplier.name, "supplier_name": supplier.supplier_name,
				"price_source": "演示模拟报价", "demanded_qty": item.qty, "recommended_qty": item.qty,
				"recommended_rate": rate, "recommended_total": item.qty * rate,
				"order_qty": item.qty, "order_total": item.qty * rate, "direct_total": item.qty * rate,
				"min_order_qty": 1, "quote_valid_till": add_days(today(), 30),
				"source_currency": frappe.db.get_value("Company", mr.company, "default_currency"),
				"calculated_at": now_datetime(), "note": "模拟价格，仅供流程演示；未勾选下单。"})
	_rebuild_supplier_summary(doc)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status,
		"material_request": doc.material_request, "items": len(doc.items),
		"quotes": [{"supplier": r.supplier, "rate": r.recommended_rate, "total": r.order_total} for r in doc.rows]}


def complete_comparison_price_sources():
	"""Provide reusable demo buying prices so normal recomparison also works."""
	from client_akivision.utils.purchase_comparison import run_comparison

	doc = frappe.get_doc("Purchase Comparison", "PC-26-00018")
	if "演示供应商比价-20261028" not in (doc.remarks or ""):
		frappe.throw("仅允许补齐指定演示单据")
	price_list = frappe.db.get_value("Price List", {"buying": 1, "enabled": 1, "currency": "CNY"}, "name")
	if not price_list:
		frappe.throw("缺少启用的人民币采购价目表")
	price_names = []
	for supplier, rate in (("AS00002", 60), ("AS00003", 58), ("AS00004", 63)):
		if "演示" not in (frappe.db.get_value("Supplier", supplier, "supplier_name") or ""):
			frappe.throw("仅允许使用演示供应商")
		for item in doc.items:
			filters = {"item_code": item.item_code, "supplier": supplier, "price_list": price_list}
			name = frappe.db.get_value("Item Price", filters, "name")
			if name:
				price = frappe.get_doc("Item Price", name)
			else:
				price = frappe.get_doc({"doctype": "Item Price", **filters})
			price.update({"price_list_rate": rate, "uom": item.uom, "valid_from": today(),
				"valid_upto": add_days(today(), 30), "note": "模拟供应商报价，仅供演示，不代表实际采购价格。"})
			price.save(ignore_permissions=True)
			price_names.append(price.name)
	unquoted = run_comparison(doc)
	# Keep the demonstration unselected: no downstream order is requested.
	for row in doc.rows:
		row.selected = 0
	doc.status = "Draft"
	doc.save(ignore_permissions=True)
	if len(doc.rows) != 3 or unquoted:
		frappe.throw("演示比价未生成完整三家结果")
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus,
		"price_sources": price_names, "unquoted_items": unquoted,
		"rows": [{"supplier": r.supplier, "rate": r.recommended_rate,
			"total": r.recommended_total, "price_source": r.price_source} for r in doc.rows]}


def create_receiving_demo_order():
	"""Stage the 100/96/4 receiving example without submitting any document."""
	marker = "收料质检入库演示-100到货96合格4不合格-20261028"
	existing = frappe.db.get_value("Purchase Order", {"remarks": marker, "docstatus": 0}, "name")
	if existing:
		return {"purchase_order": existing, "docstatus": 0, "already_exists": True}
	source = frappe.get_doc("Purchase Order", "PUR-ORD-2026-00049")
	warehouses = frappe.get_all("Warehouse", filters={"company": source.company, "is_group": 0,
		"disabled": 0}, pluck="name", order_by="name asc")
	warehouse = next((name for name in warehouses if any(word in name for word in ("Stores", "原材料", "原料"))), None)
	warehouse = warehouse or source.items[0].warehouse
	row = source.items[0]
	doc = frappe.get_doc({"doctype": "Purchase Order", "supplier": source.supplier,
		"company": source.company, "transaction_date": today(), "schedule_date": add_days(today(), 7),
		"currency": source.currency, "remarks": marker, "items": [{"item_code": row.item_code,
		"qty": 100, "rate": 60, "uom": row.uom, "warehouse": warehouse,
		"schedule_date": add_days(today(), 7), "description": "演示计划：到货100件，检验合格96件、不合格4件；合格部分入库，不合格部分待退。"}]})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"purchase_order": doc.name, "docstatus": doc.docstatus, "qty": doc.items[0].qty,
		"warehouse": warehouse, "total": doc.grand_total}


def create_rejected_return_draft():
	"""Create and verify the demo return without submitting stock documents."""
	from client_akivision.utils.purchase_quality_flow import create_purchase_return_from_quality

	qi_name = "MAT-QA-2026-00008"
	existing = frappe.db.get_value("Purchase Quality Return", {"quality_inspection": qi_name,
		"docstatus": 0}, "name")
	if existing:
		doc = frappe.get_doc("Purchase Quality Return", existing)
	else:
		doc = create_purchase_return_from_quality(qi_name, unified_return=1)
		doc.remarks = "演示：4件外观划伤待退；原采购入库尚未提交，仅保存退货草稿，不影响库存和财务账务。"
		doc.insert(ignore_permissions=True)
	frappe.db.savepoint("demo_return_guard")
	try:
		doc.submit()
	except frappe.ValidationError as exc:
		if "原采购入库单尚未提交" not in str(exc):
			raise
		blocked = str(exc)
	else:
		frappe.db.rollback(save_point="demo_return_guard")
		frappe.throw("提交限制验证失败")
	frappe.db.rollback(save_point="demo_return_guard")
	doc.reload()
	assert doc.docstatus == 0 and not doc.stock_return
	assert frappe.db.get_value("Purchase Receipt", doc.purchase_receipt, "docstatus") == 0
	# Verify duplicate reservation, over-quantity and standard stock-return guards.
	checks = {"submit_blocked": blocked}
	for label, qty in (("duplicate_blocked", 4), ("excess_qty_blocked", 5)):
		candidate = create_purchase_return_from_quality(qi_name, unified_return=1)
		candidate.items[0].qty = qty
		try:
			candidate.insert(ignore_permissions=True)
		except frappe.ValidationError as exc:
			checks[label] = str(exc)
		else:
			frappe.throw(f"{label} 验证失败")
	try:
		create_purchase_return_from_quality(qi_name)
	except frappe.ValidationError as exc:
		checks["stock_return_blocked"] = str(exc)
	else:
		frappe.throw("库存退货前置限制验证失败")
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status,
		"quality_inspection": qi_name, "purchase_receipt": doc.purchase_receipt,
		"qty": sum(row.qty for row in doc.items), "checks": checks}
