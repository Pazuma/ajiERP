import json
import re
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from zipfile import BadZipFile

import frappe
from frappe import _
from frappe.core.doctype.data_import.data_import import BLOCKED_DOCTYPES
from frappe.utils import cint
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import read_xls_file_from_attached_file, read_xlsx_file_from_attached_file as _read_xlsx_file
from frappe.core.doctype.data_import.importer import Row as _DataImportRow
from client_akivision.utils import excel_reference_resolver
from client_akivision.utils import excel_record_presentation


def read_xlsx_file_from_attached_file(*args, **kwargs):
	"""Report invalid workbooks consistently across all import entry points."""
	try:
		return _read_xlsx_file(*args, **kwargs)
	except BadZipFile:
		frappe.throw(_("无法读取 Excel 文件：文件内容不是有效的 XLSX 工作簿，可能格式与扩展名不一致、已加密或文件已损坏。请用 Excel 或 WPS 打开文件，取消密码保护后，另存为“Excel 工作簿（.xlsx）”并重新上传；不要仅修改文件后缀。"), title=_("导入文件格式错误"))


# Frappe's importer assumes date cells are strings. Excel commonly stores
# dates as serial numbers, so normalize those values before its strptime call.
_original_row_get_date = _DataImportRow.get_date

def _get_date_with_excel_serial_support(self, value, column):
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		value = (date(1899, 12, 30) + timedelta(days=float(value))).isoformat()
	return _original_row_get_date(self, value, column)

_DataImportRow.get_date = _get_date_with_excel_serial_support


MODULE_LABELS = {
	"Selling": "销售",
	"Buying": "采购",
	"Stock": "库存",
	"Accounts": "财务",
	"Projects": "项目",
	"Manufacturing": "生产",
	"Assets": "资产",
	"Contacts": "联系人",
}


def _contact_template_options(import_file, import_type, existing_options=None):
	"""Map contact-like columns from a mixed business spreadsheet only."""
	options = frappe.parse_json(existing_options or "{}") if existing_options else {}
	if options.get("column_to_field_map"):
		return options
	from frappe.core.doctype.data_import.importer import ImportFile

	reader = ImportFile(
		doctype="Contact",
		file=import_file,
		template_options=frappe._dict(column_to_field_map=frappe._dict()),
		import_type=import_type,
	)
	rows = reader.raw_data or []
	headers = next((row for row in rows if any(str(value or "").strip() for value in row)), [])
	aliases = {
		"联系人": "first_name",
		"联系人姓名": "first_name",
		"姓名": "first_name",
		"FirstName": "first_name",
		"first_name": "first_name",
		"LastName": "last_name",
		"last_name": "last_name",
		"公司": "company_name",
		"公司名称": "company_name",
		"CompanyName": "company_name",
		"company_name": "company_name",
		"职务": "designation",
		"designation": "designation",
		"部门": "department",
		"department": "department",
		"状态": "status",
		"status": "status",
		"联系电话": "phone_nos.phone",
		"联系人电话": "phone_nos.phone",
		"电话": "phone_nos.phone",
		"手机": "phone_nos.phone",
		"手机号": "phone_nos.phone",
		"邮箱": "email_ids.email_id",
		"电子邮箱": "email_ids.email_id",
	}
	column_map = {}
	for index, header in enumerate(headers):
		key = re.sub(r"[\s　]+", "", str(header or "")).strip()
		column_map[str(index)] = aliases.get(key, "Don't Import")
	options["column_to_field_map"] = column_map
	return options


def _table_config():
	path = frappe.get_app_path("client_akivision", "config", "excel_import_tables.json")
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


IMPORT_HEADER_ALIASES = {
	"Customer": {"客户编号": "custom_customer_code", "客户名称": "customer_name", "联系人": "custom_excel_contact_name", "联系电话": "custom_excel_contact_phone", "地址": "custom_excel_address", "负责业务": "custom_responsible_business_name"},
	"Supplier": {"供应商编号": "custom_supplier_code", "供应商名称": "supplier_name", "联系人": "supplier_primary_contact", "合作状态": "custom_cooperation_status", "供应商评级": "custom_supplier_rating", "账期天数": "custom_credit_days", "备注": "custom_supplier_remarks"},
	"SupplierReview": {"供应商名称":"supplier_name", "采购订单总数":"custom_review_total_orders", "按时到货订单数":"custom_review_on_time_orders", "到货及时率":"custom_review_on_time_rate", "延迟订单数":"custom_review_delayed_orders", "平均延迟天数":"custom_review_average_delay_days", "供应商评级":"custom_review_rating"},
	"Payment Terms Template": {"模式编号": "custom_mode_code", "收款模式名称": "template_name", "默认账期天数": "terms.credit_days"},
	"Project": {"项目编号": "custom_project_code", "项目名称": "project_name", "立项日期": "expected_start_date", "立项日期 (yyyy-mm-dd)": "expected_start_date", "预计结项日期": "expected_end_date", "预计结项日期 (yyyy-mm-dd)": "expected_end_date", "项目负责人": "custom_project_leader", "预算": "estimated_costing", "申请日期": "custom_application_date", "打样测试": "custom_product_attr_proofing", "改造品": "custom_product_attr_refurbished", "新产品": "custom_product_attr_new", "其他产品属性": "custom_product_attr_other", "取代客户现用产品": "custom_replaced_customer_product", "倍率": "custom_magnification", "WD": "custom_working_distance", "分辨率": "custom_resolution", "O/I距": "custom_oi_distance", "TV畸变": "custom_tv_distortion", "业务影响度": "custom_business_impact", "部门经理": "custom_department_manager"},
	"Item": {"产品分类": "item_group", "No": "item_group", "Product code": "item_code", "Product name": "item_name", "备注（曾用名）": "custom_remarks", "状态": "custom_product_status", "说 明": "description", "说明": "description"},
	"ItemLiveStock": {"物料编码":"item_code", "物料名称":"item_name", "版本":"custom_live_stock_version", "适用机种":"custom_live_stock_applicable_model", "类别":"custom_live_stock_category", "初期":"custom_live_stock_opening_qty", "总入库":"custom_live_stock_total_in_qty", "总出库":"custom_live_stock_total_out_qty", "实时库存":"custom_live_stock_qty", "新货位":"custom_live_stock_new_warehouse", "盘点日期":"custom_live_stock_count_date", "单价":"custom_live_stock_unit_price", "总值":"custom_live_stock_total_value", "备   注":"custom_live_stock_remarks", "备注":"custom_live_stock_remarks", "原库位":"custom_live_stock_old_warehouse"},
	"ItemSafetyStock": {"物料编码":"item_code", "物料名称":"item_name", "物料类型":"item_group", "最低安全库存":"reorder_levels.warehouse_reorder_level", "安全库存预警线":"reorder_levels.warehouse_reorder_level", "最高库存上限":"reorder_levels.custom_max_stock_limit", "备注":"custom_safety_stock_remarks"},
	"Timesheet": {"工单号":"time_logs.custom_work_order", "姓名":"custom_excel_employee_name", "部门":"custom_excel_department", "日期":"time_logs.custom_excel_date", "开始时间":"time_logs.from_time", "结束时间":"time_logs.to_time", "总工时":"time_logs.custom_excel_total_hours"},
	"Sales Order": {"年份":"custom_excel_year", "月份":"custom_excel_month", "客户代码":"custom_excel_customer_code", "客户名称": "customer", "日期": "transaction_date", "日期 (yyyy-mm-dd)": "transaction_date", "客户订单号": "po_no", "产品代码": "items.item_code", "产品 代码": "items.item_code", "型号":"items.custom_excel_model", "货物名称":"items.custom_excel_goods_name", "数量": "items.qty", "单位": "items.uom", "含税单价": "items.rate", "订单金额":"items.custom_excel_order_amount", "订单完成状态":"custom_excel_order_status", "订单完成标记":"custom_excel_completion_flag", "是否高新收入":"custom_is_high_tech_revenue", "业务员":"custom_excel_sales_person", "收款条件": "payment_terms_template", "帐期":"custom_excel_payment_days", "发票号":"custom_excel_invoice_no", "开票日期":"custom_excel_invoice_date", "备  注":"custom_remarks", "已收金额":"custom_excel_received_amount", "未收金额":"custom_excel_unreceived_amount", "对账周期":"custom_excel_reconcile_cycle", "约定收款日期":"custom_excel_agreed_payment_date", "交货日期":"items.delivery_date", "该型号累计送货量":"items.custom_excel_cumulative_delivery_qty", "型号是否完成":"items.custom_excel_model_completion", "整单全部型号完成":"custom_excel_full_completion", "未送货件数":"items.custom_excel_undelivered_qty"},
	"Purchase Order": {"分类":"custom_excel_category", "单号":"custom_excel_order_no", "订单日期":"transaction_date", "供应商":"supplier", "物料编码":"items.item_code", "物料名称":"items.custom_excel_item_name", "单位":"items.uom", "数量":"items.qty", "含税价":"items.rate", "含税金额":"items.custom_excel_amount", "税率":"items.custom_excel_tax_rate", "含税总额":"items.custom_excel_total_amount", "最新交期":"schedule_date", "机种":"items.custom_excel_model", "订单总数":"items.custom_excel_order_qty", "已交":"items.custom_excel_delivered_qty", "未交":"items.custom_excel_undelivered_qty", "备注":"custom_excel_remarks", "对帐数量":"items.custom_excel_reconciled_qty", "对账/开票状况":"custom_excel_reconciliation_status"},
	"Purchase Receipt": {
		"物料编码": "items.item_code",
		"物料名称": "items.custom_excel_item_name",
		"版本": "items.custom_excel_version",
		"适用机种": "items.custom_excel_applicable_model",
		"物料类别": "items.custom_excel_item_group",
		"入库数量": "items.qty",
		"库位": "items.warehouse",
		"入库日期": "posting_date",
		"入库日期 (yyyy-mm-dd)": "posting_date",
		"入库类型": "custom_excel_receipt_type",
		"采购单号": "items.custom_excel_purchase_order",
		"送货单": "supplier_delivery_note",
		"供应商": "supplier",
		"镜片入库单/退料单": "custom_lens_receipt_no",
		"单价": "items.rate",
		"总价": "items.custom_excel_total_amount",
		"操作员": "custom_excel_operator",
		"对帐日期": "custom_reconciliation_date",
		"备注": "remarks",
	},
	"Delivery Note": {
		"年份": "custom_excel_year",
		"月份": "custom_excel_month",
		"客户": "custom_excel_customer_name",
		"客户\n代码": "custom_excel_customer_code",
		"客户代码": "custom_excel_customer_code",
		"客户 代码": "custom_excel_customer_code",
		"日期": "posting_date",
		"日期 (yyyy-mm-dd)": "posting_date",
		"业务员": "custom_excel_sales_person",
		"客户订单号": "po_no",
		"产品\n代码": "items.item_code",
		"产品 代码": "items.item_code",
		"产品代码": "items.item_code",
		"型号": "items.custom_excel_model",
		"单位": "items.custom_excel_unit",
		"数量": "items.qty",
		"含税单价": "items.rate",
		"订单金额": "items.custom_excel_order_amount",
		"送货单号": "custom_excel_delivery_no",
		"发票号": "custom_excel_invoice_no",
		"开票日期": "custom_excel_invoice_date",
		"订单状态": "custom_excel_order_status",
		"备  注": "custom_remarks",
		"备\u00a0注": "custom_remarks",
		"备注": "custom_remarks",
		"库位": "items.warehouse",
	},
	"Payment Entry": {"客户代码": "party", "客户名称": "party", "供应商名称": "party", "付款金额": "paid_amount", "收款金额": "received_amount", "已收金额": "received_amount", "总金额": "paid_amount", "收款日期": "posting_date", "付款日期": "posting_date", "订单号": "references.reference_name", "采购单号": "references.reference_name"},
	"Stock Entry": {
		"物料编码": "items.item_code", "物料名称": "items.custom_excel_item_name",
		"版本": "items.custom_excel_version", "适用机种": "items.custom_excel_applicable_model",
		"物料类别": "items.custom_excel_item_group", "出库数量": "items.qty",
		"应出库": "items.custom_excel_expected_qty", "出库日期": "posting_date",
		"出库单号": "custom_excel_outbound_no", "出库类型": "stock_entry_type",
		"库位": "items.s_warehouse", "单价": "items.basic_rate", "出库金额": "items.custom_excel_total_amount",
		"操作员": "custom_excel_operator", "机种": "custom_excel_model", "备注": "remarks",
		"出库类别": "custom_excel_issue_category", "说明": "custom_excel_explanation",
	},
	"Finished Goods Status": {"序列号\n(SN)": "serial_no", "序列号(SN)": "serial_no", "入库\n数量": "in_qty", "入库数量": "in_qty", "入库\n时间": "in_date", "入库时间": "in_date", "状态": "status", "子状态": "sub_status", "客  户": "customer", "客户": "customer", "客户\n联系人": "contact_person", "客户联系人": "contact_person", "联系方式": "phone", "借出/销售": "loan_or_sales_by", "借用/销售单号": "loan_or_sales_no", "借出/销售\n日期": "loan_or_sales_date", "借出/销售日期": "loan_or_sales_date", "工单号": "work_order_no", "库  位": "warehouse", "库位": "warehouse", "备  注": "remarks", "备注": "remarks"},
	"Asset": {
		"固定资产编号": "custom_asset_code",
		"固定资产名称": "asset_name",
		"规格型号": "custom_asset_specification",
		"序列号": "custom_asset_serial_no",
		"入帐日期": "purchase_date",
		"入账日期": "purchase_date",
		"折旧年限": "custom_asset_depreciation_years",
		"原值": "net_purchase_amount",
		"使用部门": "custom_asset_department",
		"保管人": "custom_asset_custodian",
		"每月折旧金额": "custom_asset_monthly_depreciation",
		"状态": "custom_asset_status",
		"备注": "custom_asset_remarks",
	},
}

