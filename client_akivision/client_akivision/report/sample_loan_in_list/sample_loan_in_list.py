import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("借回单号 / 供应商型号"), "fieldname": "name", "fieldtype": "Data", "width": 200},
        {"label": _("供应商"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("对应阿基型号"), "fieldname": "external_model", "fieldtype": "Data", "width": 150},
        {"label": _("数量"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": _("状态"), "fieldname": "status", "fieldtype": "Data", "width": 105},
        {"label": _("是否借出"), "fieldname": "is_loaned_out", "fieldtype": "Data", "width": 95},
        {"label": _("借用日期"), "fieldname": "loan_date", "fieldtype": "Date", "width": 100},
        {"label": _("归还日期"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
        {"label": _("借用人"), "fieldname": "loaned_by", "fieldtype": "Link", "options": "User", "width": 130},
        {"label": _("联系人"), "fieldname": "contact_person", "fieldtype": "Data", "width": 120},
        {"label": _("供应商电话"), "fieldname": "phone", "fieldtype": "Data", "width": 120},
        {"label": _("借样形式"), "fieldname": "loan_form", "fieldtype": "Data", "width": 105},
        {"label": _("合同号/单号"), "fieldname": "contract_no", "fieldtype": "Data", "width": 150},
        {"label": _("最新去向"), "fieldname": "latest_destination", "fieldtype": "Link", "options": "Warehouse", "width": 140},
        {"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    loans = frappe.db.sql(
        f"""
        SELECT name, supplier, company, loan_date, contract_no, loaned_by,
            contact_person, phone, loan_form, status, remarks, total_qty, returned_qty
        FROM `tabSample Loan In`
        WHERE docstatus = 1 {conditions}
        ORDER BY loan_date DESC, name DESC
        """,
        filters,
        as_dict=True,
    )
    if not loans:
        return []

    loan_names = [loan.name for loan in loans]
    item_conditions = ["sli.parent IN %(loan_names)s"]
    item_filters = dict(filters, loan_names=loan_names)
    if filters.get("item_code"):
        item_conditions.append("sli.item_code = %(item_code)s")

    items_by_loan = {}
    for item in frappe.db.sql(
        f"""
        SELECT sli.name, sli.parent, sli.idx, sli.supplier_part_no, sli.supplier_model,
            sli.item_code, sli.internal_model, sli.external_model, sli.qty, sli.serial_no,
            sli.loan_warehouse, sli.returned_qty, sli.returned, sli.return_date, sli.disposition,
            i.item_name
        FROM `tabSample Loan In Item` sli
        LEFT JOIN `tabItem` i ON i.name = sli.item_code
        WHERE {' AND '.join(item_conditions)}
        ORDER BY sli.parent, sli.idx
        """,
        item_filters,
        as_dict=True,
    ):
        items_by_loan.setdefault(item.parent, []).append(item)

    serial_numbers = {
        item.serial_no for items in items_by_loan.values() for item in items if item.serial_no
    }
    loaned_out_serials = set()
    if serial_numbers:
        loaned_out_serials = set(
            frappe.db.sql_list(
                """
                SELECT sloi.serial_no
                FROM `tabSample Loan Out Item` sloi
                INNER JOIN `tabSample Loan Out` slo ON slo.name = sloi.parent
                WHERE slo.docstatus = 1
                  AND sloi.serial_no IN %(serial_numbers)s
                  AND sloi.returned = 0
                  AND IFNULL(sloi.disposition, '') = ''
                """,
                {"serial_numbers": list(serial_numbers)},
            )
        )

    data = []
    for loan in loans:
        items = items_by_loan.get(loan.name, [])
        if filters.get("item_code") and not items:
            continue
        data.append(
            {
                "name": loan.name,
                "parent": None,
                "indent": 0,
                "is_group": 1,
                "name_display": loan.contract_no or loan.name,
                "supplier": loan.supplier,
                "qty": flt(loan.total_qty),
                "returned_qty": flt(loan.returned_qty),
                "status": _(loan.status) if loan.status else "",
                "loan_date": loan.loan_date,
                "loaned_by": loan.loaned_by,
                "contact_person": loan.contact_person,
                "phone": loan.phone,
                "loan_form": loan.loan_form,
                "contract_no": loan.contract_no,
                "remarks": loan.remarks,
            }
        )
        for item in items:
            data.append(
                {
                    "name": f"{loan.name}#{item.name}",
                    "parent": loan.name,
                    "indent": 1,
                    "is_group": 0,
                    # The tree leaf represents the supplier's borrowed sample.
                    # Prefer its supplier model rather than the supplier part
                    # number so the hierarchy matches the loan-in document.
                    "name_display": item.supplier_model or item.supplier_part_no or item.item_name or item.item_code,
                    "supplier": loan.supplier,
                    "item_name": item.supplier_part_no or item.item_name,
                    "supplier_model": item.supplier_model,
                    "external_model": item.external_model,
                    "qty": flt(item.qty),
                    "status": get_item_status(item),
                    "is_loaned_out": _("是") if item.serial_no in loaned_out_serials else _("否"),
                    "loan_date": loan.loan_date,
                    "return_date": item.return_date,
                    "loaned_by": loan.loaned_by,
                    "contact_person": loan.contact_person,
                    "phone": loan.phone,
                    "loan_form": loan.loan_form,
                    "contract_no": loan.contract_no,
                    "latest_destination": item.loan_warehouse,
                    "remarks": loan.remarks,
                }
            )
    return data


def get_item_status(item):
    if item.disposition == "Scrapped":
        return _("已报废")
    if item.returned or flt(item.returned_qty) >= flt(item.qty):
        return _("已归还")
    if flt(item.returned_qty):
        return _("部分归还")
    return _("借用中")


def get_conditions(filters):
    conditions = []
    if filters.get("company"):
        conditions.append("AND company = %(company)s")
    if filters.get("supplier"):
        conditions.append("AND supplier = %(supplier)s")
    if filters.get("from_date"):
        conditions.append("AND loan_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("AND loan_date <= %(to_date)s")
    return " ".join(conditions)
