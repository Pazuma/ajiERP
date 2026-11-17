"""Production-shortage Material Request splitting and supplier-batched PO drafts."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, getdate, nowdate

from client_akivision.utils.purchase_order_draft import _make_item


def ensure_schema():
	create_custom_fields({
		"Material Request": [
			{"fieldname": "custom_production_shortage_request", "label": "生产缺料采购申请", "fieldtype": "Check", "default": "0", "read_only": 1, "insert_after": "material_request_type"},
			{"fieldname": "custom_shortage_source_work_order", "label": "来源生产工单", "fieldtype": "Link", "options": "Work Order", "read_only": 1, "insert_after": "custom_production_shortage_request"},
			{"fieldname": "custom_shortage_source_stock_entry", "label": "来源库存移动", "fieldtype": "Link", "options": "Stock Entry", "read_only": 1, "insert_after": "custom_shortage_source_work_order"},
			{"fieldname": "custom_shortage_source_item_row", "label": "来源库存移动明细", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_shortage_source_stock_entry"},
			{"fieldname": "custom_shortage_source_sales_order", "label": "来源销售订单", "fieldtype": "Link", "options": "Sales Order", "read_only": 1, "insert_after": "custom_shortage_source_item_row"},
			{"fieldname": "custom_shortage_source_allocations", "label": "缺料来源明细", "fieldtype": "Table", "options": "Material Request Source Detail", "insert_after": "custom_shortage_source_sales_order"},
		],
		"Purchase Order": [
			{"fieldname": "custom_supplier_consolidation", "label": "供应商汇总采购单", "fieldtype": "Check", "default": "0", "read_only": 1, "insert_after": "custom_material_request"},
			{"fieldname": "custom_source_allocations_section", "label": "采购需求来源分摊", "fieldtype": "Section Break", "insert_after": "supplier_warehouse"},
			{"fieldname": "custom_source_allocations", "label": "采购需求来源分摊", "fieldtype": "Table", "options": "Purchase Order Source Allocation", "insert_after": "custom_source_allocations_section"},
		],
	}, update=True)
	for doctype in ("Material Request", "Purchase Order", "Purchase Comparison Row"):
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


@frappe.whitelist()
def create_purchase_requests_for_shortages(source_doctype, source_name, shortages):
	"""Create one draft Purchase Material Request per shortage row."""
	if source_doctype not in ("Stock Entry", "Work Order"):
		frappe.throw(_("仅支持从生产工单或库存移动单发起缺料采购申请。"))
	if not frappe.has_permission(source_doctype, "read", source_name):
		frappe.throw(_("没有读取来源单据的权限。"), frappe.PermissionError)
	source = frappe.get_doc(source_doctype, source_name)
	if source.docstatus == 2:
		frappe.throw(_("已取消的来源单据不能发起采购申请。"))
	if source_doctype == "Stock Entry" and source.docstatus != 0:
		frappe.throw(_("只能从尚未提交的库存移动单发起缺料采购申请。"))
	if isinstance(shortages, str):
		shortages = frappe.parse_json(shortages)
	if not isinstance(shortages, list) or not shortages:
		frappe.throw(_("没有有效的缺料明细。"))
	if source_doctype == "Stock Entry":
		work_order = source.get("work_order")
		company = source.company
	else:
		work_order = source.name
		company = source.company
	created, failures = [], []
	for idx, shortage in enumerate(shortages, 1):
		frappe.db.savepoint(f"shortage_mr_{idx}")
		try:
			item_code = shortage.get("item_code")
			warehouse = shortage.get("warehouse")
			qty = flt(shortage.get("shortage_qty"))
			if not frappe.db.exists("Item", item_code) or not warehouse or qty <= 0:
				frappe.throw(_("缺料物料、仓库或数量无效。"))
			if not frappe.get_cached_value("Item", item_code, "is_stock_item"):
				frappe.throw(_("物料 {0} 不是库存物料。" ).format(item_code))
			if not frappe.has_permission("Material Request", "create"):
				frappe.throw(_("没有创建采购申请的权限。"), frappe.PermissionError)
			row_id = shortage.get("source_row") or ""
			if source_doctype == "Stock Entry":
				matching = next((row for row in source.items if row.name == row_id and row.item_code == item_code and row.s_warehouse == warehouse), None)
				if not matching or qty > flt(matching.qty) * flt(matching.conversion_factor or 1):
					frappe.throw(_("缺料明细与已保存的库存移动单不一致，请保存并刷新后重试。"))
				if flt(shortage.get("conversion_factor") or 1) != flt(matching.conversion_factor or 1):
					frappe.throw(_("缺料明细的单位换算已变化，请刷新后重试。"))
			else:
				matching = next((row for row in source.required_items if row.item_code == item_code), None)
				# Work Order required_qty is stored in stock UOM; the dialog may send
				# transaction-UOM quantities from an unsaved Stock Entry row.
				requested_stock_qty = qty * (flt(shortage.get("conversion_factor")) or 1)
				if not matching or requested_stock_qty > flt(matching.required_qty):
					frappe.throw(_("缺料物料或数量与生产工单不一致，请刷新后重试。"))
				row_id = ""
			existing = _find_open_shortage_request(source_name, item_code, warehouse, row_id)
			if existing:
				created.append({"item_code": item_code, "material_request": existing, "status": "existing"})
				continue
			mr = frappe.new_doc("Material Request")
			mr.update({"company": company, "material_request_type": "Purchase", "transaction_date": nowdate(), "schedule_date": getdate(shortage.get("schedule_date") or nowdate()), "custom_production_shortage_request": 1,
				"custom_shortage_source_work_order": work_order, "custom_shortage_source_stock_entry": source_name if source_doctype == "Stock Entry" else None,
				"custom_shortage_source_item_row": row_id, "custom_shortage_source_sales_order": frappe.db.get_value("Work Order", work_order, "sales_order") if work_order else None,
				"title": _("生产缺料采购申请-{0}").format(frappe.get_cached_value("Item", item_code, "item_name") or item_code)[:100]})
			mr.append("items", {"item_code": item_code, "qty": qty, "uom": shortage.get("uom") or frappe.db.get_value("Item", item_code, "stock_uom"),
				"stock_uom": shortage.get("stock_uom") or frappe.db.get_value("Item", item_code, "stock_uom"), "conversion_factor": flt(shortage.get("conversion_factor")) or 1,
				"warehouse": warehouse, "schedule_date": mr.schedule_date, "description": _("生产缺料，来源 {0}").format(source_name)})
			mr.insert()
			if mr.meta.has_field("custom_shortage_source_allocations"):
				mr.append("custom_shortage_source_allocations", {"source_doctype": source_doctype, "source_name": source_name, "source_row": row_id,
					"work_order": work_order, "item_code": item_code, "warehouse": warehouse, "qty": qty})
				mr.save()
			mr.db_set("custom_purchase_scene", "常规采购", update_modified=False) if mr.meta.has_field("custom_purchase_scene") else None
			created.append({"item_code": item_code, "material_request": mr.name, "status": "created"})
		except Exception as exc:
			frappe.db.rollback(save_point=f"shortage_mr_{idx}")
			failures.append({"item_code": shortage.get("item_code"), "error": str(exc)})
	return {"created": created, "failures": failures}


def _find_open_shortage_request(source_name, item_code, warehouse, source_row):
	rows = frappe.db.sql("""select mr.name from `tabMaterial Request` mr
		join `tabMaterial Request Item` mri on mri.parent=mr.name
		where mr.docstatus<2 and mr.custom_production_shortage_request=1
		and (mr.docstatus=0 or coalesce(mri.ordered_qty,0)<mri.stock_qty)
		and coalesce(mr.custom_shortage_source_stock_entry, mr.custom_shortage_source_work_order)=%s
		and mri.item_code=%s and mri.warehouse=%s
		and coalesce(mr.custom_shortage_source_item_row,'')=%s limit 1""", (source_name, item_code, warehouse, source_row), as_dict=True)
	return rows[0].name if rows else None


@frappe.whitelist()
def get_pending_sources(company=None, supplier=None):
	"""List selected, priced and not-yet-ordered shortage comparison rows."""
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("没有创建采购订单的权限。"), frappe.PermissionError)
	filters = ["mr.docstatus=1", "mr.custom_production_shortage_request=1", "mri.item_code is not null",
		"pc.docstatus < 2", "pcr.selected=1", "pcr.supplier is not null", "pcr.recommended_rate is not null"]
	values = {}
	for key in ("company",):
		if locals()[key]: filters.append(f"mr.{key}=%({key})s"); values[key] = locals()[key]
	if supplier: filters.append("pcr.supplier=%(supplier)s"); values["supplier"] = supplier
	rows = frappe.db.sql(f"""select mr.company, mr.name material_request, mri.name material_request_item,
		pc.name purchase_comparison, pcr.name comparison_row, pcr.supplier, pcr.supplier_name,
		mri.item_code, mri.item_name, mri.warehouse, mri.schedule_date, mri.stock_qty, mri.conversion_factor,
		coalesce(pcr.order_qty,pcr.recommended_qty,mri.qty) ordered_qty,
		pcr.recommended_rate rate, pcr.supplier_quotation, pcr.quote_valid_till, pcr.item_supplier_pricing_rule,
		mr.custom_shortage_source_work_order work_order,
		mr.custom_shortage_source_stock_entry source_stock_entry,
		coalesce((select sum(a.qty) from `tabPurchase Order Source Allocation` a
			join `tabPurchase Order` po on po.name=a.parent
			where a.material_request_item=mri.name and po.docstatus<2),0) ordered_source_qty
		from `tabMaterial Request` mr join `tabMaterial Request Item` mri on mri.parent=mr.name
		join `tabPurchase Comparison` pc on pc.material_request=mr.name and pc.docstatus<2
		join `tabPurchase Comparison Row` pcr on pcr.parent=pc.name and pcr.item_code=mri.item_code
		and (pcr.material_request_item=mri.name or (pcr.material_request_item is null and not exists (select 1 from `tabPurchase Comparison Row` pr2 where pr2.parent=pc.name and pr2.material_request_item is not null)))
		and not exists (select 1 from `tabPurchase Comparison` newer where newer.material_request=mr.name
			and newer.docstatus<2 and (newer.creation>pc.creation or (newer.creation=pc.creation and newer.name>pc.name)))
		where {' and '.join(filters)} order by pcr.supplier, mr.name""", values, as_dict=True)
	result = []
	for row in rows:
		if not frappe.has_permission("Material Request", "read", row.material_request):
			continue
		remaining = max(min(flt(row.ordered_qty), flt(row.stock_qty) / flt(row.conversion_factor or 1)) - flt(row.ordered_source_qty), 0)
		if remaining:
			row.available_qty = remaining
			result.append(row)
	return result


@frappe.whitelist()
def create_supplier_purchase_order(supplier, allocations):
	"""Create one draft PO per supplier/company/compatible currency and link source allocations."""
	if isinstance(allocations, str): allocations = frappe.parse_json(allocations)
	if not allocations: frappe.throw(_("请至少选择一条待下单需求。"))
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("没有创建采购订单的权限。"), frappe.PermissionError)
	if not isinstance(allocations, list) or any(not isinstance(row, dict) for row in allocations):
		frappe.throw(_("采购需求格式无效。"))
	comparison_rows = [row.get("comparison_row") for row in allocations]
	if any(not name for name in comparison_rows) or len(set(comparison_rows)) != len(comparison_rows):
		frappe.throw(_("同一采购需求不能重复选择。"))
	# Serialize orders for all affected requests before calculating the available quantities.
	requests = frappe.db.sql("""select distinct pc.material_request from `tabPurchase Comparison Row` pcr
		join `tabPurchase Comparison` pc on pc.name=pcr.parent where pcr.name in %(names)s""",
		{"names": tuple(comparison_rows)}, as_dict=True)
	if len(requests) != len(comparison_rows):
		frappe.throw(_("采购需求已变化，请刷新列表。"))
	for request_name in sorted(row.material_request for row in requests):
		frappe.db.sql("select name from `tabMaterial Request` where name=%s for update", request_name)
	all_rows = {row.comparison_row: row for row in get_pending_sources(supplier=supplier)}
	selected = []
	for allocation in allocations:
		row = all_rows.get(allocation.get("comparison_row"))
		if not row: frappe.throw(_("采购需求已变化或不属于所选供应商，请刷新列表。"))
		if not frappe.has_permission("Material Request", "read", row.material_request):
			frappe.throw(_("没有读取采购申请的权限。"), frappe.PermissionError)
		qty = flt(allocation.get("qty"))
		if qty <= 0 or qty > flt(row.available_qty): frappe.throw(_("{0} 下单数量无效或超过可下单数量。" ).format(row.item_code))
		if row.quote_valid_till and getdate(row.quote_valid_till) < getdate(nowdate()):
			frappe.throw(_("{0} 的供应商报价已过期，请重新比价。" ).format(row.item_code))
		if row.item_supplier_pricing_rule:
			from custom_filters.pricing_formula import evaluate_supplier_rule, get_active_rule
			rule = get_active_rule(row.item_code, supplier, row.company, nowdate())
			if not rule or rule.name != row.item_supplier_pricing_rule:
				frappe.throw(_("{0} 的供应商价格规则已变化，请重新比价。" ).format(row.item_code))
			verified = evaluate_supplier_rule(rule, qty)
			if abs(flt(verified["rate"]) - flt(row.rate)) > 0.000001 or abs(flt(verified["calculation_qty"]) - qty) > 0.000001:
				frappe.throw(_("{0} 当前公式价格或起订数量发生变化，请重新比价。" ).format(row.item_code))
		selected.append((row, qty))
	po_by_company = {}
	for row, qty in selected:
		company = row.company
		key = (company, row.supplier)
		if key not in po_by_company:
			existing = frappe.db.get_value("Purchase Order", {"supplier": supplier, "company": company, "docstatus": 0, "custom_supplier_consolidation": 1}, "name", order_by="creation desc")
			if existing:
				po_by_company[key] = frappe.get_doc("Purchase Order", existing)
				if not po_by_company[key].has_permission("write"):
					frappe.throw(_("没有修改采购订单 {0} 的权限。").format(existing), frappe.PermissionError)
			else:
				po = frappe.get_doc({"doctype":"Purchase Order", "supplier":supplier, "company":company, "transaction_date":nowdate(),
				"custom_preferred_supplier":supplier, "custom_supplier_consolidation":1})
				po_by_company[key] = po
		po = po_by_company[key]
		item = _make_item(row.item_code, qty, row.rate, company, row.material_request, row.material_request_item, row.warehouse, row.supplier_quotation)
		po_item = po.append("items", item)
		po_item.name = frappe.generate_hash(length=10)
		po.append("custom_source_allocations", {"material_request": row.material_request, "material_request_item": row.material_request_item,
			"purchase_order_item": po_item.name, "purchase_comparison": row.purchase_comparison, "work_order": row.work_order, "source_stock_entry": row.source_stock_entry, "qty": qty})
		# Save once after all chosen source rows have been appended.
	for po in po_by_company.values():
		if po.is_new(): po.insert()
		else: po.save()
	return [{"supplier": supplier, "company": key[0], "purchase_order": po.name} for key, po in po_by_company.items()]


def sync_purchase_order_sources(doc, method=None):
	"""Populate the source allocation ledger for every PO creation path."""
	# Carry the request category to the PO header for list/reporting purposes.
	if doc.meta.has_field("custom_excel_category") and not doc.get("custom_excel_category"):
		request_name = doc.get("custom_material_request") or next(
			(item.get("material_request") for item in doc.items if item.get("material_request")), None
		)
		if request_name and frappe.get_meta("Material Request").has_field("custom_excel_category"):
			doc.custom_excel_category = frappe.db.get_value("Material Request", request_name, "custom_excel_category")
	if not doc.meta.has_field("custom_source_allocations"):
		return
	# The custom consolidation flow already writes complete allocation rows.
	if doc.get("custom_source_allocations"):
		return
	for item in doc.items:
		material_request = item.get("material_request") or doc.get("custom_material_request")
		if not material_request:
			continue
		material_request_item = item.get("material_request_item")
		if not material_request_item:
			material_request_item = frappe.db.get_value(
				"Material Request Item",
				{"parent": material_request, "item_code": item.item_code},
				"name",
			)
		if not material_request_item:
			continue
		row = doc.append("custom_source_allocations", {
			"material_request": material_request,
			"material_request_item": material_request_item,
			"purchase_order_item": item.name,
			"qty": item.qty,
		})
		row.purchase_comparison = frappe.db.get_value(
			"Purchase Comparison", {"material_request": material_request, "docstatus": ("<", 2)}, "name"
		)
		row.work_order = frappe.db.get_value("Material Request", material_request, "custom_shortage_source_work_order")
		row.source_stock_entry = frappe.db.get_value("Material Request", material_request, "custom_shortage_source_stock_entry")


def backfill_purchase_order_source_allocations():
	"""Backfill allocation rows for existing purchase orders created from requests."""
	for name in frappe.get_all("Purchase Order", filters={"docstatus": ["<", 2]}, pluck="name"):
		po = frappe.get_doc("Purchase Order", name)
		if po.get("custom_source_allocations"):
			continue
		before = len(po.get("custom_source_allocations") or [])
		sync_purchase_order_sources(po)
		if len(po.get("custom_source_allocations") or []) > before:
			for row in po.custom_source_allocations[before:]:
				row.parent = po.name
				row.parenttype = "Purchase Order"
				row.parentfield = "custom_source_allocations"
				row.insert(ignore_permissions=True)