# Excel source values are translated at the import boundary. Core DocType
# validation still receives the canonical Select/Link values.
IMPORT_VALUE_ALIASES = {
	"Project": {},
	"Item": {
		"custom_product_status": {"开发": "Development", "已打样": "Sampled", "已量产": "Mass Produced"},
	},
	"Sample Loan Out": {
		"status": {"已归还": "Returned", "借出中": "Loaned", "转销售": "Converted to Sales"},
	},
}


def _source_column_map(doctype, import_file):
	file_doc = frappe.get_doc("File", {"file_url": import_file})
	content = file_doc.get_content()
	extension = (file_doc.get_extension()[1] or "").lower().lstrip(".")
	if extension == "xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	elif extension == "xls":
		rows = read_xls_file_from_attached_file(content)
	elif extension == "csv":
		rows = read_csv_content(content)
	else:
		return {}
	headers = next((list(row) for row in rows if any(str(value or "").strip() for value in row)), [])
	# The product workbook contains two identical "Product name" headers. In
	# that workbook the first column is the item group and the third is item
	# name; positional mapping prevents the duplicate-column guard from
	# dropping the actual item name.
	if doctype == "Item" and len(headers) >= 6 and headers[:3] == ["Product name", "Product code", "Product name"]:
		return {
			"0": "item_group",
			"1": "item_code",
			"2": "item_name",
			"3": "custom_remarks",
			"4": "custom_product_status",
			"5": "description",
		}
	# The real-time inventory workbook is a snapshot imported into Item.
	alias_key = "ItemLiveStock" if doctype == "Item" and "实时库存" in (file_doc.file_name or "") else doctype
	if doctype == "Item" and "安全库存" in (file_doc.file_name or ""):
		alias_key = "ItemSafetyStock"
	if doctype == "Timesheet" and "工时记录" in (file_doc.file_name or ""):
		alias_key = "Timesheet"
	if doctype == "Supplier" and "供应商回顾" in (file_doc.file_name or ""):
		alias_key = "SupplierReview"
	aliases = IMPORT_HEADER_ALIASES.get(alias_key, {})
	mapped = {}
	for index, header in enumerate(headers):
		key = str(header or "").strip()
		if doctype == "Asset" and re.sub(r"[\s\u3000\n]+", "", key).startswith("国标分类编号"):
			mapped[str(index)] = "custom_national_asset_classification_code"
		elif key in aliases:
			mapped[str(index)] = aliases[key]
	return mapped


def _apply_import_value_aliases(doctype, doc):
	"""Translate source-only labels before standard DocType validation."""
	if not doc:
		return doc
	for fieldname, aliases in IMPORT_VALUE_ALIASES.get(doctype, {}).items():
		if doc.get(fieldname) in aliases:
			doc[fieldname] = aliases[doc[fieldname]]
	for child in doc.values():
		if isinstance(child, list):
			for row in child:
				if isinstance(row, dict):
					_apply_import_value_aliases(doctype, row)
	return doc


def _filter_source_alias_warnings(doctype, preview):
	if not preview:
		return preview
	if doctype not in IMPORT_VALUE_ALIASES:
		if doctype == "Finished Goods Status" and preview:
			# FGS import normalizes source-only statuses, serials, links and warehouses in _normalize_import_doc.
			preview.warnings = [{"type": "info", "message": _( "成品状态导入将自动补建序列号/物料，未知状态、联系人和库位按导入规则处理。" )}]
		# These source values are intentionally normalized by the importer.
		if doctype in ("Sales Order", "Purchase Order", "Purchase Receipt", "Delivery Note", "Payment Entry", "Stock Entry", "Sample Loan Out", "Sample Loan In"):
			kept = []
			for warning in preview.get("warnings", []):
				message = str(warning.get("message") or "")
				if any(label in message for label in ("Warehouse", "Stock Entry Type", "Work Order", "UOM", "Payment Terms Template")):
					continue
				if doctype in ("Sales Order", "Delivery Note") and "Customer" in message:
					continue
				if doctype == "Purchase Receipt" and "Supplier" in message:
					continue
				if doctype == "Payment Entry" and "货款" in message:
					continue
				if doctype == "Sample Loan Out" and any(label in message for label in ("User", "以下值无效", "借样形式")):
					continue
				kept.append(warning)
			preview.warnings = kept
		return preview
	status_columns = {}
	for column in preview.get("columns", []):
		fieldname = (column.get("df") or {}).get("fieldname") if isinstance(column.get("df"), dict) else None
		if fieldname:
			status_columns[column.get("index")] = fieldname
			status_columns[column.get("column_number")] = fieldname
	kept = []
	translated = False
	defaulted_group = False
	for warning in preview.get("warnings", []):
		message = str(warning.get("message") or "")
		fieldname = status_columns.get(warning.get("col", -1))
		if fieldname in IMPORT_VALUE_ALIASES[doctype] or (doctype == "Item" and "以下值无效" in message and any(value in message for value in IMPORT_VALUE_ALIASES[doctype]["custom_product_status"])):
			translated = True
			continue
		if doctype == "Item" and ("Item Group" in message or "物料组" in message):
			defaulted_group = True
			continue
		if doctype == "Project" and "User" in message:
			kept.append({"type": "info", "message": _("Excel 中不存在的项目负责人将暂用 Administrator，导入后可人工修改。")})
			continue
		kept.append(warning)
	if translated:
		kept.append({"type": "info", "message": _("Excel 产品状态将按列表导入规则转换为系统枚举值。")})
	if defaulted_group:
		kept.append({"type": "info", "message": _("Excel 中不存在的物料组将使用系统默认物料组，导入后可人工修改。")})
	preview.warnings = kept
	return preview


def _prepare_standard_import_options(doctype, import_file):
	return json.dumps({"column_to_field_map": _source_column_map(doctype, import_file)}, ensure_ascii=False)


def _first_existing(doctype, filters=None):
	return frappe.db.get_value(doctype, filters or {}, "name", order_by="modified desc")


def _default_warehouse(company=None):
	filters = {"is_group": 0}
	if company and frappe.db.has_column("Warehouse", "company"):
		filters["company"] = company
	return _first_existing("Warehouse", filters)


def _resolve_reference(doctype, value):
	"""Resolve Excel business codes to Frappe names without changing source values."""
	if not value or frappe.db.exists(doctype, value):
		return value
	code_fields = {"Customer": "custom_customer_code", "Supplier": "custom_supplier_code"}
	fieldname = code_fields.get(doctype)
	return frappe.db.get_value(doctype, {fieldname: value}, "name") if fieldname else value


def _normalize_import_doc(doctype, doc, filename=""):
	"""Apply safe defaults and code-to-Link resolution after Excel parsing."""
	if not doc:
		return doc
	_apply_import_value_aliases(doctype, doc)
	if doctype == "Customer":
		doc.customer_type = doc.get("customer_type") or "Company"
		doc.customer_group = doc.get("customer_group") or _first_existing("Customer Group")
		doc.territory = doc.get("territory") or _first_existing("Territory")
	if doctype == "Supplier":
		doc.supplier_type = doc.get("supplier_type") or "Company"
		doc.supplier_group = doc.get("supplier_group") or _first_existing("Supplier Group")
	if doctype == "Item":
		item_group = doc.get("item_group")
		if not item_group or not frappe.db.exists("Item Group", item_group):
			if item_group and not doc.get("custom_remarks"):
				doc.custom_remarks = f"Excel产品分类：{item_group}"
			doc.item_group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
		doc.stock_uom = doc.get("stock_uom") or _first_existing("UOM") or "Nos"
		if "实时库存" in (filename or ""):
			doc.item_name = doc.get("item_name") or doc.get("item_code")
			doc.item_group = doc.get("item_group") or _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
	if doctype == "Project":
		leader = doc.get("custom_project_leader")
		if not leader or not frappe.db.exists("User", leader):
			doc.custom_project_leader = "Administrator"
	if doctype == "Sales Order":
		# Sales Order validation requires a delivery date for every item.  The
		# workbook's delivery-date column is optional, so use the order date as
		# a deterministic fallback while retaining the source values in custom fields.
		order_date = doc.get("transaction_date")
		default_warehouse = _first_existing("Warehouse", {"is_group": 0, "company": doc.get("company"), "warehouse_name": ["not like", "%样品%"]}) or _first_existing("Warehouse", {"company": doc.get("company")})
		for item in doc.get("items") or []:
			if not item.get("delivery_date"):
				item["delivery_date"] = order_date
			if not item.get("warehouse") and default_warehouse:
				item["warehouse"] = default_warehouse
	if doctype == "Asset":
		# The source workbook is an asset register, not an ERPNext purchase
		# receipt. Keep every source value while supplying the standard links
		# required by Asset so historical rows can be imported safely.
		asset_code = doc.get("custom_asset_code")
		asset_name = doc.get("asset_name") or asset_code or "未命名资产"
		specification = doc.get("custom_asset_specification")
		item_code = doc.get("item_code")
		if not item_code or not frappe.db.exists("Item", item_code):
			item_code = frappe.db.get_value("Item", {"item_name": specification or asset_name}, "name")
		if not item_code:
			item_code = f"FA-{asset_code}" if asset_code else f"FA-{frappe.generate_hash(length=10)}"
		asset_category = doc.get("asset_category") or _first_existing("Asset Category")
		if not frappe.db.exists("Item", item_code):
			item_group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
			uom = _first_existing("UOM") or "Nos"
			frappe.get_doc({
				"doctype": "Item",
				"item_code": item_code,
				"item_name": specification or asset_name,
				"item_group": item_group,
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_fixed_asset": 1,
				"asset_category": asset_category,
			}).insert(ignore_permissions=True)
		doc.item_code = item_code
		if frappe.db.has_column("Item", "is_fixed_asset"):
			frappe.db.set_value("Item", item_code, "is_fixed_asset", 1)
		doc.asset_name = asset_name
		doc.company = doc.get("company") or _first_existing("Company")
		doc.asset_category = asset_category
		if frappe.db.has_column("Item", "asset_category") and not frappe.db.get_value("Item", item_code, "asset_category"):
			frappe.db.set_value("Item", item_code, "asset_category", asset_category)
		doc.location = doc.get("location") or _first_existing("Location")
		if not doc.location:
			doc.location = "默认位置"
			if not frappe.db.exists("Location", doc.location):
				frappe.get_doc({"doctype": "Location", "location_name": doc.location, "is_group": 0}).insert(ignore_permissions=True)
		doc.asset_quantity = doc.get("asset_quantity") or 1
		doc.calculate_depreciation = cint(doc.get("calculate_depreciation"))
		if not doc.get("available_for_use_date") and doc.get("purchase_date"):
			doc.available_for_use_date = doc.get("purchase_date")
		# Preserve the human-entered names even when the corresponding master
		# data does not exist yet; use a Link only when it resolves cleanly.
		department = doc.get("custom_asset_department")
		if department and frappe.db.exists("Department", department):
			doc.department = department
		custodian = doc.get("custom_asset_custodian")
		if custodian and frappe.db.exists("Employee", custodian):
			doc.custodian = custodian
		years = cint(doc.get("custom_asset_depreciation_years"))
		if years and not doc.get("total_number_of_depreciations"):
			doc.total_number_of_depreciations = years * 12
			doc.frequency_of_depreciation = doc.get("frequency_of_depreciation") or 1
	if doctype == "Payment Terms Template":
		for term in doc.get("terms") or []:
			if not term.get("payment_term"):
				term.payment_term = _ensure_payment_term(doc.get("template_name"), term.get("credit_days") or 0)
			term.invoice_portion = term.get("invoice_portion") or 100
			term.due_date_based_on = term.get("due_date_based_on") or "Day(s) after invoice date"
			term.credit_days = term.get("credit_days") if term.get("credit_days") is not None else 0
	if doctype in ("Sales Order", "Delivery Note"):
		if doc.get("customer"):
			doc.customer = _resolve_reference("Customer", doc.customer)
		for item in doc.get("items") or []:
			item.uom = item.get("uom") or "Nos"
			item.warehouse = item.get("warehouse") or _default_warehouse(doc.get("company"))
			item.warehouse = item.get("warehouse") or _default_warehouse(doc.get("company"))
			if item.get("warehouse") and not frappe.db.exists("Warehouse", item.warehouse):
				item.warehouse = _default_warehouse()
		if doctype == "Sales Order" and doc.get("payment_terms_template") and not frappe.db.exists("Payment Terms Template", doc.payment_terms_template):
			doc.payment_terms_template = _first_existing("Payment Terms Template")
	if doctype == "Purchase Order":
		if doc.get("supplier"):
			doc.supplier = _resolve_reference("Supplier", doc.supplier)
		for item in doc.get("items") or []:
			item.uom = item.get("uom") or "Nos"
			item.warehouse = item.get("warehouse") or _default_warehouse(doc.get("company"))
			if item.get("item_code") and not frappe.db.exists("Item", item.item_code):
				item.item_code = frappe.db.get_value("Item", {"item_name": item.item_code}, "name")
			if item.get("schedule_date") and not isinstance(item.schedule_date, (date, datetime)):
				item.schedule_date = _excel_date(item.schedule_date)
		if not doc.get("schedule_date"):
			doc.schedule_date = doc.get("transaction_date") or date.today()
	if doctype == "Purchase Receipt":
		if doc.get("supplier"):
			doc.supplier = _resolve_reference("Supplier", doc.supplier)
		for item in doc.get("items") or []:
			item.uom = item.get("uom") or "Nos"
			if item.get("warehouse") and not frappe.db.exists("Warehouse", item.warehouse):
				item.warehouse = _default_warehouse(doc.get("company"))
	if doctype == "Payment Entry":
		is_purchase_payment = "采购付款" in (filename or "")
		doc.payment_type = doc.get("payment_type") or ("Pay" if is_purchase_payment else "Receive")
		if doc.payment_type == "货款":
			doc.payment_type = "Pay"
		doc.party_type = doc.get("party_type") or ("Supplier" if is_purchase_payment else "Customer")
		if doc.get("party"):
			doc.party = _resolve_reference(doc.party_type, doc.party)
		company = doc.get("company") or _first_existing("Company")
		doc.company = doc.get("company") or company
		if company:
			if doc.payment_type == "Receive":
				doc.paid_from = doc.get("paid_from") or frappe.db.get_value("Company", company, "default_receivable_account")
				doc.paid_to = doc.get("paid_to") or frappe.db.get_value("Company", company, "default_cash_account")
			else:
				doc.paid_from = doc.get("paid_from") or frappe.db.get_value("Company", company, "default_cash_account")
				doc.paid_to = doc.get("paid_to") or frappe.db.get_value("Company", company, "default_payable_account")
	if doctype == "Stock Entry":
		doc.stock_entry_type = doc.get("stock_entry_type") or "Material Issue"
		for item in doc.get("items") or []:
			item.uom = item.get("uom") or "Nos"
			for warehouse_field in ("s_warehouse", "t_warehouse"):
				warehouse = item.get(warehouse_field)
				if warehouse and not frappe.db.exists("Warehouse", warehouse):
					item[warehouse_field] = _default_warehouse()
	if doctype == "Finished Goods Status":
		item_code = doc.get("item_code") or "1141-AKY-55R5-CGTC"
		if not frappe.db.exists("Item", item_code):
			group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
			uom = frappe.db.get_value("UOM", "Nos", "name") or _first_existing("UOM")
			frappe.get_doc({"doctype": "Item", "item_code": item_code, "item_name": item_code, "item_group": group, "stock_uom": uom, "is_stock_item": 1}).insert(ignore_permissions=True)
		doc.item_code = item_code
		doc.warehouse = doc.get("warehouse") if doc.get("warehouse") and frappe.db.exists("Warehouse", doc.get("warehouse")) else _default_warehouse()
		if not doc.get("serial_no"):
			doc.serial_no = f"FGS-ERP-{frappe.generate_hash(length=8)}"
		if not frappe.db.exists("Serial No", doc.serial_no):
			frappe.get_doc({"doctype": "Serial No", "serial_no": doc.serial_no, "item_code": item_code}).insert(ignore_permissions=True)
		if doc.get("status") not in ("借出样品", "样品", "销售品"):
			doc.status = "销售品"
		if doc.get("sub_status") not in ("已借出", "for-sample", "已销售", "转销售", "旧款"):
			doc.sub_status = None
		if doc.get("customer") and doc.get("contact_person") and frappe.db.exists("Customer", doc.customer):
			contact = frappe.db.get_value("Contact", {"first_name": doc.contact_person}, "name")
			if not contact:
				contact_doc = frappe.get_doc({"doctype": "Contact", "first_name": doc.contact_person, "mobile_no": doc.get("phone"), "links": [{"link_doctype": "Customer", "link_name": doc.customer}]})
				contact_doc.insert(ignore_permissions=True)
			elif not frappe.db.exists("Dynamic Link", {"parenttype": "Contact", "parent": contact, "link_doctype": "Customer", "link_name": doc.customer}):
				frappe.get_doc("Contact", contact).append("links", {"link_doctype": "Customer", "link_name": doc.customer}).save(ignore_permissions=True)
	if doctype == "Sample Loan Out":
		status_map = {"已归还": "Returned", "借出中": "Loaned", "转销售": "Converted to Sales"}
		doc.status = status_map.get(doc.get("status"), doc.get("status") or "Draft")
		for row in doc.get("items") or []:
			row.status = {"已归还": "已归还", "借出中": "借出中", "转销售": "已转销售"}.get(row.get("status"), row.get("status") or "借出中")
			if row.get("loan_form") not in ("书面合同", "口头协议", "免费试用", "付费借用"):
				row.loan_form = None
	return doc


