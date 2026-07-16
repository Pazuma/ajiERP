import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("借出单号 / 物料编码"), "fieldname": "name", "fieldtype": "Data", "width": 190},
        {"label": _("客户"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("机种"), "fieldname": "internal_model", "fieldtype": "Data", "width": 130},
        {"label": _("型号"), "fieldname": "external_model", "fieldtype": "Data", "width": 150},
        {"label": _("借出数量"), "fieldname": "qty", "fieldtype": "Float", "width": 95},
        {"label": _("状态"), "fieldname": "status", "fieldtype": "Data", "width": 105},
        {"label": _("归还数量"), "fieldname": "returned_qty", "fieldtype": "Float", "width": 95},
        {"label": _("借出日期"), "fieldname": "loan_date", "fieldtype": "Date", "width": 100},
        {"label": _("归还日期"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
        {"label": _("借出人"), "fieldname": "loaned_by", "fieldtype": "Link", "options": "User", "width": 130},
        {"label": _("客户联系人"), "fieldname": "contact_person", "fieldtype": "Data", "width": 120},
        {"label": _("客户电话"), "fieldname": "phone", "fieldtype": "Data", "width": 120},
        {"label": _("借样形式"), "fieldname": "loan_form", "fieldtype": "Data", "width": 105},
        {"label": _("合同号"), "fieldname": "contract_no", "fieldtype": "Data", "width": 160},
        {"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    loans = frappe.db.sql(
        f"""
        SELECT name, company, loan_date, contract_no, status, remarks, total_qty, returned_qty
        FROM `tabSample Loan Out`
        WHERE docstatus = 1 {conditions}
        ORDER BY loan_date DESC, name DESC
        """,
        filters,
        as_dict=True,
    )
    if not loans:
        return []

    loan_names = [loan.name for loan in loans]
    item_conditions = ["parent IN %(loan_names)s"]
    item_filters = dict(filters, loan_names=loan_names)
    if filters.get("customer"):
        item_conditions.append("customer = %(customer)s")
    if filters.get("item_code"):
        item_conditions.append("item_code = %(item_code)s")

    items_by_loan = {}
    for item in frappe.db.sql(
        f"""
        SELECT name, parent, idx, customer, item_code, internal_model, external_model,
            qty, status, return_date, loaned_by, contact_person, phone, loan_form,
            returned, disposition
        FROM `tabSample Loan Out Item`
        WHERE {' AND '.join(item_conditions)}
        ORDER BY parent, idx
        """,
        item_filters,
        as_dict=True,
    ):
        items_by_loan.setdefault(item.parent, []).append(item)

    data = []
    for loan in loans:
        items = items_by_loan.get(loan.name, [])
        if (filters.get("customer") or filters.get("item_code")) and not items:
            continue
        data.append(
            {
                "name": loan.name,
                "parent": None,
                "indent": 0,
                "is_group": 1,
                "name_display": loan.contract_no or loan.name,
                "qty": flt(loan.total_qty),
                "returned_qty": flt(loan.returned_qty),
                "status": _(loan.status) if loan.status else "",
                "loan_date": loan.loan_date,
                "contract_no": loan.contract_no or loan.name,
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
                    "name_display": item.item_code,
                    "item_code": item.item_code,
                    "customer": item.customer,
                    "internal_model": item.internal_model,
                    "external_model": item.external_model,
                    "qty": flt(item.qty),
                    "status": get_item_status(item),
                    "returned_qty": flt(item.qty) if item.returned else 0,
                    "loan_date": loan.loan_date,
                    "return_date": item.return_date,
                    "loaned_by": item.loaned_by,
                    "contact_person": item.contact_person,
                    "phone": item.phone,
                    "loan_form": item.loan_form,
                    "contract_no": loan.contract_no or loan.name,
                    "remarks": loan.remarks,
                }
            )
    return data


def get_item_status(item):
    if item.disposition == "Sold":
        return _("已转销售")
    if item.disposition == "Scrapped":
        return _("已报废")
    if item.returned:
        return _("已归还")
    return item.status or _("借出中")


def get_conditions(filters):
    conditions = []
    if filters.get("company"):
        conditions.append("AND company = %(company)s")
    if filters.get("from_date"):
        conditions.append("AND loan_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("AND loan_date <= %(to_date)s")
    return " ".join(conditions)
