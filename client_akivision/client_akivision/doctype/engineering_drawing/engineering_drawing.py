import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


FINALIZED = "Finalized"
WORKFLOW_TRANSITIONS = {
    ("Draft", "Pending Approval"),
    ("Pending Approval", FINALIZED),
    ("Pending Approval", "Rejected"),
    ("Rejected", "Draft"),
    (FINALIZED, "Obsolete"),
}
FINALIZED_FIELDS = ("drawing_no", "title", "item", "bom", "drawing_file", "drawing_preview", "revision", "remarks", "previous_revision")


class EngineeringDrawing(Document):
    def before_validate(self):
        self.status = self.status or "Draft"
        self.revision = self.revision or "v0"

    def validate(self):
        self.validate_revision()
        self.validate_state_change()
        self.validate_finalized_document()

    def validate_revision(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,19}", self.revision or ""):
            frappe.throw(_("版本只能使用字母、数字、点、下划线或连字符，最长 20 个字符。"))

        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", self.drawing_no or ""):
            frappe.throw(_("业务图纸号只能使用字母、数字、点、下划线或连字符，最长 80 个字符。"))

    def validate_state_change(self):
        if self.is_new():
            if self.status != "Draft":
                frappe.throw(_("新图纸必须从 Draft 状态创建。"))
            return

        previous = frappe.db.get_value(self.doctype, self.name, ["status", *FINALIZED_FIELDS], as_dict=True)
        if not previous:
            return
        if previous.status == "Pending Approval":
            changed = [field for field in FINALIZED_FIELDS if self.get(field) != previous.get(field)]
            if changed:
                frappe.throw(_("图纸正在审批中，不能修改内容；请等待驳回后修改并重新提交。"))
        if previous.status == FINALIZED:
            changed = [field for field in FINALIZED_FIELDS if self.get(field) != previous.get(field)]
            protected_changes = [
                field
                for field in changed
                if field not in {"item", "bom"} or previous.get(field) or not self.get(field)
            ]
            if protected_changes:
                frappe.throw(_("已定稿图纸不可修改；如需变更，请使用“创建修订版”。"))
            if self.status == "Obsolete":
                if not self.can_approve():
                    frappe.throw(_("只有 Manufacturing Manager 或 System Manager 可以作废已定稿图纸。"), frappe.PermissionError)
                return
            if self.status != FINALIZED:
                frappe.throw(_("已定稿图纸不可修改；如需变更，请使用“创建修订版”。"))
            return

        if previous.status != self.status:
            if (previous.status, self.status) not in WORKFLOW_TRANSITIONS:
                frappe.throw(_("不允许直接将图纸从 {0} 变更为 {1}。请使用审批工作流操作。").format(previous.status, self.status))
            if self.status in {FINALIZED, "Rejected", "Obsolete"} and not self.can_approve():
                frappe.throw(_("只有 Manufacturing Manager 或 System Manager 可以执行该审批操作。"), frappe.PermissionError)

    def validate_finalized_document(self):
        if self.status != FINALIZED:
            return
        if not self.drawing_file:
            frappe.throw(_("图纸定稿前必须上传图纸文件。"))
        if not self.approved_by:
            self.approved_by = frappe.session.user
        if not self.approved_on:
            self.approved_on = now_datetime()

    def on_update(self):
        if self.status == FINALIZED:
            self.sync_finalized_references()

    def sync_finalized_references(self):
        if self.item:
            frappe.db.set_value(
                "Item",
                self.item,
                {
                    "custom_engineering_drawing": self.name,
                    "custom_engineering_drawing_no": self.drawing_no,
                    "custom_engineering_drawing_revision": self.revision,
                },
                update_modified=False,
            )

        # A draft BOM may be prepared alongside the drawing. Submitted BOMs are
        # intentionally never modified here; their references remain auditable.
        if self.bom and frappe.db.get_value("BOM", self.bom, "docstatus") == 0:
            frappe.db.set_value(
                "BOM",
                self.bom,
                {
                    "custom_engineering_drawing": self.name,
                    "custom_engineering_drawing_no": self.drawing_no,
                    "custom_engineering_drawing_revision": self.revision,
                },
                update_modified=False,
            )

    @staticmethod
    def can_approve():
        roles = set(frappe.get_roles())
        return bool({"Manufacturing Manager", "System Manager"} & roles)