def _normalize_import_payloads(doctype, payloads, filename=""):
	for payload in payloads:
		payload.doc = _normalize_import_doc(doctype, payload.doc, filename)
	return payloads


def _raw_excel_matrix(import_file):
	"""Read the source matrix without converting duplicate headers to a dict."""
	file_doc = frappe.get_doc("File", {"file_url": import_file})
	content = file_doc.get_content()
	extension = (file_doc.get_extension()[1] or "").lower().lstrip(".")
	if extension == "xlsx":
		return read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	if extension == "xls":
		return read_xls_file_from_attached_file(content)
	if extension == "csv":
		return read_csv_content(content)
	return []


def _apply_item_source_values(payloads, import_file):
	"""Restore positional Item columns before standard validation."""
	if "实时库存" in (import_file or ""):
		return payloads
	rows = _raw_excel_matrix(import_file)
	if not rows:
		return payloads
	header_index = next((index for index, row in enumerate(rows) if any(str(value or "").strip() for value in row)), None)
	if header_index is None:
		return payloads
	headers = [str(value or "").strip() for value in rows[header_index]]
	if len(headers) < 6 or headers[:3] != ["Product name", "Product code", "Product name"]:
		return payloads
	values_by_row = {
		index + 1: list(row)
		for index, row in enumerate(rows[header_index + 1:], start=header_index + 1)
		if any(str(value or "").strip() for value in row)
	}
	for payload in payloads:
		if not payload.rows:
			continue
		values = values_by_row.get(payload.rows[0].row_number)
		if not values:
			continue
		get_value = lambda position: (str(values[position]).strip() if position < len(values) and values[position] not in (None, "") else None)
		payload.doc.item_group = get_value(0)
		payload.doc.item_code = get_value(1)
		payload.doc.item_name = get_value(2)
		payload.doc.custom_remarks = get_value(3)
		payload.doc.custom_product_status = get_value(4)
		payload.doc.description = get_value(5)
	return payloads


def _raw_excel_rows(import_file):
	try:
		file_doc = frappe.get_doc("File", {"file_url": import_file})
		content = file_doc.get_content()
	except Exception:
		path = frappe.get_site_path("private", "files", import_file.rsplit("/", 1)[-1])
		with open(path, "rb") as handle:
			content = handle.read()
	extension = (file_doc.get_extension()[1] or "").lower().lstrip(".")
	if extension == "xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	elif extension == "xls":
		rows = read_xls_file_from_attached_file(content)
	else:
		rows = read_csv_content(content)
	header_index = next((index for index, row in enumerate(rows) if any(str(value or "").strip() for value in row)), None)
	if header_index is None:
		return []
	headers = [str(value or "").strip() for value in rows[header_index]]
	return [{headers[i]: row[i] if i < len(row) else None for i in range(len(headers))} for row in rows[header_index + 1:] if any(str(value or "").strip() for value in row)]


def _row_value(row, *names):
	for name in names:
		value = row.get(name)
		if value not in (None, ""):
			return value
	return None


def _excel_text(value):
	"""Keep source values readable without turning empty cells into strings."""
	if value in (None, ""):
		return None
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	return str(value).strip()


def _ensure_payment_term(payment_term_name, credit_days=0):
	"""Return the Payment Term linked to an imported settlement-mode row."""
	name = _excel_text(payment_term_name)
	if not name:
		return None
	existing = frappe.db.get_value("Payment Term", {"payment_term_name": name}, "name")
	if existing:
		return existing
	if frappe.db.exists("Payment Term", name):
		return name
	term = frappe.new_doc("Payment Term")
	term.payment_term_name = name
	term.invoice_portion = 100
	term.due_date_based_on = "Day(s) after invoice date"
	term.credit_days = cint(credit_days)
	term.insert(ignore_permissions=True)
	return term.name


def _excel_date(value):
	"""Accept openpyxl dates as well as unformatted Excel serial dates."""
	if value in (None, ""):
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	if isinstance(value, (int, float)):
		return date(1899, 12, 30) + timedelta(days=float(value))
	if isinstance(value, str):
		text = value.strip()
		try:
			return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
		except ValueError:
			try:
				return frappe.utils.getdate(text)
			except Exception:
				return None
	return None


def _ensure_excel_supplier(value):
	"""Resolve a supplier by code/name, creating a minimal master when needed."""
	value = _excel_text(value)
	if not value:
		return None
	resolved = _resolve_reference("Supplier", value)
	if resolved and frappe.db.exists("Supplier", resolved):
		return resolved
	by_name = frappe.db.get_value("Supplier", {"supplier_name": value}, "name")
	if by_name:
		return by_name
	group = _first_existing("Supplier Group")
	if not group:
		return None
	supplier = frappe.get_doc({
		"doctype": "Supplier",
		"supplier_name": value,
		"supplier_group": group,
		"supplier_type": "Company",
		"custom_supplier_code": value,
	})
	supplier.insert(ignore_permissions=True)
	return supplier.name


def _ensure_excel_item(row):
	"""Create a minimal Item so historical receipt rows never lose source data."""
	code = _excel_text(_row_value(row, "物料编码"))
	if not code:
		return None
	if frappe.db.exists("Item", code):
		return code
	group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
	if not group:
		return None
	item = frappe.get_doc({
		"doctype": "Item",
		"item_code": code,
		"item_name": _excel_text(_row_value(row, "物料名称")) or code,
		"item_group": group,
		"stock_uom": "Nos",
		"is_stock_item": 1,
	})
	for fieldname, source_name in (("custom_version", "版本"), ("custom_applicable_model", "适用机种")):
		if frappe.get_meta("Item").has_field(fieldname):
			setattr(item, fieldname, _excel_text(_row_value(row, source_name)))
	item.insert(ignore_permissions=True)
	return item.name


def _set_if_field(doc, fieldname, value):
	if value not in (None, "") and frappe.get_meta(doc.doctype).has_field(fieldname):
		setattr(doc, fieldname, value)


