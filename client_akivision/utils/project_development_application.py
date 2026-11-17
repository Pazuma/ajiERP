"""Project development application fields, validation and P1-style PDF export."""

import re
import base64
from pathlib import Path

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, getdate, get_fullname

from client_akivision.utils.formal_pdf_export import (
	download_documents,
	parse_names,
	read_doc,
	render_pdf,
)


EXPENSE_CATEGORIES = (
	"人员人工费",
	"直接投入费",
	"固定资产折旧与摊销",
	"无形资产摊销",
	"委外研发费用",
	"其他费用",
)

BUDGET_DEFAULTS = {
	"人员人工费": ("研发人员工资、奖金、社保、公积金等（按投入工时×人均薪酬测算）", ""),
	"直接投入费": ("研发领料、原材料、元器件、测试费、加工费等", ""),
	"固定资产折旧与摊销": ("研发专用设备折旧、软件/专利摊销", ""),
	"无形资产摊销": ("研发软件、专利摊销", ""),
	"委外研发费用": ("外部合作研发支出", ""),
	"其他费用": ("差旅费、会议费、第三方检测/咨询费、知识产权申请费等", "不超总预算10%"),
}

PROJECT_FIELDS = [
	{"fieldname": "custom_project_application_section", "label": "项目开发申请信息", "fieldtype": "Section Break", "insert_after": "custom_project_leader"},
	{"fieldname": "custom_application_date", "label": "申请日期", "fieldtype": "Date", "default": "Today", "insert_after": "custom_project_application_section"},
	{"fieldname": "custom_product_attr_proofing", "label": "打样测试", "fieldtype": "Check", "insert_after": "custom_application_date"},
	{"fieldname": "custom_product_attr_refurbished", "label": "改造品", "fieldtype": "Check", "insert_after": "custom_product_attr_proofing"},
	{"fieldname": "custom_product_attr_new", "label": "新产品", "fieldtype": "Check", "insert_after": "custom_product_attr_refurbished"},
	{"fieldname": "custom_product_attr_other", "label": "其他", "fieldtype": "Check", "insert_after": "custom_product_attr_new"},
	{"fieldname": "custom_replaced_customer_product", "label": "取代客户现用产品", "fieldtype": "Small Text", "insert_after": "custom_product_attr_other"},
	{"fieldname": "custom_optical_parameters_section", "label": "参数信息", "fieldtype": "Section Break", "insert_after": "custom_replaced_customer_product"},
	{"fieldname": "custom_magnification", "label": "倍率", "fieldtype": "Data", "insert_after": "custom_optical_parameters_section"},
	{"fieldname": "custom_working_distance", "label": "WD", "fieldtype": "Data", "insert_after": "custom_magnification"},
	{"fieldname": "custom_resolution", "label": "分辨率", "fieldtype": "Data", "insert_after": "custom_working_distance"},
	{"fieldname": "custom_oi_distance", "label": "O/I距", "fieldtype": "Data", "insert_after": "custom_resolution"},
	{"fieldname": "custom_tv_distortion", "label": "TV畸变", "fieldtype": "Data", "insert_after": "custom_oi_distance"},
	{"fieldname": "custom_business_impact", "label": "业务影响度", "fieldtype": "Long Text", "insert_after": "custom_tv_distortion"},
	{"fieldname": "custom_project_budget_total", "label": "预算总金额(元)", "fieldtype": "Currency", "options": "Company:company:default_currency", "read_only": 1, "insert_after": "custom_business_impact"},
	{"fieldname": "custom_department_manager", "label": "部门经理", "fieldtype": "Link", "options": "User", "insert_after": "custom_project_budget_total"},
	{"fieldname": "custom_project_leader_sign_date", "label": "项目负责人签字日期", "fieldtype": "Date", "insert_after": "custom_department_manager"},
	{"fieldname": "custom_department_manager_sign_date", "label": "部门经理签字日期", "fieldtype": "Date", "insert_after": "custom_project_leader_sign_date"},
	{"fieldname": "custom_project_budget_section", "label": "预算明细", "fieldtype": "Section Break", "insert_after": "custom_department_manager_sign_date"},
	{"fieldname": "custom_project_budget_details", "label": "预算明细", "fieldtype": "Table", "options": "Project Development Budget Detail", "insert_after": "custom_project_budget_section"},
	{"fieldname": "custom_project_files_tab", "label": "项目文件", "fieldtype": "Tab Break", "insert_after": "actual_end_date"},
	{"fieldname": "custom_project_files_section", "label": "项目文件", "fieldtype": "Section Break", "insert_after": "custom_project_files_tab"},
	{"fieldname": "custom_project_files_html", "label": "项目文件", "fieldtype": "HTML", "insert_after": "custom_project_files_section"},
	{"fieldname": "custom_project_files", "label": "项目文件", "fieldtype": "Table", "options": "Project File Item", "hidden": 1, "insert_after": "custom_project_files_html"},
	{"fieldname": "custom_project_standard_fields_section", "label": "项目基础信息", "fieldtype": "Section Break", "insert_after": "custom_department_manager_sign_date"},
]


def ensure_schema():
	"""Create the P1 fields without changing ERPNext's standard Project DocType."""
	# The Project Table field must only be created after the child DocType is
	# loaded into the site. This also makes the after_migrate hook safe on a
	# fresh site where the child table has not been cached yet.
	frappe.reload_doc("client_akivision", "doctype", "project_development_budget_detail", force=True)
	frappe.reload_doc("client_akivision", "doctype", "project_file_item", force=True)
	create_custom_fields({"Project": PROJECT_FIELDS}, update=True)
	frappe.db.updatedb("Project")
	frappe.clear_cache(doctype="Project")


