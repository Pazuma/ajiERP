"""Cost data is available only to internal costing users and source readers."""
import json

import frappe

ROLES = {"System Manager", "Accounts Manager", "Accounts User"}
APPROVERS = {"System Manager", "Accounts Manager"}


def require_cost_user():
    if frappe.session.user == "Guest" or not ROLES.intersection(frappe.get_roles()):
        frappe.throw("仅内部成本核算人员可访问", frappe.PermissionError)


def read_source(doctype, name, company=None):
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    if company and doc.get("company") and doc.company != company:
        frappe.throw("不允许跨公司引用成本来源")
    return doc


def check_sources(doc):
    require_cost_user()
    if doc.company:
        read_source("Company", doc.company)
    for dt, name in (("Item", doc.item_code), ("BOM", doc.bom_no), ("Project", doc.project),
                     ("Work Order", doc.reference_work_order)):
        if name:
            source = read_source(dt, name, doc.company)
            if dt == "BOM" and doc.item_code and source.item != doc.item_code:
                frappe.throw("BOM与报价产品不一致")
            if dt == "Work Order" and doc.item_code and source.production_item != doc.item_code:
                frappe.throw("生产工单与报价产品不一致")
    for row in doc.get("materials") or []:
        if row.item_code:
            read_source("Item", row.item_code)
        if row.supplier:
            read_source("Supplier", row.supplier)
    for row in doc.get("investments") or []:
        if row.project:
            project = read_source("Project", row.project, doc.company)
            from client_akivision.utils.project_permissions import require_project_finance
            require_project_finance()
            if project.meta.has_field("custom_project_cost_details") and not project.has_permlevel_access_to("custom_project_cost_details"):
                frappe.throw("缺少项目成本字段读取权限", frappe.PermissionError)
    for table in ("materials", "operations", "investments"):
        for row in doc.get(table) or []:
            if row.get("pricing_rule"):
                rule = read_source("Item Supplier Pricing Rule", row.pricing_rule, doc.company)
                if table == "materials" and (rule.item_code != row.item_code or rule.supplier != row.supplier):
                    frappe.throw("阶梯规则与报价行物料/供应商不一致")
            refs = json.loads(row.get("source_refs") or "[]")
            for ref in refs:
                if ref.get("doctype") not in ("BOM", "Project", "Timesheet", "Work Order"):
                    frappe.throw("无效来源类型")
                source = read_source(ref["doctype"], ref["name"], doc.company)
                if ref.get("row"):
                    expected_tables = {
                        "BOM": ("items", "operations"),
                        "Project": ("custom_project_cost_details", "custom_project_budget_details"),
                        "Timesheet": ("time_logs",),
                        "Work Order": ("required_items", "custom_labor_details"),
                    }[ref["doctype"]]
                    child = next((child for field in expected_tables if source.meta.has_field(field)
                                  for child in source.get(field) or [] if child.name == ref["row"]), None)
                    if not child:
                        frappe.throw("来源明细不属于来源单据")
                    if table == "materials" and ref["doctype"] == "BOM":
                        if not hasattr(child, "item_code") or child.item_code != row.item_code:
                            frappe.throw("BOM物料引用与报价物料不一致")
                    if ref["doctype"] == "Project" and row.get("project") and row.project != source.name:
                        frappe.throw("投入行项目与来源记录不一致")
                if ref["doctype"] in ("Project", "Timesheet"):
                    from client_akivision.utils.project_permissions import require_project_finance
                    require_project_finance()
                    cost_field = "custom_project_cost_details" if ref["doctype"] == "Project" else "total_costing_amount"
                    if source.meta.has_field(cost_field) and not source.has_permlevel_access_to(cost_field):
                        frappe.throw("缺少来源成本字段读取权限", frappe.PermissionError)


def has_permission(doc, ptype=None, user=None):
    # Sharing a cost document must not expose its embedded source snapshots.
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    if user == "Guest" or not roles.intersection(ROLES):
        return False
    if ptype in ("submit", "cancel", "amend") and not roles.intersection(APPROVERS):
        return False
    if ptype == "delete":
        return False
    if ptype not in (None, "read", "select", "print", "email", "report", "export", "create", "write", "submit", "cancel", "amend"):
        return False
    if ptype in (None, "read", "export", "print", "report", "email", "select") and doc and not doc.is_new():
        try:
            # Source permissions may have been revoked since confirmation.
            # Frappe calls this deny-only hook with the request user. If a
            # caller asks us to evaluate a different user, fail closed rather
            # than mutate the active request/session identity.
            if user != frappe.session.user:
                return False
            check_sources(doc)
        except (frappe.PermissionError, frappe.DoesNotExistError, ValueError, TypeError):
            return False
    # This hook is deny-only; role permissions remain the source of grants.
    return True