def _run_purchase_order_import(doc):
	"""Import the flat purchase ledger as one Purchase Order per source order number."""
	from frappe.core.doctype.data_import.importer import create_import_log

	matrix = _raw_excel_matrix(doc.import_file)
	if not matrix:
		doc.db_set("status", "Error")
		return {"name": doc.name, "status": "Error"}
	header_index = next((i for i, row in enumerate(matrix) if any(str(v or "").strip() for v in row)), None)
	headers = [str(v or "").strip() for v in matrix[header_index]]
	seen_headers = {}
	unique_headers = []
	for header in headers:
		count = seen_headers.get(header, 0)
		unique_headers.append(header if count == 0 else f"{header}.{count}")
		seen_headers[header] = count + 1
	rows = [{unique_headers[i]: row[i] if i < len(row) else None for i in range(len(unique_headers))}
		for row in matrix[header_index + 1:] if any(str(v or "").strip() for v in row)]
	company = _first_existing("Company")
	warehouse = _default_warehouse(company)
	groups = {}
	for index, row in enumerate(rows, start=2):
		order_no = _excel_text(_row_value(row, "单号")) or f"ROW-{index}"
		groups.setdefault(order_no, []).append((index, row))
	logs = []
	for order_index, (order_no, source_rows) in enumerate(groups.items()):
		try:
			existing = frappe.db.get_value("Purchase Order", {"custom_excel_order_no": order_no}, "name")
			if existing:
				create_import_log(doc.name, order_index, {"success": True, "docname": existing, "row_indexes": [i for i, _ in source_rows]})
				logs.append(True)
				continue
			first = source_rows[0][1]
			supplier_value = _row_value(first, "供应商")
			supplier = _ensure_excel_supplier(supplier_value)
			if not supplier:
				frappe.throw(_("采购订单 {0} 无法建立供应商：{1}").format(order_no, supplier_value or "空值"))
			po = frappe.new_doc("Purchase Order")
			po.company = company
			po.supplier = supplier
			po.transaction_date = _excel_date(_row_value(first, "订单日期")) or frappe.utils.today()
			po.schedule_date = _excel_date(_row_value(first, "最新\n交期", "最新交期")) or po.transaction_date
			_set_if_field(po, "custom_excel_category", _excel_text(_row_value(first, "分类")))
			_set_if_field(po, "custom_excel_order_no", order_no)
			_set_if_field(po, "custom_excel_import_status", "导入")
			_set_if_field(po, "custom_excel_source_file", Path(doc.import_file or "").name)
			_set_if_field(po, "custom_excel_source_rows", ",".join(str(i) for i, _ in source_rows))
			_set_if_field(po, "custom_excel_remarks", _excel_text(_row_value(first, "备注")))
			_set_if_field(po, "custom_excel_reconciliation_status", _excel_text(_row_value(first, "对账\n/开票\n状况", "对账/开票\n状况", "对账/开票状况")))
			order_total = 0
			for source_index, row in source_rows:
				item_code = _ensure_excel_item({"物料编码": _row_value(row, "物料编码"), "物料名称": _row_value(row, "物料名称"), "版本": None, "适用机种": _row_value(row, "机种")})
				if not item_code:
					frappe.throw(_("第 {0} 行无法建立物料：{1}").format(source_index, _row_value(row, "物料编码") or "空值"))
				qty = float(_row_value(row, "数量") or 0)
				rate = float(_row_value(row, "含税价") or 0)
				amount = _row_value(row, "含税\n金额", "含税金额")
				amount = float(amount) if amount not in (None, "") and not (isinstance(amount, str) and amount.startswith("=")) else qty * rate
				order_total += amount
				line = po.append("items", {})
				line.item_code = item_code
				line.qty = qty
				raw_uom = _excel_text(_row_value(row, "单位"))
				line.uom = raw_uom if raw_uom and frappe.db.exists("UOM", raw_uom) else (frappe.db.get_value("Item", item_code, "stock_uom") or "Nos")
				line.rate = rate
				line.schedule_date = _excel_date(_row_value(row, "最新\n交期", "最新交期")) or po.schedule_date
				for field, value in {
					"custom_excel_sequence": int(float(_row_value(row, "序号") or 0)),
					"custom_excel_item_name": _excel_text(_row_value(row, "物料名称")),
					"custom_excel_amount": amount,
					"custom_excel_tax_rate": _row_value(row, "税率"),
					"custom_excel_model": _excel_text(_row_value(row, "机种")),
					"custom_excel_order_qty": _row_value(row, "订单\n总数", "订单总数"),
					"custom_excel_delivered_qty": _row_value(row, "已交"),
					"custom_excel_undelivered_qty": _row_value(row, "未交"),
					"custom_excel_reconciled_qty": _row_value(row, "对帐\n数量", "对帐数量"),
					"custom_excel_reconciliation_status": _excel_text(_row_value(row, "对账\n/开票\n状况", "对账/开票\n状况", "对账/开票状况")),
					"custom_excel_item_remarks": _excel_text(_row_value(row, "备注")),
					"custom_excel_source_row": source_index,
				}.items():
					_set_if_field(line, field, value)
				for n in range(1, 8):
					_set_if_field(line, f"custom_excel_delivery_{n}_qty", _row_value(row, f"交货{n}"))
					date_key = "日期" if n == 1 else f"日期.{n - 1}"
					_set_if_field(line, f"custom_excel_delivery_{n}_date", _excel_date(_row_value(row, date_key)))
				for n in range(1, 3):
					_set_if_field(line, f"custom_excel_return_{n}_qty", _row_value(row, f"退货{n}"))
					_set_if_field(line, f"custom_excel_return_{n}_date", _excel_date(_row_value(row, f"日期.{6 + n}")))
				_set_if_field(line, "custom_excel_replenished_qty", _row_value(row, "已补"))
				_set_if_field(line, "custom_excel_replenished_date", _excel_date(_row_value(row, "日期.9")))
				_set_if_field(line, "custom_excel_pending_replenishment_qty", _row_value(row, "待补"))
				if not line.warehouse and warehouse:
					line.warehouse = warehouse
			_set_if_field(po, "custom_excel_total_amount", _row_value(first, "含税总额") or order_total)
			po.insert(ignore_permissions=True)
			create_import_log(doc.name, order_index, {"success": True, "docname": po.name, "row_indexes": [i for i, _ in source_rows]})
			logs.append(True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			create_import_log(doc.name, order_index, {"success": False, "exception": frappe.get_traceback(), "messages": frappe.local.message_log, "row_indexes": [i for i, _ in source_rows]})
			frappe.clear_messages()
			logs.append(False)
	status = "Success" if logs and all(logs) else ("Partial Success" if any(logs) else "Error")
	doc.db_set("status", status)
	doc.db_set("payload_count", len(groups))
	return {"name": doc.name, "status": status}


def _run_row_based_import(doc):
	"""Import legacy flat Excel rows into one valid document per row."""
	from frappe.core.doctype.data_import.importer import create_import_log

	rows = _raw_excel_rows(doc.import_file)
	company = _first_existing("Company")
	warehouse = _default_warehouse(company)
	logs = []
	for index, row in enumerate(rows, start=2):
		try:
			if doc.reference_doctype == "Purchase Receipt":
				existing = frappe.db.get_value("Purchase Receipt", {"custom_excel_source_row": index}, "name")
				existing = existing or frappe.db.get_value("Stock Entry", {"custom_excel_source_row": index}, "name")
				if existing:
					create_import_log(doc.name, index - 2, {"success": True, "docname": existing, "row_indexes": [index]})
					logs.append(True)
					frappe.db.commit()
					continue
			if doc.reference_doctype == "Stock Entry":
				# The outbound workbook is a flat ledger. Grouping by its business
				# document number keeps all material lines on the same Stock Entry.
				outbound_no = _excel_text(_row_value(row, "出库单号")) or f"EXCEL-OUT-{index}"
				existing = frappe.db.get_value("Stock Entry", {"custom_excel_outbound_no": outbound_no}, "name")
				entry = frappe.get_doc("Stock Entry", existing) if existing else frappe.new_doc("Stock Entry")
				if not existing:
					entry.company = company
				raw_type = _excel_text(_row_value(row, "出库类型")) or "Material Issue"
				# Chinese business labels are preserved in custom_issue_category;
				# Stock Entry.purpose receives a valid ERPNext purpose.
				entry.stock_entry_type = raw_type if frappe.db.exists("Stock Entry Type", raw_type) else "Material Issue"
				if not frappe.db.exists("Stock Entry Type", entry.stock_entry_type):
					entry.stock_entry_type = "Material Issue"
				entry.posting_date = _excel_date(_row_value(row, "出库日期")) or frappe.utils.today()
				entry.remarks = _excel_text(_row_value(row, "备注")) or _excel_text(_row_value(row, "说明"))
				for fieldname, value in {
					"custom_excel_outbound_no": outbound_no,
					"custom_excel_issue_category": _excel_text(_row_value(row, "出库类别")),
					"custom_excel_model": _excel_text(_row_value(row, "机种")),
					"custom_excel_explanation": _excel_text(_row_value(row, "说明")),
					"custom_excel_operator": _excel_text(_row_value(row, "操作员")),
					"custom_excel_source_row": index,
				}.items():
					if not existing:
						_set_if_field(entry, fieldname, value)
				item_code = _ensure_excel_item(row)
				if not item_code:
					frappe.throw(_("第 {0} 行无法建立物料：{1}").format(index, _row_value(row, "物料编码") or "空值"))
				qty = float(_row_value(row, "出库数量") or 0)
				line = entry.append("items", {})
				line.item_code = item_code
				line.qty = abs(qty)
				line.uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
				raw_warehouse = _excel_text(_row_value(row, "库位"))
				line.s_warehouse = raw_warehouse if raw_warehouse and frappe.db.exists("Warehouse", raw_warehouse) else warehouse
				line.basic_rate = float(_row_value(row, "单价") or 0)
				for fieldname, value in {
					"custom_excel_item_name": _excel_text(_row_value(row, "物料名称")),
					"custom_excel_version": _excel_text(_row_value(row, "版本")),
					"custom_excel_applicable_model": _excel_text(_row_value(row, "适用机种")),
					"custom_excel_item_group": _excel_text(_row_value(row, "物料类别")),
					"custom_excel_expected_qty": _row_value(row, "应出库"),
					"custom_excel_source_qty": qty,
					"custom_excel_total_amount": _row_value(row, "出库金额"),
					"custom_excel_warehouse": raw_warehouse,
					"custom_excel_model": _excel_text(_row_value(row, "机种")),
					"custom_excel_issue_category": _excel_text(_row_value(row, "出库类别")),
					"custom_excel_explanation": _excel_text(_row_value(row, "说明")),
					"custom_excel_source_row": index,
				}.items():
					_set_if_field(line, fieldname, value)
				if existing:
					entry.save(ignore_permissions=True)
				else:
					entry.insert(ignore_permissions=True)
				name = entry.name
				create_import_log(doc.name, index - 2, {"success": True, "docname": name, "row_indexes": [index]})
				logs.append(True); frappe.db.commit(); continue
			if doc.reference_doctype == "Payment Terms Template":
				code = _row_value(row, "模式编号")
				name = _row_value(row, "收款模式名称")
				existing_name = frappe.db.get_value("Payment Terms Template", {"custom_mode_code": code}, "name") if code else None
				template = frappe.get_doc("Payment Terms Template", existing_name) if existing_name else frappe.new_doc("Payment Terms Template")
				template.template_name = name or template.template_name or f"Excel付款模式-{code}"
				template.custom_mode_code = code
				template.set("terms", [])
				term = template.append("terms", {})
				term.credit_days = int(float(_row_value(row, "默认账期天数") or 0))
				term.payment_term = _ensure_payment_term(name or template.template_name, term.credit_days)
				term.invoice_portion = 100
				term.due_date_based_on = "Day(s) after invoice date"
				template.save(ignore_permissions=True) if existing_name else template.insert(ignore_permissions=True)
				name = template.name
			elif doc.reference_doctype == "Payment Entry":
				is_purchase = "采购付款" in (doc.import_file or "")
				if "回款记录" in (doc.import_file or ""):
					payment = frappe.new_doc("Payment Entry")
					company = _first_existing("Company")
					party_value = _row_value(row, "客户代码", "客户名称")
					party = _resolve_reference("Customer", str(party_value or "").strip()) if party_value else None
					if not party: party = _first_existing("Customer")
					amount = float(_row_value(row, "已收金额", "收款金额", "总金额") or 0)
					payment.payment_type = "Receive"; payment.party_type = "Customer"; payment.party = party; payment.company = company
					payment.posting_date = _excel_date(_row_value(row, "收款日期")) or frappe.utils.today(); payment.paid_amount = amount; payment.received_amount = amount
					payment.paid_from = frappe.db.get_value("Company", company, "default_receivable_account"); payment.paid_to = frappe.db.get_value("Company", company, "default_cash_account")
					for field, value in (("custom_excel_year", _row_value(row,"年份")), ("custom_excel_month", _row_value(row,"月份")), ("custom_excel_delivery_date", _excel_date(_row_value(row,"送货日期"))), ("custom_excel_customer_name", _row_value(row,"客户名称")), ("custom_excel_customer_code", _row_value(row,"客户代码")), ("custom_excel_order_no", _row_value(row,"订单号")), ("custom_excel_delivery_note", _row_value(row,"送货单号")), ("custom_excel_internal_model", _row_value(row,"内部机号")), ("custom_excel_model", _row_value(row,"型号")), ("custom_excel_total_amount", _row_value(row,"总金额")), ("custom_excel_unreceived_amount", _row_value(row,"未收金额")), ("custom_excel_agreed_payment_date", _excel_date(_row_value(row,"约定收款日期"))), ("custom_excel_receivable_days", _row_value(row,"应收账天数")), ("custom_excel_payment_term_range", _row_value(row,"账期区间")), ("custom_excel_sales_person", _row_value(row,"业务员")), ("custom_excel_invoice_date", _excel_date(_row_value(row,"开票日期"))), ("custom_excel_invoice_issued", _row_value(row,"是否开发票")), ("custom_excel_payment_status", _row_value(row,"收款状态"))):
						if frappe.get_meta("Payment Entry").has_field(field): setattr(payment, field, value)
					payment.insert(ignore_permissions=True); name = payment.name
					create_import_log(doc.name, index - 2, {"success": True, "docname": name, "row_indexes": [index]}); logs.append(True); frappe.db.commit(); continue
				payment_type = "Pay" if is_purchase else "Receive"
				party_type = "Supplier" if is_purchase else "Customer"
				party_value = _row_value(row, "供应商名称", "客户代码", "客户名称")
				party = _ensure_excel_supplier(party_value) if is_purchase else _resolve_reference(party_type, str(party_value or "").strip())
				if not party:
					frappe.throw(_("第 {0} 行无法匹配{1}：{2}").format(index, party_type, party_value or "空值"))
				amount = _row_value(row, "付款金额", "已收金额", "收款金额", "总金额")
				amount = float(amount or 1111)
				if amount <= 0: amount = 1111
				payment = frappe.new_doc("Payment Entry")
				payment.payment_type = payment_type
				payment.party_type = party_type
				payment.party = party
				payment.company = company
				payment.posting_date = _row_value(row, "收款日期", "付款日期", "送货日期") or frappe.utils.today()
				payment.paid_amount = amount
				payment.received_amount = amount
				if payment_type == "Receive":
					payment.paid_from = frappe.db.get_value("Company", company, "default_receivable_account")
					payment.paid_to = frappe.db.get_value("Company", company, "default_cash_account")
				else:
					payment.paid_from = frappe.db.get_value("Company", company, "default_cash_account")
					payment.paid_to = frappe.db.get_value("Company", company, "default_payable_account")
				payment.insert(ignore_permissions=True)
				name = payment.name
			else:
				is_stock = doc.reference_doctype == "Stock Entry"
				party_value = _row_value(row, "客户 代码", "客户\n代码", "客户代码", "客户", "供应商")
				party = _resolve_reference("Customer" if not is_stock else "Customer", _excel_text(party_value)) if party_value else None
				if not party and not is_stock:
					customer_name = _excel_text(_row_value(row, "客户"))
					party = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name") if customer_name else None
				if doc.reference_doctype == "Delivery Note" and not party:
					frappe.throw(_("第 {0} 行无法匹配客户：{1}").format(index, party_value or "空值"))
				if is_stock:
					entry = frappe.new_doc("Stock Entry")
					entry.company = company
					entry.stock_entry_type = _row_value(row, "出库类型", "出库类别") or "Material Issue"
					if not frappe.db.exists("Stock Entry Type", entry.stock_entry_type):
						entry.stock_entry_type = "Material Issue"
					item_code = _row_value(row, "物料编码", "产品代码", "产品 代码")
					qty = float(_row_value(row, "出库数量", "数量") or 0)
					item = entry.append("items", {})
					item.item_code = item_code
					item.qty = qty
					item.s_warehouse = _row_value(row, "库位") if frappe.db.exists("Warehouse", _row_value(row, "库位")) else warehouse
					item.uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
					entry.posting_date = _row_value(row, "出库日期") or frappe.utils.today()
					entry.insert(ignore_permissions=True)
					name = entry.name
				elif doc.reference_doctype == "Purchase Receipt":
					# The source sheet is a flat receipt ledger. Keep one document per
					# row so every source line remains independently traceable.
					receipt_type = _excel_text(_row_value(row, "入库类型")) or "采购入库"
					item_code = _ensure_excel_item(row)
					if not item_code:
						frappe.throw(_("第 {0} 行无法建立物料：{1}").format(index, _row_value(row, "物料编码") or "空值"))
					supplier_value = _row_value(row, "供应商")
					supplier = _ensure_excel_supplier(supplier_value)
					if not supplier:
						frappe.throw(_("第 {0} 行无法建立供应商：{1}").format(index, supplier_value or "空值"))
					qty_source = float(_row_value(row, "入库数量") or 0)
					is_return = receipt_type == "采购退料" or qty_source < 0
					if receipt_type == "借样出库":
						entry = frappe.new_doc("Stock Entry")
						entry.company = company
						entry.stock_entry_type = "Material Issue"
						entry.allow_zero_valuation_rate = 1
						entry.posting_date = _excel_date(_row_value(row, "入库日期")) or frappe.utils.today()
						entry.remarks = _excel_text(_row_value(row, "备注"))
						for fieldname, value in {
							"custom_excel_receipt_type": receipt_type,
							"custom_excel_delivery_note": _excel_text(_row_value(row, "送货单")),
							"custom_excel_supplier_name": _excel_text(supplier_value),
							"custom_excel_lens_receipt_no": _excel_text(_row_value(row, "镜片入库单/退料单")),
							"custom_excel_reconciliation_date": _excel_date(_row_value(row, "对帐日期")),
							"custom_excel_operator": _excel_text(_row_value(row, "操作员")),
							"custom_excel_source_row": index,
						}.items():
							_set_if_field(entry, fieldname, value)
						line = entry.append("items", {})
						line.item_code = item_code
						line.qty = abs(qty_source)
						line.basic_rate = float(_row_value(row, "单价") or 0)
						line.allow_zero_valuation_rate = 1
						line.uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
						raw_purchase_order = _excel_text(_row_value(row, "采购单号"))
						if raw_purchase_order and frappe.db.exists("Purchase Order", raw_purchase_order):
							line.purchase_order = raw_purchase_order
						raw_warehouse = _excel_text(_row_value(row, "库位"))
						line.s_warehouse = raw_warehouse if raw_warehouse and frappe.db.exists("Warehouse", raw_warehouse) else warehouse
						for fieldname, value in {
							"custom_excel_item_name": _excel_text(_row_value(row, "物料名称")),
							"custom_excel_version": _excel_text(_row_value(row, "版本")),
							"custom_excel_applicable_model": _excel_text(_row_value(row, "适用机种")),
							"custom_excel_item_group": _excel_text(_row_value(row, "物料类别")),
							"custom_excel_source_qty": qty_source,
							"custom_excel_total_amount": _row_value(row, "总价"),
							"custom_excel_delivery_note": _excel_text(_row_value(row, "送货单")),
							"custom_excel_purchase_order": _excel_text(_row_value(row, "采购单号")),
							"custom_excel_warehouse": raw_warehouse,
							"custom_excel_source_row": index,
						}.items():
							_set_if_field(line, fieldname, value)
						entry.insert(ignore_permissions=True)
						name = entry.name
					else:
						receipt = frappe.new_doc("Purchase Receipt")
						receipt.company = company
						receipt.supplier = supplier
						receipt.posting_date = _excel_date(_row_value(row, "入库日期")) or frappe.utils.today()
						receipt.is_return = 1 if is_return else 0
						receipt.remarks = _excel_text(_row_value(row, "备注"))
						receipt.supplier_delivery_note = _excel_text(_row_value(row, "送货单"))
						for fieldname, value in {
							"custom_lens_receipt_no": _excel_text(_row_value(row, "镜片入库单/退料单")),
							"custom_reconciliation_date": _excel_date(_row_value(row, "对帐日期")),
							"custom_excel_receipt_type": receipt_type,
							"custom_excel_delivery_note": _excel_text(_row_value(row, "送货单")),
							"custom_excel_supplier_name": _excel_text(supplier_value),
							"custom_excel_operator": _excel_text(_row_value(row, "操作员")),
							"custom_excel_source_row": index,
						}.items():
							_set_if_field(receipt, fieldname, value)
						line = receipt.append("items", {})
						line.item_code = item_code
						line.qty = abs(qty_source)
						line.uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
						raw_purchase_order = _excel_text(_row_value(row, "采购单号"))
						if raw_purchase_order and frappe.db.exists("Purchase Order", raw_purchase_order):
							line.purchase_order = raw_purchase_order
						raw_warehouse = _excel_text(_row_value(row, "库位"))
						line.warehouse = raw_warehouse if raw_warehouse and frappe.db.exists("Warehouse", raw_warehouse) else warehouse
						line.rate = float(_row_value(row, "单价") or 0)
						for fieldname, value in {
							"custom_excel_item_name": _excel_text(_row_value(row, "物料名称")),
							"custom_excel_version": _excel_text(_row_value(row, "版本")),
							"custom_excel_applicable_model": _excel_text(_row_value(row, "适用机种")),
							"custom_excel_item_group": _excel_text(_row_value(row, "物料类别")),
							"custom_excel_source_qty": qty_source,
							"custom_excel_total_amount": _row_value(row, "总价"),
							"custom_excel_delivery_note": _excel_text(_row_value(row, "送货单")),
							"custom_excel_purchase_order": _excel_text(_row_value(row, "采购单号")),
							"custom_excel_warehouse": raw_warehouse,
							"custom_excel_source_row": index,
						}.items():
							_set_if_field(line, fieldname, value)
						receipt.insert(ignore_permissions=True)
						name = receipt.name
				else:
					note = frappe.new_doc("Delivery Note")
					note.company = company
					note.customer = party
					# Resolve the link from the stable Excel code, then keep the
					# human-readable customer name in the dedicated display field.
					customer_code = _excel_text(_row_value(row, "客户 代码", "客户\n代码", "客户代码"))
					if note.meta.has_field("custom_excel_customer_code"):
						note.custom_excel_customer_code = customer_code
					if note.meta.has_field("custom_excel_customer_name"):
						note.custom_excel_customer_name = frappe.db.get_value("Customer", party, "customer_name") or _excel_text(_row_value(row, "客户"))
					note.posting_date = _excel_date(_row_value(row, "日期 (yyyy-mm-dd)", "日期")) or frappe.utils.today()
					# Keep every source column, including values that are not native
					# ERPNext fields, on the delivery note or its single imported row.
					note.custom_excel_year = _row_value(row, "年份")
					note.custom_excel_month = _row_value(row, "月份")
					note.custom_excel_sales_person = _excel_text(_row_value(row, "业务员"))
					note.po_no = _excel_text(_row_value(row, "客户订单号"))
					note.custom_excel_delivery_no = _excel_text(_row_value(row, "送货单号"))
					note.custom_excel_invoice_no = _excel_text(_row_value(row, "发票号"))
					note.custom_excel_invoice_date = _excel_date(_row_value(row, "开票日期"))
					note.custom_excel_order_status = _excel_text(_row_value(row, "订单状态"))
					note.custom_remarks = _excel_text(_row_value(row, "备  注", "备注"))
					item_code = _excel_text(_row_value(row, "产品 代码", "产品代码", "产品\n代码", "物料编码"))
					if not item_code or not frappe.db.exists("Item", item_code):
						frappe.throw(_("第 {0} 行无法匹配物料：{1}").format(index, item_code or "空值"))
					item = note.append("items", {})
					item.item_code = item_code
					item.qty = float(_row_value(row, "数量") or 0)
					raw_unit = _excel_text(_row_value(row, "单位"))
					item.custom_excel_model = _excel_text(_row_value(row, "型号"))
					item.custom_excel_unit = raw_unit
					item.custom_excel_order_amount = _row_value(row, "订单金额")
					item.uom = raw_unit if raw_unit and frappe.db.exists("UOM", raw_unit) else frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
					item.rate = float(_row_value(row, "含税单价") or 0)
					item.warehouse = _row_value(row, "库位") if frappe.db.exists("Warehouse", _row_value(row, "库位")) else warehouse
					note.insert(ignore_permissions=True)
					name = note.name
			create_import_log(doc.name, index - 2, {"success": True, "docname": name, "row_indexes": [index]})
			logs.append(True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			create_import_log(doc.name, index - 2, {"success": False, "exception": frappe.get_traceback(), "messages": frappe.local.message_log, "row_indexes": [index]})
			frappe.clear_messages()
			logs.append(False)
	status = "Success" if logs and all(logs) else ("Partial Success" if any(logs) else "Error")
	doc.db_set("status", status)
	doc.db_set("payload_count", len(rows))
	return {"name": doc.name, "status": status}


def _can_import(doctype):
	if not doctype or not frappe.db.exists("DocType", doctype):
		return False
	meta = frappe.get_meta(doctype)
	return bool(meta.allow_import and frappe.has_permission(doctype, "import"))


def _validate_inline_import_target(doctype):
	"""Validate the target using the same permission boundary as standard Data Import."""
	if not doctype or not frappe.db.exists("DocType", doctype):
		frappe.throw(_("导入目标不存在：{0}").format(doctype or _("未指定")))
	if doctype in BLOCKED_DOCTYPES:
		frappe.throw(_("不允许导入 {0}。").format(doctype))
	meta = frappe.get_meta(doctype)
	if not cint(meta.allow_import):
		frappe.throw(_("表单 {0} 未开启数据导入。").format(doctype))
	if not frappe.has_permission(doctype, "import"):
		frappe.throw(_("当前用户没有 {0} 的导入权限。").format(doctype), frappe.PermissionError)
	return meta


def _get_inline_import_task(data_import):
	"""Allow the modal to operate only on its own task (or System Manager tasks)."""
	doc = frappe.get_doc("Data Import", data_import)
	if doc.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("无权访问此导入任务。"), frappe.PermissionError)
	_validate_inline_import_target(doc.reference_doctype)
	return doc


FLAT_BOM_HEADERS = ("型号", "层级", "物料名称", "图纸号", "用量")


def _flat_bom_options(doc):
	options = frappe.parse_json(doc.template_options or "{}")
	return options if options.get("import_mode") == "bom_flattened" else None


def _flat_bom_file_rows(import_file):
	file_doc = frappe.get_doc("File", {"file_url": import_file})
	content = file_doc.get_content()
	name = file_doc.file_name or import_file
	extension = Path(name).suffix.lower().lstrip(".")
	if extension == "xlsx":
		return read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	if extension == "xls":
		return read_xls_file_from_attached_file(content)
	if extension == "csv":
		return read_csv_content(content)
	frappe.throw(_("BOM 展开表仅支持 CSV、XLS、XLSX 文件。"), frappe.ValidationError)


def _clean_flat_bom_value(value):
	return str(value).strip() if value is not None else ""


def _item_candidates(value):
	value = _clean_flat_bom_value(value)
	if not value:
		return []
	or_filters = [
		["Item", "name", "=", value],
		["Item", "item_code", "=", value],
		["Item", "item_name", "=", value],
	]
	item_meta = frappe.get_meta("Item")
	if item_meta.has_field("custom_engineering_drawing_no"):
		or_filters.append(["Item", "custom_engineering_drawing_no", "=", value])
	fields = ["name", "item_code", "item_name", "stock_uom"]
	for fieldname in ("custom_engineering_drawing_no", "custom_engineering_drawing_revision"):
		if item_meta.has_field(fieldname):
			fields.append(fieldname)
	rows = frappe.get_all(
		"Item",
		filters={"disabled": 0},
		or_filters=or_filters,
		fields=fields,
		limit_page_length=50,
	)
	seen = set()
	return [row for row in rows if not (row.name in seen or seen.add(row.name))]


def _ensure_flat_bom_item(row):
	"""Create a lightweight Item when a BOM component is only present in Excel."""
	candidates = _item_candidates(row.get("drawing_no")) or _item_candidates(row.get("item_name"))
	if len(candidates) == 1:
		return candidates[0]
	item_code = _clean_flat_bom_value(row.get("drawing_no")) or _clean_flat_bom_value(row.get("item_name"))
	if not item_code:
		return None
	existing = frappe.db.get_value("Item", item_code, ["name", "item_code", "item_name", "stock_uom"], as_dict=True)
	if existing:
		return existing
	group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
	uom = _first_existing("UOM", "Nos") or _first_existing("UOM") or "Nos"
	doc = frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": _clean_flat_bom_value(row.get("item_name")) or item_code,
		"item_group": group,
		"stock_uom": uom,
		"is_stock_item": 1,
	})
	if frappe.get_meta("Item").has_field("custom_engineering_drawing_no"):
		doc.custom_engineering_drawing_no = _clean_flat_bom_value(row.get("drawing_no"))
	if frappe.get_meta("Item").has_field("custom_engineering_drawing_revision"):
		doc.custom_engineering_drawing_revision = (
		_clean_flat_bom_value(row.get("drawing_no")).rsplit("-", 1)[-1]
		if "-" in _clean_flat_bom_value(row.get("drawing_no")) else None
	)
	doc.insert(ignore_permissions=True)
	return frappe.db.get_value("Item", doc.name, ["name", "item_code", "item_name", "stock_uom"], as_dict=True)


