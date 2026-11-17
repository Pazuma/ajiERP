"""One-off local import of the user-provided workbook through Item validation."""
import json
from collections import Counter
from pathlib import Path

import frappe
import openpyxl

frappe.init(site="aki_test.localhost", sites_path="sites")
frappe.connect()
frappe.set_user("Administrator")
try:
    from client_akivision.utils.item_excel_import import save_row

    sheet = openpyxl.load_workbook("/workspace/工作簿1.xlsx", read_only=True, data_only=True).active
    rows = []
    for number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
        if not any(value is not None for value in values):
            continue
        group, code, name = [str(value).strip() if value is not None else "" for value in values]
        if not all((group, code, name)):
            raise ValueError(f"Incomplete row {number}")
        rows.append({"分类": group, "物料编码": code, "物料名称": name})
    codes = [row["物料编码"] for row in rows]
    assert len(codes) == len(set(codes)), "Duplicate codes"
    existing = frappe.get_all("Item", filters={"name": ["in", codes]}, pluck="name")
    assert not existing, f"Existing items: {existing[:10]}"
    created_groups = []
    for group in sorted({row["分类"] for row in rows}):
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc({"doctype": "Item Group", "item_group_name": group,
                            "parent_item_group": "All Item Groups", "is_group": 0}).insert()
            created_groups.append(group)
        assert not frappe.db.get_value("Item Group", group, "is_group"), group
    for index, row in enumerate(rows, 1):
        save_row(row, "Insert New Records")
        if index % 250 == 0:
            print(f"Validated {index}/{len(rows)}", flush=True)
    saved = frappe.get_all("Item", filters={"name": ["in", codes]},
                           fields=["name", "item_code", "item_name", "item_group", "is_sales_item", "stock_uom"],
                           limit_page_length=0)
    assert len(saved) == len(rows)
    by_code = {row["物料编码"]: row for row in rows}
    for item in saved:
        source = by_code[item.name]
        assert item.item_code == item.name
        assert item.item_name == source["物料名称"] and item.item_group == source["分类"]
        assert item.is_sales_item == 0 and item.stock_uom == "Nos"
    frappe.db.commit()
    report = {"site": "aki_test.localhost", "file": "工作簿1.xlsx", "inserted": len(saved),
              "created_groups": created_groups, "counts_by_group": dict(Counter(r["分类"] for r in rows)),
              "verified": True, "item_codes": codes}
    Path("/workspace/workbook_items_import_result_20261104.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "item_codes"}, ensure_ascii=False), flush=True)
except Exception:
    frappe.db.rollback()
    raise
finally:
    frappe.destroy()
