"""Read business evidence without changing source documents or legacy references."""
import frappe
from frappe.utils import flt, now_datetime

MODE = "业务完成模式"


def reached(actual, expected, precision=6):
	return flt(actual, precision) >= flt(expected, precision)


def evaluate(doctype, name):
	if not frappe.db.exists(doctype, name):
		return {"complete": False, "summary": "来源单据不存在", "exception": "来源单据不存在"}
	doc = frappe.get_doc(doctype, name)
	result = {"doctype": doctype, "name": name, "complete": False, "summary": "", "exception": ""}
	if doc.docstatus != 1:
		result.update(summary="已取消" if doc.docstatus == 2 else "未提交", exception="关联单据已取消" if doc.docstatus == 2 else "")
		return result
	if doctype == "Sales Order":
		result["summary"] = f"送货 {flt(doc.per_delivered, 2)}%；开票 {flt(doc.per_billed, 2)}%"
		if doc.skip_delivery_note or not flt(doc.grand_total) or doc.status == "Closed":
			result["exception"] = "特殊销售路径，需管理员核实完成口径"
		else:
			result["complete"] = reached(doc.per_delivered, 100, doc.precision("per_delivered")) and reached(doc.per_billed, 100, doc.precision("per_billed"))
	elif doctype == "Work Order":
		from client_akivision.utils.work_order_completion import _receipt_rows
		rows = _receipt_rows(name)
		submitted = sum(flt(r.finished_qty) for r in rows if r.docstatus == 1)
		result["summary"] = f"{doc.status}；生产 {flt(doc.produced_qty)}/{flt(doc.qty)}；过程损耗 {flt(doc.process_loss_qty)}；入库 {submitted}"
		precision = doc.precision("produced_qty") or 6
		if flt(submitted - flt(doc.produced_qty), precision) != 0:
			result["exception"] = "工单与生产入库数量不同步"
		else:
			result["complete"] = doc.status == "Completed"
	elif doctype == "Purchase Order":
		result.update(evaluate_purchase(doc))
	else:
		result["summary"] = "单据已提交，待负责人确认"
	return result


def evaluate_purchase(doc):
	completed = 0
	lines = []
	exceptions = []
	for item in doc.items:
		if item.get("delivered_by_supplier") or not frappe.db.get_value("Item", item.item_code, "is_stock_item"):
			exceptions.append("含非库存或供应商直送行，需核实完成口径")
			continue
		# qty is accepted quantity, received_qty also includes rejected stock.
		accepted = 0
		for child, parent, field in (("Purchase Receipt Item", "Purchase Receipt", "purchase_order_item"), ("Purchase Invoice Item", "Purchase Invoice", "po_detail")):
			condition = " and p.update_stock=1" if parent == "Purchase Invoice" else ""
			if parent == "Purchase Receipt":
				condition += """ and not (p.is_return=1 and exists(select 1 from `tabPurchase Receipt Item` original
					where original.name=i.purchase_receipt_item and ifnull(original.rejected_warehouse,'')!=''
					and i.warehouse=original.rejected_warehouse))"""
			# An invoice linked to a receipt must not double-count the same stock.
			condition += " and ifnull(i.purchase_receipt, '')=''" if parent == "Purchase Invoice" else ""
			accepted += flt(frappe.db.sql(f"""select sum(i.qty * ifnull(nullif(i.conversion_factor,0),1))
				from `tab{child}` i join `tab{parent}` p on p.name=i.parent
				where i.`{field}`=%s and p.docstatus=1 {condition}""", item.name)[0][0])
		planned = flt(item.qty) * (flt(item.conversion_factor) or 1)
		precision = item.precision("stock_qty") or 6
		ok = reached(accepted, planned, precision)
		completed += int(ok)
		lines.append(f"行{item.idx} {item.item_code}：合格净入库 {flt(accepted, precision)}/{flt(planned, precision)} {item.stock_uom}")
	# Consolidated and historical single-line inspections are both supported.
	inspections = frappe.get_all("Quality Inspection", filters={"custom_purchase_order": doc.name, "docstatus": ["!=", 2]}, fields=["name", "docstatus", "status", "custom_inspection_qty", "custom_purchase_order_item"])
	quality = []
	for qi in inspections:
		rows = frappe.get_all("Purchase Quality Inspection Item", filters={"parent": qi.name}, fields=["name", "purchase_order_item", "inspection_qty", "accepted_qty", "rejected_qty"])
		quality.append(f"{qi.name}：{'草稿' if qi.docstatus == 0 else qi.status}；检验 {sum(flt(r.inspection_qty) for r in rows) or flt(qi.custom_inspection_qty)}；合格 {sum(flt(r.accepted_qty) for r in rows)}；不合格 {sum(flt(r.rejected_qty) for r in rows)}")
		if qi.docstatus == 0:
			exceptions.append("存在未提交质检")
		for quality_row in rows:
			if qi.docstatus != 1 or flt(quality_row.rejected_qty) <= 0:
				continue
			returned = flt(frappe.db.sql("""select sum(case when i.warehouse=original.rejected_warehouse
				then -i.qty else -ifnull(i.rejected_qty,0) end)
				from `tabPurchase Receipt Item` i join `tabPurchase Receipt` p on p.name=i.parent
				join `tabPurchase Receipt Item` original on original.name=i.purchase_receipt_item
				where p.docstatus=1 and p.is_return=1 and i.quality_inspection=%s and i.purchase_order_item=%s""", (qi.name, quality_row.purchase_order_item))[0][0])
			# Legacy accepted-only receipts use a non-stock quality return.
			returned += flt(frappe.db.sql("""select sum(i.qty) from `tabPurchase Quality Return Item` i
				join `tabPurchase Quality Return` p on p.name=i.parent where p.docstatus=1
				and ifnull(p.stock_return,'')='' and i.quality_inspection_item=%s""", quality_row.name)[0][0])
			if not reached(returned, quality_row.rejected_qty):
				exceptions.append("存在未退回的不合格数量")
	# Existing custom quality flow is mandatory for stock procurement. Verify
	# accepted receipt rows really have submitted inspection evidence.
	for row in frappe.db.sql("""select i.item_code, i.quality_inspection from `tabPurchase Receipt Item` i
		join `tabPurchase Receipt` p on p.name=i.parent where i.purchase_order=%s
		and p.docstatus=1 and p.is_return=0 and i.qty>0""", doc.name, as_dict=True):
		if frappe.db.get_value("Item", row.item_code, "inspection_required_before_purchase"):
			if not row.quality_inspection or frappe.db.get_value("Quality Inspection", row.quality_inspection, "docstatus") != 1:
				exceptions.append("必检入库缺少已提交质检证据")
	for row in frappe.db.sql("""select i.item_code, i.quality_inspection from `tabPurchase Invoice Item` i
		join `tabPurchase Invoice` p on p.name=i.parent where i.purchase_order=%s
		and p.docstatus=1 and p.update_stock=1 and p.is_return=0 and i.qty>0
		and ifnull(i.purchase_receipt,'')=''""", doc.name, as_dict=True):
		if frappe.db.get_value("Item", row.item_code, "inspection_required_before_purchase") and (not row.quality_inspection or frappe.db.get_value("Quality Inspection", row.quality_inspection, "docstatus") != 1):
			exceptions.append("直接开票入库缺少已提交质检证据")
	if doc.status == "Closed" and completed != len(doc.items):
		exceptions.append("采购少收关闭，需核实")
	return {"complete": bool(doc.items) and completed == len(doc.items) and not exceptions,
		"summary": f"合格入库完成 {completed}/{len(doc.items)} 行；质检 {len(inspections)} 单",
		"lines": lines, "quality": quality, "exception": "；".join(sorted(set(exceptions)))}