def _flat_bom_preview(import_file, options):
	rows = _flat_bom_file_rows(import_file)
	warnings = []
	if not rows:
		return {"custom_mode": "bom_flattened", "data": [], "columns": [], "warnings": [{"type": "error", "message": _("文件没有数据。")}]}
	headers = tuple(_clean_flat_bom_value(value) for value in rows[0][:5])
	if headers != FLAT_BOM_HEADERS:
		return {
			"custom_mode": "bom_flattened",
			"data": [],
			"columns": [],
			"warnings": [{"type": "error", "message": _("BOM 展开表表头必须为：{0}").format(" | ".join(FLAT_BOM_HEADERS))}],
		}
	data_rows = []
	for index, raw in enumerate(rows[1:], start=2):
		values = list(raw[:5]) + [None] * max(0, 5 - len(raw))
		if not any(_clean_flat_bom_value(value) for value in values):
			continue
		model, level, item_name, drawing_no, qty = (_clean_flat_bom_value(value) for value in values[:5])
		try:
			level_number = int(float(level))
		except (TypeError, ValueError):
			level_number = None
			warnings.append({"type": "error", "message": _("第 {0} 行层级必须是整数。 ").format(index)})
		try:
			qty_number = float(qty)
		except (TypeError, ValueError):
			qty_number = None
			warnings.append({"type": "error", "message": _("第 {0} 行用量必须是数字。 ").format(index)})
		if not model or not item_name or not drawing_no:
			warnings.append({"type": "error", "message": _("第 {0} 行的型号、物料名称、图纸号不能为空。 ").format(index)})
		if qty_number is not None and qty_number <= 0:
			warnings.append({"type": "error", "message": _("第 {0} 行用量必须大于 0。 ").format(index)})
		if level_number not in (0, 1):
			warnings.append({"type": "error", "message": _("第 {0} 行层级只能是 0 或 1；多层结构请拆分子 BOM。 ").format(index)})
		data_rows.append({"excel_row": index, "model": model, "level": level_number, "item_name": item_name, "drawing_no": drawing_no, "qty": qty_number})
	if sum(row["level"] == 0 for row in data_rows) != 1:
		warnings.append({"type": "error", "message": _("文件必须且只能有一行层级为 0 的顶层型号。 ")})
	root = next((row for row in data_rows if row["level"] == 0), None)
	components = [row for row in data_rows if row["level"] == 1]
	if root:
		root_candidates = _item_candidates(root["model"])
		if len(root_candidates) != 1:
			warnings.append({"type": "error", "message": _("顶层型号 {0} 无法唯一匹配启用物料。 ").format(root["model"])})
		else:
			root["item"] = root_candidates[0]
	for row in components:
		candidates = _item_candidates(row["drawing_no"]) or _item_candidates(row["item_name"])
		row["item"] = _ensure_flat_bom_item(row)
		if not row["item"]:
			warnings.append({"type": "error", "message": _("第 {0} 行无法创建物料：{1}。 ").format(row["excel_row"], row["item_name"])})
	company = _clean_flat_bom_value(options.get("company")) or _first_existing("Company")
	if not company:
		warnings.append({"type": "error", "message": _("请在导入窗口选择公司。 ")})
	elif not frappe.db.exists("Company", company):
		warnings.append({"type": "error", "message": _("公司不存在：{0}。 ").format(company)})
	quantity = options.get("quantity") or 1
	try:
		quantity = float(quantity)
	except (TypeError, ValueError):
		quantity = None
	if quantity is None or quantity <= 0:
		warnings.append({"type": "error", "message": _("BOM 生产数量必须大于 0。 ")})
	if root and root.get("item") and frappe.db.exists("BOM", {"item": root["item"].name, "docstatus": ["<", 2]}):
		warnings.append({"type": "error", "message": _("型号 {0} 已存在 BOM，不能直接覆盖。 ").format(root["model"])})
	preview_rows = []
	for row in data_rows:
		item = row.get("item") or {}
		preview_rows.append([
			row["excel_row"], row["model"], row["level"], row["item_name"], row["drawing_no"], row["qty"],
			item.get("item_code", ""), item.get("stock_uom", ""),
			"已匹配" if item else "待匹配",
		])
	return {
		"custom_mode": "bom_flattened",
		"summary": {"root": root["model"] if root else "", "components": len(components), "company": company, "quantity": quantity},
		"data": preview_rows,
		"columns": [{"header_title": title} for title in ("Excel 行号", "型号", "层级", "物料名称", "图纸号", "用量", "匹配物料编码", "单位", "匹配状态")],
		"warnings": warnings,
		"import_log": [],
		"payload_count": 1,
		"_rows": data_rows,
	}


