"""Opt-in direct-component manufacturing and shortage sourcing.

All inventory mutations remain standard ERPNext documents. No ledger writes.
"""
import math

import frappe
from frappe.utils import cint, flt, nowdate


def ensure_schema():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "Company": [dict(fieldname="custom_enable_layered_manufacturing", label="允许分层组装", fieldtype="Check", insert_after="default_currency")],
        "Item": [dict(fieldname="custom_supply_mode", label="半成品/物料供应方式", fieldtype="Select", options="\n外购\n自制\n可外购/可自制", insert_after="item_group",
            description="生产领料缺料时，外购默认采购，自制默认勾选发起生产工单；可外购/可自制默认采购。直接组件模式下可在缺料弹窗调整。")],
        "BOM": [dict(fieldname="custom_default_create_work_order_on_shortage", label="缺料时默认发起生产工单", fieldtype="Check", default="0", hidden=1, insert_after="quantity",
            description="该 BOM 作为子 BOM 缺料时，生产领料缺料弹窗默认勾选发起生产工单；未勾选默认发起采购申请。")],
        "Work Order": [
            dict(fieldname="custom_direct_component_supply", label="一级组件补料模式", fieldtype="Check", insert_after="custom_layered_mode"),
            dict(fieldname="custom_layered_mode", label="分层组装", fieldtype="Check", insert_after="use_multi_level_bom"),
            dict(fieldname="custom_root_work_order", label="根生产工单", fieldtype="Link", options="Work Order", read_only=1, insert_after="custom_layered_mode"),
            dict(fieldname="custom_parent_work_order", label="上层生产工单", fieldtype="Link", options="Work Order", read_only=1, insert_after="custom_root_work_order"),
        ],
        "Material Request": [dict(fieldname="custom_layered_work_order", label="分层补料来源工单", fieldtype="Link", options="Work Order", read_only=1, insert_after="material_request_type")],
    }, update=True)
    if not frappe.db.exists("DocType", "Layered Supply Allocation"):
        frappe.get_doc(dict(doctype="DocType", name="Layered Supply Allocation", module="Client Akivision", custom=1,
            autoname="hash", track_changes=1,
            fields=[
                dict(fieldname="work_order", label="来源工单", fieldtype="Link", options="Work Order", reqd=1),
                dict(fieldname="item_code", label="物料", fieldtype="Link", options="Item", reqd=1),
                dict(fieldname="warehouse", label="需求仓库", fieldtype="Link", options="Warehouse", reqd=1),
                dict(fieldname="supply_type", label="供应方式", fieldtype="Select", options="Purchase\nManufacture", reqd=1),
                dict(fieldname="qty", label="分配数量（库存单位）", fieldtype="Float", reqd=1),
                dict(fieldname="reference_doctype", label="关联类型", fieldtype="Link", options="DocType", reqd=1),
                dict(fieldname="reference_name", label="关联单据", fieldtype="Dynamic Link", options="reference_doctype", reqd=1),
            ], permissions=[dict(role="System Manager", read=1, report=1), dict(role="Manufacturing User", read=1), dict(role="Manufacturing Manager", read=1)]
        )).insert()


def is_layered(work_order):
    return bool(work_order and frappe.db.get_value("Work Order", work_order, "custom_layered_mode"))


def initialize_direct_component_work_order(doc, method=None):
    """Only opt new orders into the company-enabled flow; never rewrite history."""
    if doc.is_new() and not doc.get("track_semi_finished_goods") and not doc.get("custom_layered_mode"):
        if frappe.db.get_value("Company", doc.company, "custom_enable_layered_manufacturing"):
            doc.custom_direct_component_supply = 1
    if not doc.get("custom_direct_component_supply"):
        return
    previous = doc.get_doc_before_save()
    if previous and previous.docstatus == 1:
        return
    if previous and not previous.get("custom_direct_component_supply"):
        if frappe.db.exists("Stock Entry", {"work_order": doc.name, "docstatus": 1}):
            frappe.throw("已发生库存操作的工单不能切换一级组件补料模式")
    if not frappe.db.get_value("Company", doc.company, "custom_enable_layered_manufacturing"):
        frappe.throw("请先在公司启用允许分层组装")
    switching = doc.use_multi_level_bom or not previous or not previous.get("custom_direct_component_supply")
    doc.custom_layered_mode = 1
    doc.use_multi_level_bom = 0
    if switching and doc.bom_no and doc.qty:
        doc.set_required_items()