def calculate_project_budget_total(doc):
	total = 0
	for row in doc.get("custom_project_budget_details") or []:
		category = (row.get("expense_category") or "").strip()
		if category not in EXPENSE_CATEGORIES:
			frappe.throw(_("预算明细第 {0} 行必须选择有效的费用分类。").format(row.idx))
		if row.get("amount") in (None, ""):
			frappe.throw(_("预算明细第 {0} 行必须填写金额。").format(row.idx))
		amount = flt(row.get("amount"))
		if amount < 0:
			frappe.throw(_("预算明细第 {0} 行金额不能为负数。").format(row.idx))
		total += amount
	doc.custom_project_budget_total = total
	return total


def validate_project_application(doc, method=None):
	"""Project validate hook for planned budget fields only."""
	start = doc.get("expected_start_date")
	end = doc.get("expected_end_date")
	if start and end and str(end) < str(start):
		frappe.throw(_("项目完成日期不能早于项目启动日期。"))
	calculate_project_budget_total(doc)


def _display_user(user):
	if not user:
		return ""
	return frappe.db.get_value("User", user, "full_name") or get_fullname(user) or user


def _display_date(value):
	if not value:
		return ""
	value = getdate(value)
	return f"{value.year}/{value.month}/{value.day}"


def _display_amount(value):
	if value in (None, ""):
		return ""
	return f"{flt(value):,.2f}".rstrip("0").rstrip(".")


def _safe_filename(value):
	value = re.sub(r'[\\/:*?"<>|\r\n]+', "-", str(value or "")).strip(" .-")
	return value[:100] or "未命名项目"


def _budget_rows(doc):
	rows = list(doc.get("custom_project_budget_details") or [])
	by_category = {row.get("expense_category"): row for row in rows}
	ordered = []
	for category in EXPENSE_CATEGORIES:
		row = by_category.get(category)
		default_basis, default_remarks = BUDGET_DEFAULTS[category]
		ordered.append({
			"category": category,
			"amount": _display_amount(row.get("amount")) if row else "",
			"calculation_basis": (row.get("calculation_basis") if row else "") or default_basis,
			"remarks": (row.get("remarks") if row else "") or default_remarks,
		})
	for row in rows:
		if row.get("expense_category") not in EXPENSE_CATEGORIES:
			ordered.append({
				"category": row.get("expense_category") or "",
				"amount": _display_amount(row.get("amount")),
				"calculation_basis": row.get("calculation_basis") or "",
				"remarks": row.get("remarks") or "",
			})
	return ordered


def _project_logo_data_uri():
	path = Path(frappe.get_app_path("client_akivision", "public", "images", "project_development_application_logo.png"))
	try:
		if path.is_file():
			return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
	except OSError:
		frappe.log_error(frappe.get_traceback(), "项目开发申请表 Logo 加载失败")
	return ""


def _context(doc):
	if doc.docstatus == 2:
		frappe.throw(_("已取消项目不能生成项目开发申请表。"))
	budget_total = calculate_project_budget_total(doc)
	company_currency = frappe.defaults.get_global_default("currency") or "CNY"
	return {
		"doc": doc,
		"project_name": doc.get("project_name") or doc.name,
		"project_code": doc.get("custom_project_code") or "",
		"application_date": _display_date(doc.get("custom_application_date")),
		"priority": doc.get("priority") or "",
		"department": doc.get("department") or "",
		"project_leader": _display_user(doc.get("custom_project_leader")),
		"department_manager": _display_user(doc.get("custom_department_manager")),
		"start_date": _display_date(doc.get("expected_start_date")),
		"end_date": _display_date(doc.get("expected_end_date")),
		"product_attributes": [
			{"label": "打样测试", "checked": bool(doc.get("custom_product_attr_proofing"))},
			{"label": "改造品", "checked": bool(doc.get("custom_product_attr_refurbished"))},
			{"label": "新产品", "checked": bool(doc.get("custom_product_attr_new"))},
			{"label": "其他", "checked": bool(doc.get("custom_product_attr_other"))},
		],
		"replaced_product": doc.get("custom_replaced_customer_product") or "",
		"description": doc.get("project_description") or doc.get("description") or "",
		"optical_parameters": [
			("倍率", doc.get("custom_magnification") or ""),
			("WD", doc.get("custom_working_distance") or ""),
			("分辨率", doc.get("custom_resolution") or ""),
			("O/I距", doc.get("custom_oi_distance") or ""),
			("TV畸变", doc.get("custom_tv_distortion") or ""),
		],
		"business_impact": doc.get("custom_business_impact") or "",
		"budget_rows": _budget_rows(doc),
		"budget_total": _display_amount(budget_total),
		"currency": company_currency,
		"leader_sign_date": _display_date(doc.get("custom_project_leader_sign_date")),
		"manager_sign_date": _display_date(doc.get("custom_department_manager_sign_date")),
		"project_logo_data_uri": _project_logo_data_uri(),
	}


@frappe.whitelist()
def download_project_development_application(document_names):
	from client_akivision.utils.project_permissions import require_project_finance
	require_project_finance()
	files = []
	for name in parse_names(document_names):
		doc = read_doc("Project", name)
		context = _context(doc)
		base = _safe_filename(doc.get("custom_project_code") or doc.name)
		project = _safe_filename(doc.get("project_name") or doc.name)
		files.append((f"项目开发申请表-{base}-{project}", render_pdf("templates/project_development_application.html", context, "Portrait")))
	download_documents(files, "项目开发申请表")
