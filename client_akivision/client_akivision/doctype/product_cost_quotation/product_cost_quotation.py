import hashlib
import json

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from client_akivision.utils.product_cost_calculation import calculate
from client_akivision.utils.product_cost_permissions import check_sources, read_source
from client_akivision.utils.product_cost_pricing import make_resolver


class ProductCostQuotation(Document):
    def validate(self):
        check_sources(self)
        previous = self.get_doc_before_save()
        context = json.loads(previous.get("source_context_json") or "{}") if previous else {}
        # Existing records acquire their original source context before a product change.
        for group in ("materials", "operations"):
            if group not in context:
                origin = previous or self
                if any(row.source_key for row in origin.get(group) or []):
                    context[group] = [origin.item_code or None, origin.bom_no or None]
        context.update(getattr(self.flags, "refreshed_source_context", {}) or {})
        self.source_context_json = frappe.as_json(context)
        if self.contact:
            contact = read_source("Contact", self.contact)
            if not self.customer or not any(r.link_doctype == "Customer" and r.link_name == self.customer for r in contact.links):
                frappe.throw("联系人未绑定当前客户")
        if self.customer:
            read_source("Customer", self.customer)
        if not self.item_code and not self.provisional_model:
            frappe.throw("产品编码与暂定型号至少填写一个")
        if flt(self.exchange_rate) <= 0:
            frappe.throw("请填写公司本币至报价币种汇率")
        base_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        if self.currency == base_currency and flt(self.exchange_rate) != 1:
            frappe.throw("报价币种为公司本币时，汇率须为1")
        if not self.product_name:
            self.product_name = frappe.get_cached_value("Item", self.item_code, "item_name") if self.item_code else self.provisional_model
        seen = set()
        table_labels = {
            "Product Cost Material": "材料明细",
            "Product Cost Operation": "制造工时",
            "Product Cost Investment": "项目投入",
        }
        for table in ("materials", "operations", "investments"):
            for row in self.get(table) or []:
                if row.source_key:
                    if row.source_key in seen:
                        frappe.throw("重复引用来源：" + row.source_key)
                    seen.add(row.source_key)
                if not row.source_refs and not row.manual_reason:
                    label = table_labels.get(row.doctype, row.doctype)
                    frappe.throw(f"{label}第{row.idx}行请填写手工依据")
                try:
                    refs = json.loads(row.source_refs or "[]")
                except ValueError:
                    frappe.throw("来源引用JSON无效")
                if not isinstance(refs, list):
                    frappe.throw("来源引用必须为记录列表")
                for ref in refs:
                    if not isinstance(ref, dict) or ref.get("doctype") not in ("BOM", "Project", "Timesheet", "Work Order"):
                        frappe.throw("来源类型无效")
                    source = read_source(ref["doctype"], ref.get("name"), self.company)
                    if ref["doctype"] in ("Project", "Timesheet"):
                        from client_akivision.utils.project_permissions import require_project_finance
                        require_project_finance()
                    if ref.get("row"):
                        children = [child.name for field in source.meta.get_table_fields() for child in source.get(field.fieldname) or []]
                        if ref["row"] not in children:
                            frappe.throw("引用明细不属于来源记录")
        if self.previous_version:
            read_source("Product Cost Quotation", self.previous_version, self.company)
        # A draft's actual reference is always reconstructed, never trusted from a client payload.
        if self.reference_work_order:
            from client_akivision.utils.product_cost_sources import work_order_reference
            self.actual_reference_json = frappe.as_json(work_order_reference(self.reference_work_order, self.company))
        else:
            self.actual_reference_json = ""
        self.recalculate()
        display = {key: self.get(key) for key in ("customer", "contact", "contact_phone", "quotation_date", "valid_until", "terms", "sales_contact", "sales_phone")}
        display["scenarios"] = [{key: row.get(key) for key in ("quantity", "show_in_customer_quote", "final_tax_inclusive_price")} for row in self.scenarios]
        self.quote_display_hash = hashlib.sha256(json.dumps(display, sort_keys=True, default=str).encode()).hexdigest()

    def recalculate(self):
        try:
            results = calculate(self.as_dict(), make_resolver(self))
        except ValueError as exc:
            frappe.throw(str(exc))
        for row, result in zip(self.scenarios, results, strict=True):
            for key, value in result.items():
                if key != "missing":
                    row.set(key, value)
        for material in self.materials:
            material.calculation_details_json = frappe.as_json([
                {"quantity": r["quantity"], "detail": d}
                for r in results for d in json.loads(r["detail_snapshot_json"])["materials"]
                if d.get("row") == material.name
            ])
        self.calculation_version = "1.0"
        payload = {"company": self.company, "currency": self.currency, "exchange_rate": self.exchange_rate,
                   "item": self.item_code or self.provisional_model,
                   "materials": [r.as_dict() for r in self.materials], "operations": [r.as_dict() for r in self.operations],
                   "investments": [r.as_dict() for r in self.investments], "results": results,
                   "actual_reference": self.actual_reference_json}
        # Strip volatile child timestamps so a second deterministic calculation yields the same hash.
        for table in ("materials", "operations", "investments"):
            for row in payload[table]:
                for key in ("modified", "creation", "owner", "modified_by", "docstatus", "parent", "__islocal", "__unsaved"):
                    row.pop(key, None)
        self.snapshot_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
        return results

    def before_submit(self):
        self.check_source_context()
        results = self.recalculate()
        errors = [f"批量{r['quantity']:g}：" + "；".join(r["missing"]) for r in results if r["missing"]]
        if errors:
            frappe.throw("数据不完整，不能确认：\n" + "\n".join(errors))
        if not self.estimate_acknowledged or not self.estimate_reason:
            frappe.throw("确认前请勾选估算依据确认，并填写说明（包含采购税务、项目归属和制造费用范围）")

    def check_source_context(self):
        context = json.loads(self.get("source_context_json") or "{}")
        for group in ("materials", "operations"):
            if context.get(group) and [value or None for value in context[group]] != [self.item_code or None, self.bom_no or None] and any(row.source_key for row in self.get(group) or []):
                frappe.throw("产品或BOM已变化，来源待刷新，请核对并应用材料及工时来源")