def validate_work_order(doc, method=None):
    previous = doc.get_doc_before_save()
    if previous and previous.docstatus == 1 and cint(previous.get("custom_direct_component_supply")) != cint(doc.get("custom_direct_component_supply")):
        frappe.throw("已提交工单不能切换一级组件补料模式")
    if doc.get("custom_direct_component_supply") and (not doc.get("custom_layered_mode") or doc.use_multi_level_bom):
        frappe.throw("一级组件补料模式必须使用分层组装且关闭多层 BOM 展开")
    if previous and previous.docstatus == 1 and cint(previous.get("custom_layered_mode")) != cint(doc.get("custom_layered_mode")):
        frappe.throw("已提交工单不能切换分层组装模式")
    if not doc.get("custom_layered_mode"):
        return
    if (not previous or not previous.get("custom_layered_mode")) and not frappe.db.get_value("Company", doc.company, "custom_enable_layered_manufacturing"):
        frappe.throw("请先在公司启用允许分层组装")
    if doc.track_semi_finished_goods:
        frappe.throw("分层组装不能与工序半成品跟踪同时启用")
    if doc.use_multi_level_bom:
        frappe.throw("分层组装必须关闭多层 BOM 展开，按直接组件领料")
    if doc.get("custom_parent_work_order") and doc.sales_order:
        frappe.throw("分层子工单通过根工单追溯销售订单，不能重复关联销售订单归集成本")
    if previous and not previous.get("custom_layered_mode") and frappe.db.exists("Stock Entry", {"work_order": doc.name, "docstatus": 1}):
        frappe.throw("已执行库存操作的工单不能转为分层组装")


def validate_stock_entry(doc, method=None):
    if is_layered(doc.get("work_order")) and doc.get("use_multi_level_bom"):
        frappe.throw("分层组装库存单不能展开下层 BOM")
    if not is_layered(doc.get("work_order")) or doc.purpose != "Manufacture" or not doc.get("inspection_required"):
        return
    inspection = doc.get("custom_quality_inspection")
    if not inspection:
        frappe.throw("此分层工单要求完工质检，请选择已提交的完工质检单")
    qi = frappe.get_doc("Quality Inspection", inspection)
    if qi.docstatus != 1 or qi.status != "Accepted" or qi.get("custom_work_order") != doc.work_order:
        frappe.throw("完工质检必须是当前工单已提交的合格质检")
    frappe.db.sql("select name from `tabQuality Inspection` where name=%s for update", qi.name)
    used = frappe.db.sql("""select coalesce(sum(fg_completed_qty),0) from `tabStock Entry`
        where docstatus=1 and purpose='Manufacture' and custom_quality_inspection=%s and name!=%s""", (qi.name, doc.name))[0][0]
    if flt(used) + flt(doc.fg_completed_qty) > flt(qi.get("custom_accepted_qty")) + 1e-6:
        frappe.throw("本次生产入库超过该质检单剩余合格数量")


def before_submit_stock_entry(doc, method=None):
    if not is_layered(doc.get("work_order")) or doc.purpose not in ("Material Transfer for Manufacture", "Material Issue"):
        return
    wo = frappe.get_doc("Work Order", doc.work_order)
    rows = _shortages(doc, wo)
    if rows:
        frappe.throw("库存不足，请在缺料列表安排补料或调整本批领料数量", title="库存不足")