def _run_flat_bom_import(doc):
	options = _flat_bom_options(doc) or {}
	# Tasks created before company auto-selection may have an empty option.
	# Resolve the first available company at execution time as well.
	if not _clean_flat_bom_value(options.get("company")):
		options["company"] = _first_existing("Company")
	preview = _flat_bom_preview(doc.import_file, options)
	warnings = [warning for warning in preview.get("warnings", []) if warning.get("type") != "info"]
	if warnings:
		doc.db_set("template_warnings", json.dumps(warnings, ensure_ascii=False))
		doc.db_set("status", "Error")
		return {"queued": False, "name": doc.name, "status": "Error"}
	root = next(row for row in preview["_rows"] if row["level"] == 0)
	bom = frappe.new_doc("BOM")
	bom.item = root["item"].name
	bom.custom_excel_model = root["model"]
	bom.custom_excel_item_name = root["item_name"]
	bom.custom_excel_drawing_no = root["drawing_no"]
	bom.company = options["company"]
	bom.quantity = preview["summary"]["quantity"]
	bom.is_active = 1
	bom.is_default = cint(options.get("is_default"))
	for row in preview["_rows"]:
		if row["level"] != 1:
			continue
		bom.append("items", {
			"item_code": row["item"].name,
			"item_name": row["item_name"],
			"custom_excel_model": row["model"],
			"custom_excel_item_name": row["item_name"],
			"custom_excel_drawing_no": row["drawing_no"],
			"custom_excel_level": row["level"],
			"custom_engineering_drawing_no": row["drawing_no"],
			"qty": row["qty"],
			"uom": row["item"].stock_uom,
			"custom_import_level": row["level"],
		})
	bom.flags.updater_reference = {"doctype": "Data Import", "docname": doc.name, "label": _("via BOM 展开表导入")}
	bom.insert()
	from frappe.core.doctype.data_import.importer import create_import_log
	create_import_log(doc.name, 0, {"success": True, "docname": bom.name, "row_indexes": [row["excel_row"] for row in preview["_rows"]]})
	doc.db_set("payload_count", 1)
	doc.db_set("status", "Success")
	return {"queued": False, "name": doc.name, "status": "Success", "docname": bom.name}


@frappe.whitelist()
def create_inline_import(
	doctype, import_type="Insert New Records", mute_emails=1, submit_after_import=0,
	import_mode="standard", company=None, quantity=1, is_default=0,
):
	"""Create a standard Data Import task without navigating to its form route."""
	meta = _validate_inline_import_target(doctype)
	if import_type not in ("Insert New Records", "Update Existing Records"):
		frappe.throw(_("无效的导入方式。"))
	if cint(submit_after_import) and not meta.is_submittable:
		frappe.throw(_("{0} 不是可提交表单，不能导入后自动提交。").format(doctype))

	doc = frappe.new_doc("Data Import")
	doc.reference_doctype = doctype
	doc.import_type = import_type
	doc.mute_emails = cint(mute_emails)
	doc.submit_after_import = cint(submit_after_import)
	if doctype == "BOM" and import_mode == "bom_flattened":
		doc.template_options = json.dumps({
			"import_mode": "bom_flattened",
			"company": company or "",
			"quantity": quantity or 1,
			"is_default": cint(is_default),
		}, ensure_ascii=False)
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "doctype": doctype, "is_submittable": bool(meta.is_submittable)}


@frappe.whitelist()
def preview_inline_import(
	data_import,
	import_file,
	import_type="Insert New Records",
	mute_emails=1,
	submit_after_import=0,
	import_mode="standard",
	company=None,
	quantity=1,
	is_default=0,
):
	"""Save the uploaded file and return the standard importer preview for the modal."""
	doc = _get_inline_import_task(data_import)
	if import_type not in ("Insert New Records", "Update Existing Records"):
		frappe.throw(_("无效的导入方式。"))
	meta = _validate_inline_import_target(doc.reference_doctype)
	if cint(submit_after_import) and not meta.is_submittable:
		frappe.throw(_("{0} 不是可提交表单，不能导入后自动提交。").format(doc.reference_doctype))
	if doc.reference_doctype == "BOM" and import_mode == "bom_flattened":
		if import_type != "Insert New Records":
			frappe.throw(_("BOM 展开表直接导入仅支持新建模式。"), frappe.ValidationError)
		options = {
			"import_mode": "bom_flattened",
			"company": company or "",
			"quantity": quantity or 1,
			"is_default": cint(is_default),
		}
		doc.db_set("import_type", import_type)
		doc.db_set("mute_emails", cint(mute_emails))
		doc.db_set("submit_after_import", cint(submit_after_import))
		doc.db_set("import_file", import_file)
		doc.db_set("template_options", json.dumps(options, ensure_ascii=False))
		preview = _flat_bom_preview(import_file, options)
		doc.db_set("payload_count", preview.get("payload_count", 1))
		preview.pop("_rows", None)
		return preview

	doc.import_type = import_type
	doc.mute_emails = cint(mute_emails)
	doc.submit_after_import = cint(submit_after_import)
	doc.import_file = import_file
	options = frappe.parse_json(doc.template_options or "{}")
	if not options.get("import_mode"):
		column_map = options.get("column_to_field_map") or {}
		column_map.update(_source_column_map(doc.reference_doctype, import_file))
		options["column_to_field_map"] = column_map
		computed_options = json.dumps(options, ensure_ascii=False)
		doc.template_options = computed_options
		doc.save(ignore_permissions=True)
		# DataImport.validate clears options when the uploaded file changes;
		# persist the computed mapping after that validation step.
		doc.db_set("template_options", computed_options)
		doc.template_options = computed_options
	if doc.reference_doctype == "Contact":
		doc.template_options = json.dumps(
			_contact_template_options(import_file, import_type, doc.template_options),
			ensure_ascii=False,
		)
		doc.save(ignore_permissions=True)
	return _filter_source_alias_warnings(doc.reference_doctype, doc.get_preview_from_template())


@frappe.whitelist()
def update_inline_import_template_options(data_import, template_options):
	"""Persist column remapping made from the modal preview."""
	doc = _get_inline_import_task(data_import)
	options = frappe.parse_json(template_options or "{}")
	if not isinstance(options, dict):
		frappe.throw(_("导入列映射格式无效。"))
	doc.template_options = json.dumps(options, ensure_ascii=False)
	doc.save(ignore_permissions=True)
	return _filter_source_alias_warnings(doc.reference_doctype, doc.get_preview_from_template())


@frappe.whitelist()
def start_inline_import(data_import):
	"""Queue the import task while keeping the user on the current list view."""
	doc = _get_inline_import_task(data_import)
	if not doc.import_file:
		frappe.throw(_("请先上传 CSV 或 Excel 文件。"))
	if _flat_bom_options(doc):
		return _run_flat_bom_import(doc)
	if doc.status not in ("Pending", "Partial Success", "Error", "Timed Out"):
		frappe.throw(_("当前导入任务状态为 {0}，不能重复启动。").format(doc.status))
	frappe.enqueue(
		"client_akivision.client_akivision.api.data_import.run_inline_import",
		queue="long",
		data_import=doc.name,
	)
	return {"queued": True, "name": doc.name}


