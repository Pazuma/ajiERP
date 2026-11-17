import json
from pathlib import Path

import frappe

from client_akivision.client_akivision.api.data_import import (
	_source_column_map,
	run_inline_import,
)


JOBS = [
	("Customer", "客户清单.xlsx", "Update Existing Records"),
	("Supplier", "供应商清单.xlsx", "Update Existing Records"),
	("Payment Terms Template", "收款模式清单.xlsx", "Update Existing Records"),
	("Project", "研发项目清单.xlsx", "Update Existing Records"),
	("Item", "ERP表格模板(2)(1)_产品清单.xlsx", "Update Existing Records"),
	("Item", "安全库存参数.xlsx", "Update Existing Records"),
	("Sales Order", "销售订单.xlsx", "Insert New Records"),
	("Purchase Order", "ERP表格模板(2)(1)_采购清单.xlsx", "Insert New Records"),
	("Purchase Receipt", "ERP表格模板(2)(1)_入库清单.xlsx", "Insert New Records"),
	("Delivery Note", "ERP表格模板(2)(1)_送货清单.xlsx", "Insert New Records"),
	("Payment Entry", "ERP表格模板(2)(1)_回款记录.xlsx", "Insert New Records"),
	("Payment Entry", "ERP表格模板(2)(1)_采购付款记录表.xlsx", "Insert New Records"),
	("Stock Entry", "ERP表格模板(2)(1)_出库清单.xlsx", "Insert New Records"),
	("Asset", "ERP表格模板(2)(1)_固定资产清单.xlsx", "Update Existing Records"),
	("Timesheet", "ERP表格模板(2)(1)_工时记录.xlsx", "Insert New Records"),
	("Sample Loan Out", "ERP表格模板(2)(1)_借出样品清单.xlsx", "Insert New Records"),
	("Sample Loan In", "ERP表格模板(2)(1)_借回样品清单.xlsx", "Insert New Records"),
	("Supplier", "ERP表格模板(2)(1)_供应商回顾.xlsx", "Update Existing Records"),
	("Item", "实时库存.xlsx", "Update Existing Records"),
]


@frappe.whitelist()
def import_data_directory():
	root = Path(frappe.get_site_path("private", "files", "数据"))
	results = []
	for doctype, filename, import_type in JOBS:
		path = root / filename
		result = {"doctype": doctype, "filename": filename, "import_type": import_type}
		if not path.exists():
			result.update(status="missing", message="文件不存在")
			results.append(result)
			continue
		url = "/private/files/数据/" + filename
		file_name = frappe.db.get_value("File", {"file_url": url}, "name")
		if not file_name:
			file_doc = frappe.get_doc({"doctype": "File", "file_name": filename, "file_url": url, "is_private": 1})
			file_doc.insert(ignore_permissions=True)
			frappe.db.commit()
		try:
			task = frappe.get_doc({"doctype": "Data Import", "reference_doctype": doctype, "import_type": import_type, "mute_emails": 1, "submit_after_import": 0})
			task.import_file = url
			task.template_options = json.dumps({"column_to_field_map": _source_column_map(doctype, url)}, ensure_ascii=False)
			task.insert(ignore_permissions=True)
			out = run_inline_import(task.name)
			result.update(status=out.get("status"), task=task.name)
		except Exception:
			frappe.db.rollback()
			result.update(status="Error", message=frappe.get_traceback())
		results.append(result)
		frappe.db.commit()
	return results