def _pending(work_order, item, warehouse):
    pending, links = 0.0, []
    for row in frappe.get_all("Layered Supply Allocation", filters=dict(work_order=work_order, item_code=item, warehouse=warehouse), fields=["qty", "reference_doctype", "reference_name"]):
        ref = frappe.get_doc(row.reference_doctype, row.reference_name)
        if ref.docstatus == 2:
            continue
        if ref.doctype == "Work Order":
            remaining = 0 if ref.status in ("Closed", "Stopped", "Completed") else max(min(row.qty, flt(ref.qty)) - flt(ref.produced_qty) - flt(ref.process_loss_qty), 0)
        else:
            # Ordered is not received: outstanding purchased quantity remains
            # allocated until a submitted receipt is posted or the request closes.
            received = frappe.db.sql("""select coalesce(sum(pri.stock_qty),0)
                from `tabPurchase Receipt Item` pri join `tabPurchase Receipt` pr on pr.name=pri.parent
                where pr.docstatus=1 and pri.material_request=%s and pri.item_code=%s""", (ref.name, item))[0][0]
            # Consolidated purchasing can retain MR provenance in allocations
            # instead of the native receipt row link. Apportion received stock
            # by its PO source share without counting native-linked rows twice.
            if frappe.db.exists("DocType", "Purchase Order Source Allocation"):
                sources = frappe.db.sql("""select a.parent, a.qty, a.purchase_order_item,
                    (select sum(b.qty) from `tabPurchase Order Source Allocation` b
                        where b.parent=a.parent and b.purchase_order_item=a.purchase_order_item) total
                    from `tabPurchase Order Source Allocation` a join `tabPurchase Order` po on po.name=a.parent
                    join `tabPurchase Order Item` poi on poi.name=a.purchase_order_item
                    where po.docstatus=1 and a.material_request=%s and poi.item_code=%s""", (ref.name, item), as_dict=True)
                for source in sources:
                    consolidated = frappe.db.sql("""select coalesce(sum(pri.stock_qty),0)
                        from `tabPurchase Receipt Item` pri join `tabPurchase Receipt` pr on pr.name=pri.parent
                        where pr.docstatus=1 and pri.purchase_order_item=%s and pri.item_code=%s
                        and ifnull(pri.material_request,'')=''""", (source.purchase_order_item, item))[0][0]
                    if flt(source.total):
                        received += flt(consolidated) * flt(source.qty) / flt(source.total)
            remaining = 0 if ref.status in ("Stopped", "Cancelled") else max(min(row.qty, sum(flt(x.stock_qty) for x in ref.items if x.item_code == item)) - flt(received), 0)
        pending += remaining
        links.append(dict(doctype=ref.doctype, name=ref.name, pending_qty=remaining))
    return pending, links


def _entry(entry):
    data = frappe.parse_json(entry) if isinstance(entry, str) else entry
    doc = frappe.get_doc(data)
    if doc.doctype != "Stock Entry" or doc.docstatus != 0 or doc.purpose not in ("Material Transfer for Manufacture", "Material Issue") or not doc.work_order:
        frappe.throw("仅支持关联生产工单的未提交生产领料单")
    wo = frappe.get_doc("Work Order", doc.work_order)
    wo.check_permission("read")
    if not frappe.has_permission("Stock Entry", "create"):
        frappe.throw("没有创建生产领料单的权限", frappe.PermissionError)
    if not wo.get("custom_layered_mode") or wo.docstatus != 1 or wo.status in ("Closed", "Stopped", "Completed"):
        frappe.throw("来源工单必须是有效的已提交分层组装工单")
    if doc.company != wo.company:
        frappe.throw("领料单与工单公司不一致")
    return doc, wo