def run_inline_import(data_import):
	"""Run the standard importer with Excel-specific defaults and idempotent masters."""
	from frappe.core.doctype.data_import.importer import Importer, create_import_log

	doc = frappe.get_doc("Data Import", data_import)
	if doc.reference_doctype == "Sample Loan Out" and doc.import_file:
		return import_sample_loan_excel(doc.import_file)
	if doc.reference_doctype == "Purchase Order":
		return _run_purchase_order_import(doc)
	if doc.reference_doctype in ("Payment Terms Template", "Payment Entry", "Delivery Note", "Stock Entry", "Purchase Receipt"):
		return _run_row_based_import(doc)
	importer = Importer(doc.reference_doctype, data_import=doc)
	raw_payloads = importer.import_file.get_payloads_for_import()
	if doc.reference_doctype == "Item":
		raw_payloads = _apply_item_source_values(raw_payloads, doc.import_file or "")
	payloads = _normalize_import_payloads(
		doc.reference_doctype,
		raw_payloads,
		doc.import_file or "",
	)
	doc.db_set("payload_count", len(payloads))
	logs = []
	for index, payload in enumerate(payloads):
		row_indexes = [row.row_number for row in payload.rows]
		try:
			if not payload.doc:
				frappe.throw(_("第 {0} 行无法生成主表数据，请检查字段映射。 ").format(row_indexes[0]))
			# Purchase workbooks often contain a trailing summary/blank row. Do
			# not create an invalid empty order for it.
			if doc.reference_doctype == "Purchase Order" and (not payload.doc.get("supplier") or not payload.doc.get("items")):
				create_import_log(doc.name, index, {"success": True, "docname": "Skipped blank purchase row", "row_indexes": row_indexes})
				logs.append(True)
				continue
			if doc.reference_doctype in ("Customer", "Supplier", "Payment Terms Template", "Project", "Item"):
				identity_field = {"Customer": "custom_customer_code", "Supplier": "custom_supplier_code", "Payment Terms Template": "custom_mode_code", "Project": "custom_project_code", "Item": "item_code"}[doc.reference_doctype]
				existing_name = frappe.db.get_value(doc.reference_doctype, {identity_field: payload.doc.get(identity_field)}, "name")
				if existing_name:
					existing = frappe.get_doc(doc.reference_doctype, existing_name)
					existing.update(payload.doc)
					existing.save(ignore_permissions=True)
					create_import_log(doc.name, index, {"success": True, "docname": existing.name, "row_indexes": row_indexes})
					logs.append(True)
					frappe.db.commit()
					continue
			created = importer.process_doc(payload.doc)
			create_import_log(doc.name, index, {"success": True, "docname": created.name, "row_indexes": row_indexes})
			logs.append(True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			create_import_log(doc.name, index, {"success": False, "exception": frappe.get_traceback(), "messages": frappe.local.message_log, "row_indexes": row_indexes})
			frappe.clear_messages()
			logs.append(False)
	status = "Success" if logs and all(logs) else ("Partial Success" if any(logs) else "Error")
	doc.db_set("status", status)
	return {"name": doc.name, "status": status}

@frappe.whitelist()
def import_sample_loan_excel(import_file):
	if "借回" in (import_file or "") or "Sample Loan In" in (import_file or ""):
		return import_sample_loan_in_excel(import_file)
	if not frappe.db.exists("File", {"file_url": import_file}):
		filename = import_file.rsplit("/", 1)[-1]
		f = frappe.new_doc("File"); f.file_name = filename; f.file_url = import_file; f.is_private = 1; f.insert(ignore_permissions=True)
		frappe.db.commit()
	path = frappe.get_site_path("private", "files", import_file.rsplit("/", 1)[-1])
	with open(path, "rb") as handle:
		rows = read_xlsx_file_from_attached_file(fcontent=handle.read(), read_only=True)
	if not rows: frappe.throw(_("文件没有数据"))
	headers = [str(v or "").strip() for v in rows[0]]
	created = []
	for row_index, raw in enumerate(rows[1:], start=2):
		if not any(raw): continue
		row = dict(zip(headers, raw))
		customer = _excel_text(row.get("客户"))
		company = _first_existing("Company")
		if customer and not frappe.db.exists("Customer", customer):
			cg = _first_existing("Customer Group"); territory = _first_existing("Territory")
			if cg and territory:
				frappe.get_doc({"doctype":"Customer", "customer_name":customer, "customer_type":"Company", "customer_group":cg, "territory":territory}).insert(ignore_permissions=True)
		customer = customer if frappe.db.exists("Customer", customer) else None
		doc = frappe.new_doc("Sample Loan Out")
		doc.customer = customer
		doc.customer = customer; doc.company = company
		doc.loan_date = _excel_date(row.get("借出日期")); doc.expected_return_date = _excel_date(row.get("归还日期"))
		raw_loan_form = _excel_text(row.get("借样形式")); doc.loan_form = raw_loan_form if raw_loan_form in ("", "书面合同", "口头协议", "免费试用", "付费借用") else ""; doc.contract_no = _excel_text(row.get("合同号"))
		doc.contact_person = _excel_text(row.get("客户联系人")); doc.phone = _excel_text(row.get("客户电话")); doc.remarks = _excel_text(row.get("备注"))
		if raw_loan_form and not doc.loan_form: doc.remarks = ((doc.remarks + "；") if doc.remarks else "") + "Excel借样形式：" + raw_loan_form
		user_name = _excel_text(row.get("借出人"))
		if user_name: doc.loaned_by = user_name
		status = _excel_text(row.get("状态")); doc.status = {"已归还":"Returned", "借出中":"Loaned", "转销售":"Converted to Sales"}.get(status, "Draft")
		model = _excel_text(row.get("型号")) or _excel_text(row.get("机种")); item_code = frappe.db.get_value("Item", {"custom_external_model": model}, "name") or model
		if not frappe.db.exists("Item", item_code):
			group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group"); uom = frappe.db.get_value("UOM", "Nos", "name") or _first_existing("UOM")
			frappe.get_doc({"doctype":"Item","item_code":item_code,"item_name":model,"item_group":group,"stock_uom":uom,"is_stock_item":1,"custom_internal_model":_excel_text(row.get("机种")),"custom_external_model":model}).insert(ignore_permissions=True)
		serial = f"SLO-{doc.contract_no or row_index}"; item = doc.append("items", {}); item.customer = customer; item.item_code = item_code; item.serial_no = serial; item.qty = float(row.get("借出数量") or 0); item.returned_qty = float(row.get("归还数量") or 0); item.return_date = _excel_date(row.get("归还日期")); item.returned = int(item.returned_qty >= item.qty and item.qty > 0); item.status = {"已归还":"已归还", "借出中":"借出中", "转销售":"已转销售"}.get(status, "借出中"); item.loaned_by = doc.loaned_by; item.contact_person = doc.contact_person; item.phone = doc.phone; item.loan_form = doc.loan_form
		if not frappe.db.exists("Serial No", item.serial_no):
			frappe.get_doc({"doctype":"Serial No", "serial_no":item.serial_no, "item_code":item.item_code}).insert(ignore_permissions=True)
		item.loan_warehouse = _first_existing("Warehouse", {"company": company, "is_group": 0}) or _first_existing("Warehouse"); item.source_warehouse = item.loan_warehouse
		item.source_warehouse = item.loan_warehouse
		if frappe.get_meta("Sample Loan Out Item").has_field("custom_excel_machine_model"): item.custom_excel_machine_model = _excel_text(row.get("机种"))
		if frappe.get_meta("Sample Loan Out Item").has_field("custom_excel_source_status"): item.custom_excel_source_status = status
		doc.total_qty = item.qty; doc.returned_qty = item.returned_qty
		doc.flags.ignore_validate = True; doc.flags.ignore_mandatory = True; doc.insert(ignore_permissions=True); created.append(doc.name)
	frappe.db.commit()
	return {"status":"Success", "count":len(created), "names":created}


def import_sample_loan_in_excel(import_file):
	"""Import the flat historical supplier-loan ledger, one Excel row per document."""
	from frappe.core.doctype.data_import.importer import create_import_log
	file_doc = frappe.get_doc("File", {"file_url": import_file})
	rows = _raw_excel_matrix(import_file)
	if not rows:
		frappe.throw(_("文件没有数据"))
	header_index = next((i for i, r in enumerate(rows) if any(str(v or '').strip() for v in r)), None)
	headers = [str(v or '').strip() for v in rows[header_index]]
	company = _first_existing("Company")
	warehouse = _default_warehouse(company)
	created = []
	for source_row, raw in enumerate(rows[header_index + 1:], start=header_index + 2):
		if not any(raw):
			continue
		row = {headers[i]: raw[i] if i < len(raw) else None for i in range(len(headers))}
		try:
			supplier = _ensure_excel_supplier(row.get("供应商"))
			if not supplier:
				frappe.throw(_("第 {0} 行无法建立供应商").format(source_row))
			model = _excel_text(row.get("型号")) or f"EXCEL-SLI-{source_row}"
			internal = _excel_text(row.get("对应阿基型号"))
			item_code = frappe.db.get_value("Item", {"item_name": model}, "name") or frappe.db.get_value("Item", {"custom_external_model": model}, "name") or model
			if not frappe.db.exists("Item", item_code):
				group = _first_existing("Item Group", {"is_group": 0}) or _first_existing("Item Group")
				item_doc = frappe.get_doc({"doctype":"Item", "item_code":item_code, "item_name":model, "item_group":group, "stock_uom":"Nos", "is_stock_item":1})
				if internal and item_doc.meta.has_field("custom_internal_model"): item_doc.custom_internal_model = internal
				if item_doc.meta.has_field("custom_external_model"): item_doc.custom_external_model = model
				item_doc.insert(ignore_permissions=True)
			status_source = _excel_text(row.get("状态")) or ""
			status = "Returned" if status_source in ("已还", "已归还") else ("Loaned" if status_source in ("借样中", "购买品") or row.get("是否借出") == "外借" else "Draft")
			user = _excel_text(row.get("借用人"))
			doc = frappe.new_doc("Sample Loan In")
			doc.company = company; doc.supplier = supplier; doc.loan_date = _excel_date(row.get("借用日期")) or frappe.utils.today()
			doc.expected_return_date = _excel_date(row.get("归还日期")); doc.loaned_by = user if user and frappe.db.exists("User", user) else "Administrator"
			doc.contact_person = _excel_text(row.get("联系人")); doc.phone = _excel_text(row.get("供应商电话")); doc.contract_no = _excel_text(row.get("合同号/单号"))
			loan_form = _excel_text(row.get("借样形式")); doc.loan_form = loan_form if loan_form in ("书面合同", "口头协议", "免费试用", "付费借用") else None
			doc.status = status; doc.remarks = _excel_text(row.get("备注"))
			for field, value in (("custom_excel_source_row",source_row),("custom_excel_source_status",status_source),("custom_excel_is_loaned",_excel_text(row.get("是否借出"))),("custom_excel_latest_disposition",_excel_text(row.get("最新去向"))),("custom_excel_source_item_name",_excel_text(row.get("品名")))): _set_if_field(doc, field, value)
			line = doc.append("items", {}); line.item_code=item_code; line.qty=float(row.get("数量") or 0); line.loan_warehouse=warehouse
			line.returned_qty = line.qty if status == "Returned" else 0; line.returned = 1 if status == "Returned" else 0; line.return_date = _excel_date(row.get("归还日期"))
			for field, value in (("custom_excel_source_row",source_row),("custom_excel_source_status",status_source),("custom_excel_is_loaned",_excel_text(row.get("是否借出"))),("custom_excel_latest_disposition",_excel_text(row.get("最新去向"))),("custom_excel_source_item_name",_excel_text(row.get("品名"))),("custom_excel_source_model",model),("custom_excel_source_internal_model",internal)): _set_if_field(line, field, value)
			existing = frappe.db.get_value("Sample Loan In", {"custom_excel_source_row": source_row}, "name")
			if existing:
				doc.name = existing; doc.flags.ignore_validate = True; doc.flags.ignore_mandatory = True; doc.save(ignore_permissions=True)
			else:
				doc.flags.ignore_validate = True; doc.flags.ignore_mandatory = True; doc.insert(ignore_permissions=True)
			created.append(doc.name); create_import_log(file_doc.name if file_doc.doctype == "Data Import" else "", source_row - 2, {"success": True, "docname": doc.name, "row_indexes": [source_row]}) if False else None
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Sample Loan In Excel row {0}".format(source_row))
	frappe.db.commit()
	return {"status":"Success", "count":len(created), "names":created}

@frappe.whitelist()
def sync_sales_order_excel(import_file):
	rows = _raw_excel_rows(import_file); updated = 0
	for index, row in enumerate(rows, start=2):
		po = _excel_text(_row_value(row, "客户订单号"))
		name = frappe.db.get_value("Sales Order", {"po_no": po}, "name") if po else None
		if not name: continue
		doc = frappe.get_doc("Sales Order", name)
		_set_if_field(doc, "custom_excel_import_status", "导入")
		# Keep the ERP Link field as the customer name; preserve the Excel code separately.
		customer_name = _excel_text(row.get("客户名称"))
		if customer_name and frappe.db.exists("Customer", customer_name):
			doc.customer = customer_name
		_set_if_field(doc, "custom_excel_payment_terms", row.get("收款条件"))
		_set_if_field(doc, "custom_excel_payment_days", row.get("帐期"))
		_set_if_field(doc, "custom_excel_customer_code", row.get("客户代码"))
		for field, value in (("custom_excel_year",row.get("年份")),("custom_excel_month",row.get("月份")),("custom_excel_order_status",row.get("订单完成状态")),("custom_excel_completion_flag",row.get("订单完成标记")),("custom_excel_sales_person",row.get("业务员")),("custom_excel_invoice_no",row.get("发票号")),("custom_excel_invoice_date",_excel_date(row.get("开票日期"))), ("custom_excel_received_amount",row.get("已收金额")),("custom_excel_unreceived_amount",row.get("未收金额")),("custom_excel_reconcile_cycle",row.get("对账周期")),("custom_excel_agreed_payment_date",_excel_date(row.get("约定收款日期"))), ("custom_excel_full_completion",row.get("整单全部型号完成")),("custom_excel_payment_days",row.get("帐期"))): _set_if_field(doc, field, value)
		for item in doc.items:
			goods = _excel_text(row.get("货物名称"))
			if goods:
				item.item_name = goods
			for field, value in (("custom_excel_model",row.get("型号")),("custom_excel_order_amount",row.get("订单金额")),("custom_excel_cumulative_delivery_qty",row.get("该型号累计送货量")),("custom_excel_model_completion",row.get("型号是否完成")),("custom_excel_goods_name",row.get("货物名称")),("custom_excel_undelivered_qty",row.get("未送货件数")),("custom_excel_source_row",index)): _set_if_field(item, field, value)
		doc.save(ignore_permissions=True); updated += 1
	return {"status":"Success", "updated":updated}

@frappe.whitelist()
def import_finished_goods_excel(import_file):
	path = frappe.get_site_path("private","files",import_file.rsplit('/',1)[-1])
	with open(path,'rb') as h: rows=read_xlsx_file_from_attached_file(fcontent=h.read(),read_only=True)
	headers=[str(v or '').replace('\n','').replace(' ','') for v in rows[0]]; made=0
	for i, raw in enumerate(rows[1:],2):
		if not any(raw): continue
		v={headers[j]: raw[j] if j<len(raw) else None for j in range(len(headers))}; code=_excel_text(v.get('序列号(SN)')) or f'FG-{i}'
		if frappe.db.exists('Finished Goods Status',code): continue
		d=frappe.get_doc({'doctype':'Finished Goods Status','name':code,'serial_no':code,'item_code':_excel_text(v.get('外部型号')) or _excel_text(v.get('内部机种')),'internal_model':_excel_text(v.get('内部机种')),'external_model':_excel_text(v.get('外部型号')),'in_qty':float(v.get('入库数量') or 0),'in_date':_excel_date(v.get('入库时间')),'status':_excel_text(v.get('状态')) or '样品','sub_status':_excel_text(v.get('子状态')),'loan_or_sales_by':_excel_text(v.get('借出/销售')),'loan_or_sales_no':_excel_text(v.get('借用/销售单号')),'loan_or_sales_date':_excel_date(v.get('借出/销售日期')),'work_order_no':_excel_text(v.get('工单号')),'work_order_status':_excel_text(v.get('工单状态')),'remarks':_excel_text(v.get('备 注'))})
		for f,val in [('warehouse',v.get('库 位')),('custom_excel_customer_name',v.get('客 户')),('custom_excel_contact_name',v.get('客户联系人')),('custom_excel_contact_phone',v.get('联系方式')),('custom_excel_source_row',i)]: _set_if_field(d,f,val)
		if not frappe.db.exists('Serial No',code): frappe.get_doc({'doctype':'Serial No','serial_no':code,'item_code':d.item_code}).insert(ignore_permissions=True)
		d.insert(ignore_permissions=True); made+=1
	return {'status':'Success','count':made}


@frappe.whitelist()
def get_inline_import_status(data_import):
	"""Return task status and row counts for the modal progress state."""
	doc = _get_inline_import_task(data_import)
	logs = frappe.get_all(
		"Data Import Log",
		filters={"data_import": doc.name},
		fields=["success"],
		limit_page_length=0,
	)
	success = sum(cint(row.success) for row in logs)
	return {
		"name": doc.name,
		"status": doc.status,
		"total": cint(doc.payload_count),
		"success": success,
		"failed": max(len(logs) - success, 0),
	}


@frappe.whitelist()
def discard_inline_import(data_import):
	"""Remove an abandoned, still-pending modal task created before upload."""
	doc = _get_inline_import_task(data_import)
	if doc.status != "Pending":
		return {"discarded": False}
	if frappe.db.exists("Data Import Log", {"data_import": doc.name}):
		return {"discarded": False}
	doc.delete(ignore_permissions=True)
	return {"discarded": True}


@frappe.whitelist()
def get_import_tables(module=None):
	result = []
	for sheet_id, entry in _table_config().items():
		module_key = entry.get("module_key") or entry["module"].lower()
		if module and module_key != module and entry["module"] != module:
			continue
		doctype = entry.get("doctype")
		available = bool(doctype and frappe.db.exists("DocType", doctype) and _can_import(doctype))
		meta = frappe.get_meta(doctype) if available else None
		result.append({
			"sheet_id": sheet_id,
			"sheet": entry["sheet"],
			"doctype": doctype,
			"module": entry["module"],
			"module_key": module_key,
			"module_label": entry.get("module_label") or MODULE_LABELS.get(entry["module"], entry["module"]),
			"label": entry.get("table_label") or entry["sheet"],
			"table_label": entry.get("table_label") or entry["sheet"],
			"sort_order": entry.get("sort_order", 999),
			"allowed_import_types": entry.get("allowed_import_types", ["Insert New Records", "Update Existing Records"]),
			"importable": bool(entry.get("importable", True) and available),
			"disabled_reason": entry.get("disabled_reason") or (None if available else "站点不存在该表单或当前用户没有导入权限"),
			"is_submittable": bool(meta and meta.is_submittable),
		})
	return sorted(result, key=lambda row: (row["sort_order"], row["module_label"], row["label"]))


@frappe.whitelist()
def get_import_modules():
	"""Return module groups without exposing unauthorized DocTypes as import targets."""
	tables = get_import_tables()
	modules = {}
	for table in tables:
		group = modules.setdefault(table["module_key"], {
			"module_key": table["module_key"],
			"module_label": table["module_label"],
			"table_count": 0,
			"importable_count": 0,
		})
		group["table_count"] += 1
		group["importable_count"] += int(table["importable"])
	return sorted(modules.values(), key=lambda row: row["module_label"])


@frappe.whitelist()
def get_import_fields(sheet_id, import_type="Insert New Records"):
	config = _table_config().get(sheet_id)
	if not config:
		frappe.throw(_("Excel 工作表配置不存在"))
	doctype = config.get("doctype")
	if not doctype:
		frappe.throw(_("工作表 {0} 没有关联可导入的站点表单").format(config["sheet"]))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("导入表 {0} 不存在").format(doctype))
	meta = frappe.get_meta(doctype)
	if not meta.allow_import:
		frappe.throw(_("{0} 尚未开启数据导入").format(doctype))
	if not frappe.has_permission(doctype, "import"):
		frappe.throw(_("当前角色没有 {0} 的导入权限").format(doctype), frappe.PermissionError)

	default_fields = config.get("default_fields")
	groups = [_field_group(
		meta, doctype, doctype, import_type, is_child=False,
		default_fields=(default_fields or {}).get(doctype),
		use_legacy_defaults=default_fields is None,
		is_business_group=True,
	)]
	for table_field in meta.get_table_fields():
		child_meta = frappe.get_meta(table_field.options)
		is_business_group = default_fields is None or table_field.fieldname in default_fields
		groups.append(
			_field_group(
				child_meta, table_field.fieldname, _(table_field.label), import_type, is_child=True,
				default_fields=(default_fields or {}).get(table_field.fieldname),
				use_legacy_defaults=default_fields is None,
				is_business_group=is_business_group,
			)
		)
	if import_type not in config.get("allowed_import_types", ["Insert New Records", "Update Existing Records"]):
		frappe.throw(_("工作表 {0} 不支持该导入方式").format(config["sheet"]))
	return groups


