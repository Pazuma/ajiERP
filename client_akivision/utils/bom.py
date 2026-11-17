"""BOM identity, import validation, and read-only structure helpers."""

import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.document import Document
from frappe.utils import cint


MAX_BOM_NAME_LENGTH = 140
SHARED_DRAWING_FIELDS = (
	"custom_shared_drawing_name", "custom_shared_drawing_revision", "custom_shared_drawing_path",
)
_UNC_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_shared_drawing_path(value):
	"""Return one safe Windows UNC path without probing the remote share."""
	path = (value or "").strip()
	if not path:
		return ""
	if _UNC_CONTROL_CHARACTERS.search(path):
		frappe.throw(_("图纸地址只能填写一条路径，不能包含换行或控制字符。"))
	if not path.startswith("\\\\") or path.startswith(("\\\\?\\", "\\\\.\\")):
		frappe.throw(_("图纸地址必须是 Windows UNC 路径，例如 \\\\文件服务器\\共享目录\\图纸.pdf。"))
	parts = path[2:].split("\\")
	if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
		frappe.throw(_("图纸地址必须同时包含服务器名和共享目录。"))
	if any(not part.strip() for part in parts):
		frappe.throw(_("图纸地址不能包含空的路径层级或多条路径。"))
	if any(char in path for char in ('<', '>', ':', '"', '|', '?', '*')):
		frappe.throw(_("图纸地址包含 Windows 路径不支持的字符。"))
	return path


def validate_shared_drawing_info(doc):
	doc.custom_shared_drawing_path = normalize_shared_drawing_path(doc.get("custom_shared_drawing_path"))
	for fieldname in SHARED_DRAWING_FIELDS[:2]:
		doc.set(fieldname, (doc.get(fieldname) or "").strip())


@frappe.whitelist()
def update_basic_drawing_info(bom, drawing_name=None, drawing_revision=None, drawing_path=None):
	"""Update descriptive drawing information using standard permissions and audit."""
	doc = frappe.get_doc("BOM", bom)
	doc.check_permission("write")
	if doc.docstatus != 1 or not doc.is_active:
		frappe.throw(_("仅已提交且有效的 BOM 可以编辑基本信息。草稿请直接编辑，历史版本请保留原资料。"))
	for fieldname, value in zip(SHARED_DRAWING_FIELDS, (drawing_name, drawing_revision, drawing_path)):
		doc.set(fieldname, value or "")
	validate_shared_drawing_info(doc)
	doc.save()
	return doc.name


def get_bom_code(item_code):
	"""Return the stable business code used for a model's first BOM."""
	model_code = (item_code or "").strip()
	if not model_code:
		frappe.throw(_("请选择型号后再创建 BOM。"))
	code = f"BOM-{model_code}"
	if len(code) > MAX_BOM_NAME_LENGTH:
		frappe.throw(_("型号编码过长，无法生成不超过 {0} 个字符的 BOM 编码。").format(MAX_BOM_NAME_LENGTH))
	return code


def get_item_code(item):
	"""Resolve a BOM Item link to its immutable business item code."""
	if not item:
		frappe.throw(_("请选择型号后再创建 BOM。"))
	item_code = frappe.db.get_value("Item", item, "item_code")
	if not item_code:
		frappe.throw(_("型号 {0} 不存在或未维护物料编码。").format(item))
	return item_code


def validate_bom(doc):
	"""Apply Akivision-specific invariants after ERPNext validates the BOM."""
	item_code = get_item_code(doc.item)
	doc.custom_bom_code = (doc.get("custom_bom_code") or "").strip() or get_bom_code(item_code)
	doc.custom_shared_drawing_path = normalize_shared_drawing_path(doc.get("custom_shared_drawing_path"))
	doc.custom_shared_drawing_name = (doc.get("custom_shared_drawing_name") or "").strip()
	doc.custom_shared_drawing_revision = (doc.get("custom_shared_drawing_revision") or "").strip()
	if len(doc.custom_bom_code) > MAX_BOM_NAME_LENGTH:
		frappe.throw(_("BOM 编码不能超过 {0} 个字符。").format(MAX_BOM_NAME_LENGTH))
	if doc.get("amended_from"):
		source = frappe.db.get_value(
			"BOM", doc.amended_from, ["item", "custom_bom_code", "docstatus"], as_dict=True
		)
		if not source or source.docstatus != 2:
			frappe.throw(_("BOM 只能从已取消的原版本创建修订。"))
		if source.item != doc.item:
			frappe.throw(_("BOM 修订版本必须与原版本使用相同型号。"))

	previous = doc.get_doc_before_save()
	if previous and previous.docstatus != 0 and previous.get("custom_bom_code") != doc.custom_bom_code:
		frappe.throw(_("已提交或已取消的 BOM 编码不能修改，请更新版本后修改草稿。"))
	if previous and previous.item != doc.item:
		frappe.throw(_("已保存的 BOM 不允许变更型号；请通过修订流程创建新版本。"))

	for row in doc.get("items", []):
		level = row.get("custom_import_level")
		if level not in (None, "") and cint(level) != 1:
			frappe.throw(
				_("第 {0} 行层级必须为 1。多层结构请拆为独立 BOM，并通过子 BOM 编码关联。").format(row.idx)
			)