def _shortages(doc, wo):
    from erpnext.stock.utils import get_stock_balance
    grouped = {}
    allowed = {r.item_code for r in wo.required_items}
    for r in doc.items:
        if not r.s_warehouse or not r.item_code:
            continue
        if r.item_code not in allowed:
            frappe.throw("领料物料不在工单直接组件中")
        if frappe.db.get_value("Warehouse", r.s_warehouse, "company") != wo.company:
            frappe.throw("发料仓库公司不匹配")
        key = (r.item_code, r.s_warehouse)
        qty = flt(r.qty) * (flt(r.conversion_factor) or 1)
        if qty <= 0 or not math.isfinite(qty):
            frappe.throw("领料数量必须为有效正数")
        grouped[key] = grouped.get(key, 0) + qty
    rows = []
    for (item, warehouse), required in grouped.items():
        limit = sum(flt(r.required_qty) for r in wo.required_items if r.item_code == item)
        if required > limit + 1e-6:
            frappe.throw("本次领料数量超过工单需求")
        available = max(flt(get_stock_balance(item, warehouse, doc.posting_date, doc.posting_time)), 0)
        reserved = frappe.db.sql("""select coalesce(sum(greatest(reserved_qty-delivered_qty-consumed_qty,0)),0)
            from `tabStock Reservation Entry` where docstatus=1 and item_code=%s and warehouse=%s
            and not (voucher_type='Work Order' and voucher_no=%s)""", (item, warehouse, wo.name))[0][0]
        available = max(available - flt(reserved), 0)
        shortage = max(required - available, 0)
        if shortage <= 1e-6:
            continue
        pending, links = _pending(wo.name, item, warehouse)
        info = frappe.db.get_value("Item", item, ["item_name", "stock_uom", "custom_supply_mode", "default_bom", "is_purchase_item"], as_dict=True)
        bom = info.default_bom
        parent_bom = frappe.get_cached_doc("BOM", wo.bom_no) if wo.get("bom_no") else None
        linked = {r.bom_no for r in parent_bom.items if r.item_code == item and r.bom_no} if parent_bom else set()
        if len(linked) > 1:
            frappe.throw("同一物料关联多个子 BOM，请先明确生产版本")
        if linked:
            bom = next(iter(linked))
        if not bom or not frappe.db.exists("BOM", dict(name=bom, item=item, docstatus=1, is_active=1)):
            bom = None
        rows.append(dict(item_code=item, warehouse=warehouse, required_qty=required, available_qty=available,
            shortage_qty=shortage, pending_qty=pending, allocatable_qty=max(shortage-pending, 0),
            item_name=info.item_name, stock_uom=info.stock_uom, supply_mode=info.custom_supply_mode,
            bom_no=bom, is_purchase_item=info.is_purchase_item, links=links))
    return rows


@frappe.whitelist()
def get_shortage_details(entry):
    doc, wo = _entry(entry)
    return dict(work_order=wo.name, rows=_shortages(doc, wo), direct_component_supply=bool(wo.get("custom_direct_component_supply")))


def _get_item_shortage_default(row):
    """Item sourcing is a preference in direct mode, not a capability check."""
    mode = row.get("supply_mode") or "外购"
    return dict(
        default_create_work_order=bool(mode == "自制" and row.get("bom_no")),
        supply_mode=mode,
        default_source="item_supply_mode",
        default_block_reason="missing_manufacturing_bom" if mode == "自制" and not row.get("bom_no") else "",
    )


@frappe.whitelist()
def get_direct_component_shortage_defaults(entry):
    """Return Item-controlled defaults using server-resolved component BOMs."""
    doc, wo = _entry(entry)
    if not wo.get("custom_direct_component_supply"):
        return dict(rows=[])
    rows = []
    for row in _shortages(doc, wo):
        rows.append(dict(
            item_code=row["item_code"],
            warehouse=row["warehouse"],
            **_get_item_shortage_default(row),
        ))
    return dict(rows=rows)


@frappe.whitelist()
def allocate_shortage(entry, selections):
    doc, wo = _entry(entry)
    if wo.get("custom_direct_component_supply"):
        frappe.throw("一级组件补料模式请使用采购／自产二选一接口")
    return _allocate_shortage(doc, wo, selections)