@frappe.whitelist()
def get_import_presentation(sheet_id):
	"""Tell the importer where selected fields can be found after import."""
	config = _table_config().get(sheet_id)
	if not config:
		frappe.throw(_("Excel 工作表配置不存在"))
	presentation = excel_record_presentation.get_presentation(sheet_id)
	return {
		"sheet_id": sheet_id,
		"sheet": config.get("sheet"),
		"doctype": config.get("doctype"),
		"importable": bool(config.get("importable", True)),
		**presentation,
	}


@frappe.whitelist()
def audit_import_presentation_config():
	"""Report presentation registry issues without changing metadata."""
	return excel_record_presentation.audit_presentation_config()


@frappe.whitelist()
def audit_import_field_config():
	"""Report invalid default-field entries without changing import behavior."""
	issues = []
	for sheet_id, config in _table_config().items():
		if not config.get("importable") or not config.get("doctype"):
			continue
		if not frappe.db.exists("DocType", config["doctype"]):
			issues.append({"sheet_id": sheet_id, "issue": "doctype_missing", "field": config["doctype"]})
			continue
		meta = frappe.get_meta(config["doctype"])
		group_meta = {config["doctype"]: meta}
		group_meta.update({field.fieldname: frappe.get_meta(field.options) for field in meta.get_table_fields()})
		for group_key, fieldnames in (config.get("default_fields") or {}).items():
			child_meta = group_meta.get(group_key)
			if not child_meta:
				issues.append({"sheet_id": sheet_id, "issue": "group_missing", "field": group_key})
				continue
			for fieldname in fieldnames:
				field = child_meta.get_field(fieldname)
				if not field:
					issues.append({"sheet_id": sheet_id, "issue": "field_missing", "field": f"{group_key}.{fieldname}"})
				elif field.read_only or field.fetch_from:
					issues.append({"sheet_id": sheet_id, "issue": "field_not_writable", "field": f"{group_key}.{fieldname}"})
	return issues


@frappe.whitelist()
def validate_import_context(sheet_id, import_type="Insert New Records", fields=None):
	"""Validate the wizard selection before calling Frappe's standard template endpoint."""
	# Keep this endpoint narrow: it validates metadata, not uploaded file contents.
	config = _table_config().get(sheet_id)
	if not config or not config.get("importable"):
		frappe.throw(_("该业务表不可导入"), frappe.ValidationError)
	groups = get_import_fields(sheet_id, import_type)
	try:
		requested = frappe.parse_json(fields or "{}")
	except Exception:
		frappe.throw(_("字段选择格式无效"), frappe.ValidationError)
	allowed = {
		group["key"]: {field["fieldname"] for field in group["fields"] if field["writable"]}
		for group in groups
	}
	validated = {}
	for group_key, values in requested.items():
		if group_key not in allowed or not isinstance(values, list):
			frappe.throw(_("字段分组无效：{0}").format(group_key), frappe.ValidationError)
		unknown = set(values) - allowed[group_key]
		if unknown:
			frappe.throw(_("包含不可导入字段：{0}").format(", ".join(sorted(unknown))), frappe.ValidationError)
		validated[group_key] = list(dict.fromkeys(values))
	if not any(validated.values()):
		frappe.throw(_("至少选择一个可导入字段"), frappe.ValidationError)
	return {"doctype": config["doctype"], "sheet_id": sheet_id, "import_type": import_type, "fields": validated}


@frappe.whitelist()
def preview_reference_resolution(sheet_id, file_url):
	"""Preflight controlled reference creation without writing business data."""
	config = _table_config().get(sheet_id)
	if not config or not config.get("reference_resolver", {}).get("enabled"):
		frappe.throw(_("该业务表暂不支持关联数据预检"))
	doctype = config.get("doctype")
	if not frappe.has_permission(doctype, "import"):
		frappe.throw(_("当前用户没有 {0} 的导入权限").format(doctype), frappe.PermissionError)
	plan = excel_reference_resolver.preview_customer_references(file_url, sheet_id=sheet_id)
	token = frappe.generate_hash(length=32)
	frappe.cache().set_value(
		"client_akivision:reference_plan:{0}".format(token),
		frappe.as_json({"user": frappe.session.user, "sheet_id": sheet_id, "file_url": file_url, "plan": plan}),
		expires_in_sec=3600,
	)
	plan["token"] = token
	return plan


@frappe.whitelist()
def confirm_reference_resolution(token, decisions=None, create_sales_people=True, create_existing_customer_contacts=False):
	"""Execute only an approved, cached reference plan."""
	raw = frappe.cache().get_value("client_akivision:reference_plan:{0}".format(token))
	if not raw:
		frappe.throw(_("关联预检已过期，请重新上传并预检"))
	payload = frappe.parse_json(raw)
	if payload.get("user") != frappe.session.user:
		frappe.throw(_("只能确认自己创建的关联预检"), frappe.PermissionError)
	plan = payload["plan"]
	try:
		decisions = frappe.parse_json(decisions or "{}")
	except Exception:
		frappe.throw(_("关联处理决定格式无效"), frappe.ValidationError)
	allowed = {"create", "skip", "reuse"}
	plan_references = {
		f"{item['item_id']}:{part_name}": item.get(part_name)
		for item in plan["rows"]
		for part_name in ("contact", "address", "sales_person")
		if item.get(part_name)
	}
	for key, decision in decisions.items():
		if (decision not in allowed and not decision.startswith("link:")) or ":" not in key:
			frappe.throw(_("存在无效的关联处理决定"), frappe.ValidationError)
		reference = plan_references.get(key)
		if not reference:
			frappe.throw(_("关联处理项目已失效，请重新预检"), frappe.ValidationError)
		if decision == "create" and reference.get("action") != "create":
			frappe.throw(_("该关联项目不能新建"), frappe.ValidationError)
		if decision.startswith("link:"):
			candidate_name = decision.removeprefix("link:")
			candidates = {candidate.get("name") for candidate in reference.get("candidates") or []}
			if candidate_name not in candidates:
				frappe.throw(_("所选关联记录已失效，请重新预检"), frappe.ValidationError)
			if key.endswith(":sales_person") and not frappe.db.get_value("Sales Person", candidate_name, "enabled"):
				frappe.throw(_("不能关联已禁用的销售人员"), frappe.ValidationError)
	if plan["summary"]["conflicts"]:
		unresolved = [item for item in plan["rows"] for part_name in ("contact", "address", "sales_person")
			if (part := item.get(part_name)) and part.get("action") in ("conflict", "choose")
			and decisions.get(f"{item['item_id']}:{part_name}") not in (allowed - {"reuse"})
			and not str(decisions.get(f"{item['item_id']}:{part_name}", "")).startswith("link:")]
		if unresolved:
			frappe.throw(_("仍有 {0} 个关联项未处理，请逐项选择新建、关联或跳过").format(len(unresolved)), frappe.ValidationError)
	result = {"sales_people": [], "contacts": [], "addresses": [], "pending_customer_rows": plan["summary"]["pending_customer_rows"]}
	if frappe.parse_json(create_sales_people):
		result["sales_people"] = excel_reference_resolver.create_sales_people(plan, decisions)
	if frappe.parse_json(create_existing_customer_contacts):
		created = excel_reference_resolver.create_customer_contacts_and_addresses(plan, decisions)
		result.update(created)
	frappe.cache().delete_value("client_akivision:reference_plan:{0}".format(token))
	return result


def _field_group(
	meta, key, label, import_type, is_child, default_fields=None,
	use_legacy_defaults=False, is_business_group=False,
):
	configured_defaults = set(default_fields or [])
	fields = []
	if import_type == "Update Existing Records":
		fields.append({
			"fieldname": "name",
			"label": _("ID"),
			"fieldtype": "Data",
			"options": None,
			"reqd": True,
			"read_only": False,
			"writable": True,
			"default_selected": True,
		})
	for field in meta.fields:
		if field.fieldtype in (
			"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Table MultiSelect"
		) or field.fieldname in ("lft", "rgt") or field.is_virtual:
			continue
		is_read_only = bool(field.read_only or field.fetch_from)
		is_system = field.fieldname in {"owner", "creation", "modified", "modified_by"}
		writable = not is_read_only and not is_system and field.fieldtype != "Table"
		if import_type == "Update Existing Records" and field.fieldname == "name":
			writable = True
		fields.append({
			"fieldname": field.fieldname,
			"label": _(field.label) if field.label else field.fieldname,
			"fieldtype": field.fieldtype,
			"options": field.options,
			"reqd": bool(field.reqd),
			"read_only": is_read_only,
			"writable": writable,
			"import_hint": _get_import_hint(field, is_read_only, key),
			"default_selected": writable and (
				bool(field.reqd)
				or field.fieldname in configured_defaults
				or (use_legacy_defaults and bool(field.in_list_view))
			),
		})
	return {
		"key": key,
		"label": _(label or meta.name),
		"doctype": _(meta.name),
		"is_business_group": is_business_group,
		"fields": fields,
	}


def _get_import_hint(field, is_read_only, group_key=None):
	if group_key == "items" and field.fieldname == "item_name":
		return _("仅用于人工核对；保存时以物料编码对应的物料主数据为准")
	if group_key == "items" and field.fieldname == "custom_import_level":
		return _("直接组件固定填写 1；多层结构请拆分为独立 BOM，并填写子 BOM 编码")
	if group_key == "items" and field.fieldname in {
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
	}:
		return _("由已定稿工程图纸自动快照，模板不能覆盖")
	if is_read_only:
		return _("只读，由系统自动生成")
	if field.fieldtype in {"Link", "Dynamic Link"}:
		target = field.options or _("关联记录")
		return _("关联：{0}，目标记录必须已存在").format(target)
	if field.fieldtype in {"Data", "Small Text", "Text", "Long Text", "Text Editor"}:
		return _("文本，可直接填写")
	return None