def refresh_project(project):
	from client_akivision.utils.project_progress import _persist_project_totals, _sync_row_duration
	# Serialize event workers and user actions on this project.
	frappe.db.sql("select name from `tabProject` where name=%s for update", project)
	doc = frappe.get_doc("Project", project)
	if doc.get("custom_progress_mode") != MODE:
		return
	blocked = False
	for row in sorted(doc.custom_project_progress_items, key=lambda r: r.idx):
		links = frappe.get_all("Project Progress Reference", filters={"project": project, "progress_item": row.name}, fields=["reference_doctype", "reference_name"])
		if not links and row.reference_doctype and row.reference_name:
			links = [frappe._dict(reference_doctype=row.reference_doctype, reference_name=row.reference_name)]
		details = [evaluate(link.reference_doctype, link.reference_name) for link in links]
		ready = bool(details) and all(d["complete"] for d in details)
		exception = "；".join(sorted({d["exception"] for d in details if d.get("exception")}))
		confirmed_documents = row.completion_source == "人工确认" and bool(links) and all(link.reference_doctype not in ("Purchase Order", "Work Order", "Sales Order") and frappe.db.get_value(link.reference_doctype, link.reference_name, "docstatus") == 1 for link in links)
		if row.status == "已完成" and row.completion_rule != "Manual" and not ready and not confirmed_documents:
			exception = exception or "完成后业务条件发生变化，请管理员核实或退回"
		values = {"business_summary": "；".join(f'{d.get("name", "")}：{d["summary"]}' for d in details) or ("手工事项" if row.completion_rule == "Manual" else "尚未关联单据"), "business_details": frappe.as_json(details), "business_exception": exception, "last_synced_on": now_datetime()}
		if ready and not blocked and not exception and row.status != "已完成" and doc.custom_project_stage == "进行中" and doc.status not in ("Completed", "Cancelled"):
			values.update(status="已完成", actual_completed_on=now_datetime(), completed_by=None, completion_source="业务自动完成")
			if not row.actual_started_on:
				values["actual_started_on"] = now_datetime()
			doc.add_comment("Info", f"节点 {row.subject} 业务自动完成；来源：" + ", ".join(d.get("name", "") for d in details))
		frappe.db.set_value("Project Progress Item", row.name, values, update_modified=False)
		row.update(values)
		_sync_row_duration(row, row.actual_completed_on if row.status == "已完成" else None)
		blocked = blocked or row.status != "已完成" or bool(exception)
	return _persist_project_totals(project)


def refresh_active_projects():
	for project in frappe.get_all("Project", filters={"custom_progress_mode": MODE, "is_active": "Yes"}, pluck="name"):
		try:
			refresh_project(project)
		except Exception:
			frappe.log_error(title="项目业务进度补偿失败", message=frappe.get_traceback())