def _allocate_shortage(doc, wo, selections, enforce_supply_mode=True):
    # Serialize all allocations against this source, including repeated clicks.
    frappe.db.sql("select name from `tabWork Order` where name=%s for update", wo.name)
    rows = {(r["item_code"], r["warehouse"]): r for r in _shortages(doc, wo)}
    selected = frappe.parse_json(selections) if isinstance(selections, str) else selections
    created, seen = [], set()
    for choice in selected:
        key = (choice.get("item_code"), choice.get("warehouse"))
        if key in seen or key not in rows:
            frappe.throw("缺料明细重复或已变化，请重新检查")
        seen.add(key)
        row = rows[key]
        purchase, manufacture = flt(choice.get("purchase_qty")), flt(choice.get("manufacture_qty"))
        if not all(math.isfinite(x) and x >= 0 for x in (purchase, manufacture)) or purchase + manufacture > row["allocatable_qty"] + 1e-6:
            frappe.throw("采购与自产合计不能超过待安排缺口")
        mode = row["supply_mode"]
        if purchase and (not row["is_purchase_item"] or (enforce_supply_mode and mode not in ("外购", "可外购/可自制"))):
            frappe.throw("该物料不允许外购，请维护供应方式和采购许可")
        if manufacture and (not row["bom_no"] or (enforce_supply_mode and mode not in ("自制", "可外购/可自制"))):
            frappe.throw("该物料不允许自产或缺少有效默认 BOM")
        if purchase:
            mr = frappe.new_doc("Material Request")
            mr.update(dict(company=wo.company, material_request_type="Purchase", transaction_date=nowdate(), schedule_date=nowdate(), custom_layered_work_order=wo.name))
            for fieldname, value in {
                "custom_production_shortage_request": 1,
                "custom_shortage_source_work_order": wo.name,
                "custom_shortage_source_sales_order": wo.sales_order,
                "custom_purchase_scene": "常规采购",
            }.items():
                if mr.meta.has_field(fieldname):
                    mr.set(fieldname, value)
            mr.append("items", dict(item_code=key[0], qty=purchase, uom=row["stock_uom"], stock_uom=row["stock_uom"], conversion_factor=1, warehouse=key[1], schedule_date=nowdate()))
            if mr.meta.has_field("custom_shortage_source_allocations"):
                mr.append("custom_shortage_source_allocations", dict(source_doctype="Work Order", source_name=wo.name,
                    work_order=wo.name, item_code=key[0], warehouse=key[1], qty=purchase))
            mr.insert()
            created.append(_allocation(wo, row, purchase, "Purchase", mr))
        if manufacture:
            from erpnext.manufacturing.doctype.work_order.work_order import make_work_order
            child = make_work_order(row["bom_no"], key[0], qty=manufacture, company=wo.company, project=wo.project, use_multi_level_bom=0)
            child.update(dict(custom_layered_mode=1, custom_root_work_order=wo.get("custom_root_work_order") or wo.name,
                custom_direct_component_supply=cint(wo.get("custom_direct_component_supply")),
                custom_parent_work_order=wo.name, fg_warehouse=key[1], wip_warehouse=wo.wip_warehouse, source_warehouse=wo.source_warehouse))
            child.insert()
            created.append(_allocation(wo, row, manufacture, "Manufacture", child))
    return dict(created=created)