class AkivisionBOMMixin(Document):
	"""Keep the standard BOM controller while replacing only first-version naming."""

	def autoname(self):
		if self.get("custom_version_source"):
			from client_akivision.utils.bom_version import name_version
			name_version(self)
			return
		# Frappe handles amendments before calling autoname. Therefore this applies
		# only to a model's first BOM and preserves standard revision traceability.
		bom_code = (self.get("custom_bom_code") or "").strip() or get_bom_code(get_item_code(self.item))
		existing = frappe.db.get_value(
			"BOM",
			{"item": self.item, "docstatus": ["<", 2]},
			["name"],
			as_dict=True,
		)
		if existing or frappe.db.exists("BOM", bom_code):
			existing_name = (existing or {}).get("name") or bom_code
			frappe.throw(
				_("型号 {0} 已存在 BOM {1}。请进入原 BOM 维护，或通过修订创建新版本。").format(
					self.item, existing_name
				)
			)
		self.name = bom_code

	def validate(self):
		super().validate()
		validate_bom(self)

	def before_update_after_submit(self):
		parent = getattr(super(), "before_update_after_submit", None)
		if parent:
			parent()
		previous = self.get_doc_before_save()
		if previous and any(previous.get(key) != self.get(key) for key in SHARED_DRAWING_FIELDS):
			if not self.is_active or not previous.is_active:
				frappe.throw(_("历史或停用 BOM 的图纸资料不能修改。"))
			validate_shared_drawing_info(self)


def ensure_schema():
	"""Create the small set of standard-DocType fields owned by this feature."""
	create_custom_fields(
		{
			"BOM": [
				{
					"fieldname": "custom_drawing_info_section",
					"label": "图纸资料",
					"fieldtype": "Section Break",
					"insert_after": "uom",
					"print_hide": 1,
				},
				{
					"fieldname": "custom_shared_drawing_name",
					"label": "图纸名称",
					"fieldtype": "Data",
					"insert_after": "custom_drawing_info_section",
					"allow_on_submit": 1,
					"print_hide": 1,
				},
				{
					"fieldname": "custom_shared_drawing_revision",
					"label": "图纸版本",
					"fieldtype": "Data",
					"insert_after": "custom_shared_drawing_name",
					"allow_on_submit": 1,
					"print_hide": 1,
				},
				{
					"fieldname": "custom_shared_drawing_path",
					"label": "图纸地址",
					"fieldtype": "Small Text",
					"insert_after": "custom_shared_drawing_revision",
					"allow_on_submit": 1,
					"print_hide": 1,
					"description": "仅支持一条 Windows UNC 共享目录或文件路径。",
				},
				{
					"fieldname": "custom_shared_drawing_actions",
					"label": "图纸地址操作",
					"fieldtype": "HTML",
					"insert_after": "custom_shared_drawing_path",
					"print_hide": 1,
				},
				{
					"fieldname": "custom_internal_model",
					"label": "内部机种",
					"fieldtype": "HTML",
					"insert_after": "custom_bom_code",
				},
				{
					"fieldname": "custom_external_model",
					"label": "外部型号",
					"fieldtype": "HTML",
					"insert_after": "custom_internal_model",
				},
				{
					"fieldname": "custom_bom_code",
					"label": "BOM 编码",
					"fieldtype": "Data",
					"insert_after": "item",
					"read_only": 0,
					"in_list_view": 1,
					"description": "草稿可人工填写；留空时按 BOM-型号编码生成。保存后的实际单号和工单引用不变。",
				},
				{
					"fieldname": "custom_bom_structure",
					"label": "BOM 展开结构",
					"fieldtype": "HTML",
					"hidden": 1,
					"insert_after": "items",
				},
				{
					"fieldname": "custom_bom_version_tab",
					"label": "版本",
					"fieldtype": "Tab Break",
					"insert_after": "connections_tab",
				},
				{
					"fieldname": "custom_bom_versions",
					"label": "BOM 版本记录",
					"fieldtype": "HTML",
					"insert_after": "custom_bom_version_tab",
				},
			],
			"BOM Item": [
				{
					"fieldname": "custom_import_level",
					"label": "层级（导入校验）",
					"fieldtype": "Int",
					"insert_after": "item_code",
					"default": "1",
					"hidden": 1,
					"description": "仅供 Excel 模板校验。直接组件必须为 1；实际层级由展开结构计算。",
				},
			],
		},
		update=True,
	)
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"BOM", "section_break_hygk", "label", "副产品", "Data", is_system_generated=True
	)
	make_property_setter(
		"BOM", "section_break_hygk", "collapsible", 1, "Check", is_system_generated=True
	)
	make_property_setter(
		"BOM", "secondary_items", "label", "", "Data", is_system_generated=True
	)
	for doctype in ("BOM", "BOM Item"):
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)