@frappe.whitelist()
def allocate_direct_component_shortage(entry, decisions):
    doc, wo = _entry(entry)
    if not wo.get("custom_direct_component_supply"):
        frappe.throw("来源工单未启用一级组件补料模式")
    frappe.db.sql("select name from `tabWork Order` where name=%s for update", wo.name)
    rows = {(r["item_code"], r["warehouse"]): r for r in _shortages(doc, wo)}
    decisions = frappe.parse_json(decisions) if isinstance(decisions, str) else decisions
    if not isinstance(decisions, list):
        frappe.throw("缺料处理选择必须为列表")
    selected, existing, seen = [], [], set()
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("create_work_order") not in (True, False, 0, 1):
            frappe.throw("请明确选择是否发起生产工单")
        key = (decision.get("item_code"), decision.get("warehouse"))
        if key in seen:
            frappe.throw("缺料明细重复，请重新检查")
        seen.add(key)
        if key not in rows:
            continue  # Stock arrived since the dialog opened.
        row = rows[key]
        qty = row["allocatable_qty"]
        if qty <= 1e-6:
            existing.extend(row["links"])
            continue
        manufacture = bool(decision["create_work_order"])
        requested_type = "Manufacture" if manufacture else "Purchase"
        active_types = {
            "Manufacture" if link.get("doctype") == "Work Order" else "Purchase"
            for link in row["links"] if flt(link.get("pending_qty")) > 1e-6
        }
        if active_types and requested_type not in active_types:
            current = "生产工单" if "Manufacture" in active_types else "采购申请"
            frappe.throw(f"该缺口已通过{current}安排，请先取消原补料单据后再切换方式：{key[0]}")
        if manufacture:
            if not row["bom_no"]:
                frappe.throw("该物料缺少有效子 BOM，无法发起生产工单：" + key[0])
            bom = frappe.get_doc("BOM", row["bom_no"])
            bom.check_permission("read")
            if bom.company and bom.company != wo.company:
                frappe.throw("子 BOM 公司与来源工单不一致")
            if not frappe.has_permission("Work Order", "create"):
                frappe.throw("没有创建生产工单的权限", frappe.PermissionError)
        else:
            if not row["is_purchase_item"]:
                frappe.throw("该物料未启用采购许可，无法发起采购申请：" + key[0])
            if not frappe.has_permission("Material Request", "create"):
                frappe.throw("没有创建采购申请的权限", frappe.PermissionError)
        selected.append(dict(item_code=key[0], warehouse=key[1],
            manufacture_qty=qty if manufacture else 0, purchase_qty=0 if manufacture else qty))
    # Validate the whole selection before any writes. Roll back all drafts if a
    # downstream controller fails, even when this method is used internally.
    frappe.db.savepoint("direct_component_supply")
    try:
        # In direct-component mode the checkbox itself is the explicit routing
        # decision: valid child BOM = manufacture, unchecked = purchase.
        result = _allocate_shortage(doc, wo, selected, enforce_supply_mode=False)
    except Exception:
        frappe.db.rollback(save_point="direct_component_supply")
        raise
    result.update(existing=existing, rows=_shortages(doc, wo))
    return result


@frappe.whitelist()
def get_work_order_component_tree(work_order):
    """Read-only BOM paths; never replace the actual material requirements."""
    wo = frappe.get_doc("Work Order", work_order)
    wo.check_permission("read")
    rows = []

    def visit(bom_name, required_qty, ancestors, parent_path="", depth=1):
        if bom_name in ancestors or depth > 20:
            frappe.throw("BOM 存在循环引用或层级超过 20 层")
        bom = frappe.get_doc("BOM", bom_name)
        bom.check_permission("read")
        if bom.docstatus != 1 or not bom.is_active or (bom.company and bom.company != wo.company):
            frappe.throw("BOM 未启用、未提交或公司不匹配：" + bom_name)
        if flt(bom.quantity) <= 0:
            frappe.throw("BOM 产出数量必须大于零")
        factor = flt(required_qty) / flt(bom.quantity)
        for item in bom.items:
            path = f"{parent_path}/{item.idx}"
            qty = flt(item.stock_qty) if item.get("stock_qty") is not None else flt(item.qty) * (flt(item.conversion_factor) or 1)
            rows.append(dict(path=path, parent_path=parent_path, depth=depth,
                item_code=item.item_code, item_name=item.item_name, bom_no=item.bom_no,
                stock_uom=item.stock_uom, required_qty=qty * factor))
            if len(rows) > 5000:
                frappe.throw("BOM 展开超过 5000 行，请缩小查看范围")
            if item.bom_no:
                child_item = frappe.db.get_value("BOM", item.bom_no, "item")
                if child_item != item.item_code:
                    frappe.throw("子 BOM 与组件物料不匹配")
                visit(item.bom_no, qty * factor, ancestors | {bom_name}, path, depth + 1)

    if wo.bom_no:
        visit(wo.bom_no, wo.qty, set())
    return dict(work_order=wo.name, rows=rows)


def _allocation(wo, row, qty, supply_type, reference):
    # Internal record creation only after standard document permission checks.
    frappe.get_doc(dict(doctype="Layered Supply Allocation", work_order=wo.name, item_code=row["item_code"], warehouse=row["warehouse"],
        qty=qty, supply_type=supply_type, reference_doctype=reference.doctype, reference_name=reference.name)).insert(ignore_permissions=True)
    return dict(doctype=reference.doctype, name=reference.name, qty=qty, item_code=row["item_code"])
