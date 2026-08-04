import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today


def validate_sample_loan_warehouses(company, warehouses):
    """Validate warehouses before a trusted sample Stock Entry is created."""
    checked = set()
    for warehouse in warehouses:
        if not warehouse or warehouse in checked:
            continue
        checked.add(warehouse)
        values = frappe.db.get_value(
            "Warehouse", warehouse, ["company", "is_group", "disabled"], as_dict=True
        )
        if not values:
            frappe.throw(_("仓库 {0} 不存在，无法处理样品库存。").format(warehouse))
        if values.company and company and values.company != company:
            frappe.throw(_("仓库 {0} 不属于公司 {1}，无法处理样品库存。").format(warehouse, company))
        if values.is_group:
            frappe.throw(_("仓库 {0} 是仓库组，不能用于样品库存移动。").format(warehouse))
        if values.disabled:
            frappe.throw(_("仓库 {0} 已禁用，不能用于样品库存移动。").format(warehouse))


def create_sample_loan_stock_entry(
    doc, items, stock_entry_type, is_return=False
):
    """Create a Stock Entry for sample loan out/return and submit it.

    Args:
        doc: Sample Loan Out / Sample Loan Out Return document
        items: list of child row dicts with keys item_code, serial_no,
               source_warehouse, loan_warehouse
        stock_entry_type: Stock Entry Type name
        is_return: whether this is a return stock entry

    Returns:
        Stock Entry name
    """
    from erpnext.stock.serial_batch_bundle import SerialBatchCreation

    if not items:
        frappe.throw(_("No items to process."))

    warehouses = []
    for row in items:
        warehouses.extend(
            [
                row.get("source_warehouse") if isinstance(row, dict) else row.source_warehouse,
                row.get("loan_warehouse") if isinstance(row, dict) else row.loan_warehouse,
            ]
        )
    if is_return:
        warehouses.append(frappe.db.get_single_value("Stock Settings", "sample_retention_warehouse"))
    validate_sample_loan_warehouses(doc.company, warehouses)

    posting_date = doc.get("loan_date") or doc.get("return_date") or today()

    stock_entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": stock_entry_type,
            "purpose": "Material Transfer",
            "company": doc.company,
            "posting_date": posting_date,
            "custom_akivision_sample_loan_doctype": doc.doctype,
            "custom_akivision_sample_loan_doc": doc.name,
        }
    )

    # Group by (item_code, source_warehouse, loan_warehouse)
    grouped = {}
    for row in items:
        item_code = row.get("item_code") if isinstance(row, dict) else row.item_code
        serial_no = row.get("serial_no") if isinstance(row, dict) else row.serial_no
        source_warehouse = row.get("source_warehouse") if isinstance(row, dict) else row.source_warehouse
        loan_warehouse = row.get("loan_warehouse") if isinstance(row, dict) else row.loan_warehouse

        from_wh = loan_warehouse if is_return else source_warehouse
        return_warehouse = frappe.db.get_single_value("Stock Settings", "sample_retention_warehouse") if is_return else None
        to_wh = (return_warehouse or source_warehouse) if is_return else loan_warehouse
        key = (item_code, from_wh, to_wh)
        grouped.setdefault(key, {"serial_nos": [], "source_warehouse": source_warehouse, "loan_warehouse": loan_warehouse})
        grouped[key]["serial_nos"].append(serial_no)

    for (item_code, from_wh, to_wh), data in grouped.items():
        serial_nos = data["serial_nos"]
        qty = len(serial_nos)
        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
        stock_entry.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "uom": stock_uom,
                "stock_uom": stock_uom,
                "conversion_factor": 1,
                "s_warehouse": from_wh,
                "t_warehouse": to_wh,
                "allow_zero_valuation_rate": 1,
            },
        )

    # Save first to obtain the Stock Entry name and child row names for the bundles.
    stock_entry.flags.ignore_validate = True
    stock_entry.save(ignore_permissions=True)
    stock_entry.flags.ignore_validate = False

    for row in stock_entry.items:
        key = (row.item_code, row.s_warehouse, row.t_warehouse)
        data = grouped.get(key)
        if not data:
            continue
        serial_nos = data["serial_nos"]
        qty = len(serial_nos)
        bundle_doc = SerialBatchCreation(
            {
                "item_code": row.item_code,
                "warehouse": row.s_warehouse,
                "qty": -qty,
                "actual_qty": -qty,
                "type_of_transaction": "Outward",
                "voucher_type": "Stock Entry",
                "voucher_no": stock_entry.name,
                "voucher_detail_no": row.name,
                "company": doc.company,
                "serial_nos": serial_nos,
                "do_not_submit": True,
            }
        ).make_serial_and_batch_bundle(serial_nos=serial_nos)

        if bundle_doc and bundle_doc.name:
            row.db_set("serial_and_batch_bundle", bundle_doc.name)

    stock_entry.reload()
    stock_entry.submit()

    return stock_entry.name


def cancel_linked_stock_entry(stock_entry_name):
    """Cancel a linked Stock Entry."""
    if not stock_entry_name:
        return

    se = frappe.get_doc("Stock Entry", stock_entry_name)
    if se.docstatus == 1:
        se.cancel()


def update_serial_no_status(serial_no, status, loan_out=None, customer=None, sales_order=None):
    """Update custom status fields on Serial No."""
    values = {"custom_akivision_status": status}

    if loan_out is not None:
        values["custom_akivision_loan_out"] = loan_out
    if customer is not None:
        values["custom_akivision_customer"] = customer
    if sales_order is not None:
        values["custom_akivision_sales_order"] = sales_order

    frappe.db.set_value("Serial No", serial_no, values)


def get_finished_goods_status(serial_no):
    """Get or create Finished Goods Status record for a Serial No."""
    if frappe.db.exists("Finished Goods Status", serial_no):
        return frappe.get_doc("Finished Goods Status", serial_no)

    sn = frappe.get_doc("Serial No", serial_no)
    item = frappe.get_doc("Item", sn.item_code) if sn.item_code else None

    doc = frappe.get_doc(
        {
            "doctype": "Finished Goods Status",
            "name": serial_no,
            "serial_no": serial_no,
            "item_code": sn.item_code,
            "internal_model": item.custom_internal_model if item else None,
            "external_model": item.custom_external_model if item else None,
            "warehouse": sn.warehouse,
            "in_qty": 1,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def upsert_finished_goods_status(serial_no, data):
    """Update Finished Goods Status with given data dict."""
    doc = get_finished_goods_status(serial_no)
    for key, value in data.items():
        doc.set(key, value)
    doc.save(ignore_permissions=True)


def sync_finished_goods_status_from_serial_no(serial_no):
    """Sync warehouse from Serial No to Finished Goods Status."""
    sn = frappe.get_doc("Serial No", serial_no)
    data = {"warehouse": sn.warehouse}
    upsert_finished_goods_status(serial_no, data)


def update_parent_return_status(loan_out_name):
    """Recompute Sample Loan Out status and returned qty without re-validating the parent.

    Items that are sold or scrapped are treated as finalized for the parent status,
    but they do not count toward the physical returned quantity.
    """
    items = frappe.get_all(
        "Sample Loan Out Item",
        filters={"parent": loan_out_name, "parenttype": "Sample Loan Out"},
        fields=["returned", "disposition"],
    )
    total = len(items)
    if total == 0:
        return

    returned = sum(1 for row in items if row.returned)
    finalized = sum(
        1
        for row in items
        if row.returned or row.disposition in ("Sold", "Scrapped")
    )
    sold = sum(1 for row in items if row.disposition == "Sold")
    scrapped = sum(1 for row in items if row.disposition == "Scrapped")

    if sold == total:
        status = "Converted to Sales"
    elif scrapped == total:
        status = "Scrapped"
    elif finalized == total:
        status = "Returned"
    elif finalized > 0:
        status = "Partially Returned"
    else:
        status = "Loaned"

    current_status = frappe.db.get_value("Sample Loan Out", loan_out_name, "status")
    values = {"returned_qty": returned}

    if current_status not in ["Converted to Sales", "Scrapped"] or finalized == total:
        values["status"] = status

    frappe.db.set_value("Sample Loan Out", loan_out_name, values)


def get_unreturned_serial_nos(loan_out_name):
    """Return list of unreturned serial nos for a Sample Loan Out."""
    rows = frappe.get_all(
        "Sample Loan Out Item",
        filters={"parent": loan_out_name, "parenttype": "Sample Loan Out", "returned": 0},
        fields=["serial_no", "item_code"],
    )
    return rows


def create_sales_order_from_loan(loan_doc, serial_nos):
    """Create one Sales Order per customer for selected Sample Loan Out rows."""
    if not serial_nos:
        frappe.throw(_("Please select at least one Serial No to convert to sales."))

    selected_items = [row for row in loan_doc.items if row.serial_no in serial_nos]
    if not selected_items:
        frappe.throw(_("Selected serial numbers are not part of this loan."))

    grouped = {}
    for row in selected_items:
        if not row.customer:
            frappe.throw(
                _("Row {0}: Customer is required before converting to sales.").format(row.idx)
            )
        key = (row.customer, row.item_code, row.loan_warehouse)
        grouped[key] = grouped.get(key, 0) + 1

    sales_orders = {}
    for customer in {row.customer for row in selected_items}:
        items = [
            {
                "item_code": item_code,
                "qty": qty,
                "delivery_date": today(),
                "warehouse": loan_warehouse,
            }
            for (group_customer, item_code, loan_warehouse), qty in grouped.items()
            if group_customer == customer
        ]
        so = frappe.get_doc(
            {
                "doctype": "Sales Order",
                "customer": customer,
                "company": loan_doc.company,
                "transaction_date": today(),
                "delivery_date": today(),
                "items": items,
            }
        )
        so.insert()
        so.submit()
        sales_orders[customer] = so.name

    # Update loan items and serial numbers
    selected_by_serial = {row.serial_no: row for row in selected_items}
    for row in selected_items:
        row.db_set({"disposition": "Sold", "status": "已转销售"})

    for serial_no in serial_nos:
        row = selected_by_serial[serial_no]
        sales_order = sales_orders[row.customer]
        update_serial_no_status(
            serial_no,
            status="Sold",
            loan_out=loan_doc.name,
            customer=row.customer,
            sales_order=sales_order,
        )
        upsert_finished_goods_status(
            serial_no,
            {
                "status": "销售品",
                "sub_status": "转销售",
                "customer": row.customer,
                "loan_or_sales_no": sales_order,
                "loan_or_sales_date": getdate(today()),
                "sample_loan_out": loan_doc.name,
                "sales_order": sales_order,
                "warehouse": frappe.db.get_value("Serial No", serial_no, "warehouse"),
            },
        )

    # Move stock from loan warehouse to a regular warehouse via Stock Entry
    # This step is optional; if Delivery Note is created from SO, it will consume from loan warehouse.
    # To keep simple, we leave stock in loan warehouse and let DN handle it.

    update_parent_return_status(loan_doc.name)
    loan_doc.reload()

    # If all items are sold, record the sales order reference.
    total = len(loan_doc.items)
    sold = sum(1 for r in loan_doc.items if r.disposition == "Sold")
    if sold == total:
        loan_doc.db_set(
            "sales_order_reference",
            next(iter(sales_orders.values())) if len(sales_orders) == 1 else None,
        )

    return list(sales_orders.values())


def create_sample_loan_in_stock_entry(
    doc, items, stock_entry_type=None, is_return=False
):
    """Create a Stock Entry for sample loan in (Material Receipt) or return (Material Issue).

    Args:
        doc: Sample Loan In / Sample Loan In Return document
        items: list of child row dicts with keys item_code, serial_no, qty, loan_warehouse
        stock_entry_type: Stock Entry Type name
        is_return: whether this is a return stock entry (Material Issue)

    Returns:
        Stock Entry name
    """
    from erpnext.stock.serial_batch_bundle import SerialBatchCreation

    if not items:
        frappe.throw(_("No items to process."))

    validate_sample_loan_warehouses(
        doc.company,
        [
            row.get("loan_warehouse") if isinstance(row, dict) else getattr(row, "loan_warehouse", None)
            for row in items
        ],
    )

    posting_date = doc.get("loan_date") or doc.get("return_date") or today()

    purpose = "Material Issue" if is_return else "Material Receipt"
    stock_entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": stock_entry_type,
            "purpose": purpose,
            "company": doc.company,
            "posting_date": posting_date,
            "custom_akivision_sample_loan_doctype": doc.doctype,
            "custom_akivision_sample_loan_doc": doc.name,
        }
    )

    # Group by (item_code, loan_warehouse) and accumulate qty / serial_nos
    grouped = {}
    for row in items:
        item_code = row.get("item_code") if isinstance(row, dict) else row.item_code
        serial_no = row.get("serial_no") if isinstance(row, dict) else row.serial_no
        qty = row.get("qty", 1) if isinstance(row, dict) else getattr(row, "qty", 1)
        loan_warehouse = row.get("loan_warehouse") if isinstance(row, dict) else getattr(row, "loan_warehouse", None)
        key = (item_code, loan_warehouse)
        entry = grouped.setdefault(key, {"qty": 0, "serial_nos": [], "loan_warehouse": loan_warehouse})
        entry["qty"] += qty
        if serial_no:
            entry["serial_nos"].append(serial_no)

    for (item_code, loan_warehouse), data in grouped.items():
        qty = data["qty"]
        serial_nos = data["serial_nos"]
        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
        row_kwargs = {
            "item_code": item_code,
            "qty": qty,
            "uom": stock_uom,
            "stock_uom": stock_uom,
            "conversion_factor": 1,
            "allow_zero_valuation_rate": 1,
        }
        if is_return:
            row_kwargs["s_warehouse"] = loan_warehouse
        else:
            row_kwargs["t_warehouse"] = loan_warehouse

        stock_entry.append("items", row_kwargs)

    # Save first to obtain the Stock Entry name and child row names for the bundles.
    stock_entry.flags.ignore_validate = True
    stock_entry.save(ignore_permissions=True)
    stock_entry.flags.ignore_validate = False

    for row in stock_entry.items:
        key = (row.item_code, row.s_warehouse if is_return else row.t_warehouse)
        data = grouped.get(key)
        if not data:
            continue
        qty = data["qty"]
        serial_nos = data["serial_nos"]
        if qty <= 0:
            continue

        item_has_serial_no = frappe.db.get_value("Item", row.item_code, "has_serial_no")
        item_has_batch_no = frappe.db.get_value("Item", row.item_code, "has_batch_no")

        if not (item_has_serial_no or item_has_batch_no):
            continue

        bundle_kwargs = {
            "item_code": row.item_code,
            "warehouse": row.s_warehouse if is_return else row.t_warehouse,
            "qty": -qty if is_return else qty,
            "actual_qty": -qty if is_return else qty,
            "type_of_transaction": "Outward" if is_return else "Inward",
            "voucher_type": "Stock Entry",
            "voucher_no": stock_entry.name,
            "voucher_detail_no": row.name,
            "company": doc.company,
            "do_not_submit": True,
        }

        if item_has_serial_no:
            bundle_kwargs["serial_nos"] = serial_nos

        bundle_doc = SerialBatchCreation(bundle_kwargs).make_serial_and_batch_bundle(
            serial_nos=serial_nos
        )

        if bundle_doc and bundle_doc.name:
            row.db_set("serial_and_batch_bundle", bundle_doc.name)

    stock_entry.reload()
    stock_entry.submit()

    return stock_entry.name


def update_serial_no_status_for_loan_in(serial_no, status, loan_in=None, supplier=None):
    """Update custom status fields on Serial No for Sample Loan In."""
    values = {"custom_akivision_status": status}

    if loan_in is not None:
        values["custom_akivision_loan_in"] = loan_in
    if supplier is not None:
        values["custom_akivision_supplier"] = supplier

    frappe.db.set_value("Serial No", serial_no, values)


def update_parent_return_status_for_loan_in(loan_in_name):
    """Recompute Sample Loan In status based on returned qty."""
    items = frappe.get_all(
        "Sample Loan In Item",
        filters={"parent": loan_in_name, "parenttype": "Sample Loan In"},
        fields=["name", "qty", "returned_qty"],
    )
    total = sum(flt(item.qty) for item in items)
    returned = sum(flt(item.returned_qty) for item in items)

    if returned == 0:
        status = "Loaned"
    elif returned < total:
        status = "Partially Returned"
    else:
        status = "Returned"

    frappe.db.set_value(
        "Sample Loan In", loan_in_name, {"returned_qty": returned, "status": status}
    )


# Stock Entry hooks
# -----------------


def on_stock_entry_submit(doc, method):
    """Frappe doc_event hook: update Serial No status when a loan-linked Stock Entry is submitted."""
    if not is_sample_loan_stock_entry(doc):
        return
    _sync_serial_nos_from_stock_entry(doc, is_cancel=False)


def on_stock_entry_cancel(doc, method):
    """Frappe doc_event hook: revert Serial No status when a loan-linked Stock Entry is cancelled."""
    if not is_sample_loan_stock_entry(doc):
        return
    _sync_serial_nos_from_stock_entry(doc, is_cancel=True)


def is_sample_loan_stock_entry(doc):
    """Return True if the Stock Entry is linked to a sample loan document."""
    loan_doctype = doc.get("custom_akivision_sample_loan_doctype")
    loan_doc_name = doc.get("custom_akivision_sample_loan_doc")
    if not loan_doctype or not loan_doc_name:
        return False
    return loan_doctype in (
        "Sample Loan Out",
        "Sample Loan Out Return",
        "Sample Loan In",
        "Sample Loan In Return",
    )


def _sync_serial_nos_from_stock_entry(doc, is_cancel):
    """Sync Serial No custom_akivision_status from a loan-linked Stock Entry."""
    serial_nos = _get_serial_nos_from_stock_entry(doc)
    if not serial_nos:
        return

    sync_serial_status_from_loan_doc(
        doc.custom_akivision_sample_loan_doctype,
        doc.custom_akivision_sample_loan_doc,
        is_cancel=is_cancel,
        serial_nos=serial_nos,
    )


def _get_serial_nos_from_stock_entry(doc):
    """Collect all serial numbers from a Stock Entry's items."""
    serial_nos = []
    for row in doc.items:
        serial_nos.extend(_get_serial_nos_from_stock_entry_row(row))
    return list(dict.fromkeys(serial_nos))


def _get_serial_nos_from_stock_entry_row(row):
    """Return serial numbers for a Stock Entry Detail row."""
    return _get_serial_nos_from_item_row(row)


def sync_serial_status_from_loan_doc(
    loan_doc_type, loan_doc_name, is_cancel=False, serial_nos=None
):
    """Update Serial No custom_akivision_status and Finished Goods Status for a loan document.

    Args:
        loan_doc_type: one of Sample Loan Out/Return/In/Return
        loan_doc_name: name of the loan document
        is_cancel: if True, apply the reverse/cancelled state
        serial_nos: optional list of serial numbers to update; defaults to all serials on the loan doc
    """
    loan_doc = frappe.get_doc(loan_doc_type, loan_doc_name)

    if serial_nos is None:
        serial_nos = [row.serial_no for row in loan_doc.items if row.serial_no]

    if not serial_nos:
        return

    if loan_doc_type == "Sample Loan Out":
        _sync_sample_loan_out(loan_doc, serial_nos, is_cancel)
    elif loan_doc_type == "Sample Loan Out Return":
        _sync_sample_loan_out_return(loan_doc, serial_nos, is_cancel)
    elif loan_doc_type == "Sample Loan In":
        _sync_sample_loan_in(loan_doc, serial_nos, is_cancel)
    elif loan_doc_type == "Sample Loan In Return":
        _sync_sample_loan_in_return(loan_doc, serial_nos, is_cancel)


def _sync_sample_loan_out(loan_doc, serial_nos, is_cancel):
    item_map = _get_item_map_by_serial(loan_doc)

    if is_cancel:
        for serial_no in serial_nos:
            row = item_map.get(serial_no, {})
            update_serial_no_status(serial_no, status="In Stock", loan_out=None, customer=None)
            upsert_finished_goods_status(
                serial_no,
                {
                    "status": "样品",
                    "sub_status": "for-sample",
                    "customer": None,
                    "contact_person": None,
                    "phone": None,
                    "loan_or_sales_by": None,
                    "loan_or_sales_no": None,
                    "loan_or_sales_date": None,
                    "sample_loan_out": None,
                    "warehouse": row.get("source_warehouse"),
                },
            )
    else:
        for serial_no in serial_nos:
            row = item_map.get(serial_no, {})
            update_serial_no_status(
                serial_no,
                status="On Loan",
                loan_out=loan_doc.name,
                customer=row.get("customer"),
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "item_code": row.get("item_code"),
                    "internal_model": row.get("internal_model"),
                    "external_model": row.get("external_model"),
                    "status": "借出样品",
                    "sub_status": "已借出",
                    "customer": row.get("customer"),
                    "contact_person": row.get("contact_person"),
                    "phone": row.get("phone"),
                    "loan_or_sales_by": row.get("loaned_by"),
                    "loan_or_sales_no": loan_doc.name,
                    "loan_or_sales_date": loan_doc.loan_date,
                    "sample_loan_out": loan_doc.name,
                    "warehouse": row.get("loan_warehouse"),
                },
            )


def _sync_sample_loan_out_return(return_doc, serial_nos, is_cancel):
    loan_out_name = return_doc.sample_loan_out
    loan_out = frappe.get_doc("Sample Loan Out", loan_out_name)
    return_item_map = _get_item_map_by_serial(return_doc)

    if is_cancel:
        # Restore "On Loan" state from the original Sample Loan Out
        loan_out_item_map = _get_item_map_by_serial(loan_out)
        for serial_no in serial_nos:
            loan_row = loan_out_item_map.get(serial_no, {})
            update_serial_no_status(
                serial_no,
                status="On Loan",
                loan_out=loan_out_name,
                customer=loan_row.get("customer"),
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "item_code": loan_row.get("item_code"),
                    "internal_model": loan_row.get("internal_model"),
                    "external_model": loan_row.get("external_model"),
                    "status": "借出样品",
                    "sub_status": "已借出",
                    "customer": loan_row.get("customer"),
                    "contact_person": loan_row.get("contact_person"),
                    "phone": loan_row.get("phone"),
                    "loan_or_sales_by": loan_row.get("loaned_by"),
                    "loan_or_sales_no": loan_out.name,
                    "loan_or_sales_date": loan_out.loan_date,
                    "sample_loan_out": loan_out_name,
                    "warehouse": loan_row.get("loan_warehouse"),
                },
            )
    else:
        for serial_no in serial_nos:
            row = return_item_map.get(serial_no, {})
            update_serial_no_status(
                serial_no,
                status="In Stock",
                loan_out=None,
                customer=None,
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "status": "样品",
                    "sub_status": "for-sample",
                    "customer": None,
                    "contact_person": None,
                    "phone": None,
                    "loan_or_sales_by": None,
                    "loan_or_sales_no": None,
                    "loan_or_sales_date": None,
                    "sample_loan_out": None,
                    "warehouse": row.get("source_warehouse"),
                },
            )


def _sync_sample_loan_in(loan_doc, serial_nos, is_cancel):
    item_map = _get_item_map_by_serial(loan_doc)

    if is_cancel:
        for serial_no in serial_nos:
            row = item_map.get(serial_no, {})
            update_serial_no_status_for_loan_in(
                serial_no, status="In Stock", loan_in=None, supplier=None
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "status": "样品",
                    "sub_status": "for-sample",
                    "supplier": None,
                    "contact_person": None,
                    "phone": None,
                    "loan_or_sales_by": None,
                    "loan_or_sales_no": None,
                    "loan_or_sales_date": None,
                    "sample_loan_in": None,
                    "warehouse": row.get("loan_warehouse"),
                },
            )
    else:
        for serial_no in serial_nos:
            row = item_map.get(serial_no, {})
            update_serial_no_status_for_loan_in(
                serial_no,
                status="On Loan",
                loan_in=loan_doc.name,
                supplier=loan_doc.supplier,
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "item_code": row.get("item_code"),
                    "internal_model": row.get("internal_model"),
                    "external_model": row.get("external_model"),
                    "status": "借出样品",
                    "sub_status": "已借出",
                    "supplier": loan_doc.supplier,
                    "contact_person": loan_doc.contact_person,
                    "phone": loan_doc.phone,
                    "loan_or_sales_by": loan_doc.loaned_by,
                    "loan_or_sales_no": loan_doc.name,
                    "loan_or_sales_date": loan_doc.loan_date,
                    "sample_loan_in": loan_doc.name,
                    "warehouse": row.get("loan_warehouse"),
                },
            )


def _sync_sample_loan_in_return(return_doc, serial_nos, is_cancel):
    loan_in_name = return_doc.sample_loan_in
    loan_in = frappe.get_doc("Sample Loan In", loan_in_name)
    loan_in_supplier = loan_in.supplier
    return_item_map = _get_item_map_by_serial(return_doc)

    if is_cancel:
        loan_in_item_map = _get_item_map_by_serial(loan_in)
        for serial_no in serial_nos:
            loan_row = loan_in_item_map.get(serial_no, {})
            update_serial_no_status_for_loan_in(
                serial_no,
                status="On Loan",
                loan_in=loan_in_name,
                supplier=loan_in_supplier,
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "item_code": loan_row.get("item_code"),
                    "internal_model": loan_row.get("internal_model"),
                    "external_model": loan_row.get("external_model"),
                    "status": "借出样品",
                    "sub_status": "已借出",
                    "supplier": loan_in_supplier,
                    "contact_person": loan_in.contact_person,
                    "phone": loan_in.phone,
                    "loan_or_sales_by": loan_in.loaned_by,
                    "loan_or_sales_no": loan_in.name,
                    "loan_or_sales_date": loan_in.loan_date,
                    "sample_loan_in": loan_in_name,
                    "warehouse": loan_row.get("loan_warehouse"),
                },
            )
    else:
        for serial_no in serial_nos:
            row = return_item_map.get(serial_no, {})
            update_serial_no_status_for_loan_in(
                serial_no,
                status="In Stock",
                loan_in=None,
                supplier=None,
            )
            upsert_finished_goods_status(
                serial_no,
                {
                    "status": "样品",
                    "sub_status": "for-sample",
                    "supplier": None,
                    "contact_person": None,
                    "phone": None,
                    "loan_or_sales_by": None,
                    "loan_or_sales_no": None,
                    "loan_or_sales_date": None,
                    "sample_loan_in": None,
                    "warehouse": row.get("loan_warehouse"),
                },
            )


def _get_item_map_by_serial(loan_doc):
    """Return a dict mapping serial_no to the loan document item row."""
    return {row.serial_no: row for row in loan_doc.items if row.serial_no}


# Finished Goods Status auto-creation on receipt
# ----------------------------------------------


def on_purchase_receipt_submit(doc, method):
    """Create Finished Goods Status records when serialized items are received."""
    if doc.get("is_return"):
        return

    for row in doc.items:
        serial_nos = _get_serial_nos_from_item_row(row)
        if not serial_nos:
            continue
        for serial_no in serial_nos:
            create_finished_goods_status_for_receipt(
                serial_no,
                item_code=row.item_code,
                warehouse=row.warehouse,
                posting_date=doc.posting_date,
            )


def on_stock_entry_submit_for_fgs(doc, method):
    """Create Finished Goods Status records when serialized items are received via Stock Entry.

    Skips loan-linked Stock Entries because they are handled by the sample-loan hooks.
    """
    if is_sample_loan_stock_entry(doc):
        return

    if doc.purpose not in ("Material Receipt", "Disassemble"):
        return

    for row in doc.items:
        serial_nos = _get_serial_nos_from_item_row(row)
        if not serial_nos:
            continue
        warehouse = row.get("t_warehouse") or row.get("warehouse")
        if not warehouse:
            continue
        for serial_no in serial_nos:
            create_finished_goods_status_for_receipt(
                serial_no,
                item_code=row.item_code,
                warehouse=warehouse,
                posting_date=doc.posting_date,
            )


def create_finished_goods_status_for_receipt(serial_no, item_code, warehouse, posting_date):
    """Create or update Finished Goods Status when a serialized item is received.

    New records default to status="样品" and sub_status="for-sample".
    Existing records only have their warehouse updated; status/sub_status are preserved.
    """
    if frappe.db.exists("Finished Goods Status", serial_no):
        doc = frappe.get_doc("Finished Goods Status", serial_no)
        doc.warehouse = warehouse
        if not doc.status:
            doc.status = "样品"
        if not doc.sub_status:
            doc.sub_status = "for-sample"
        doc.save(ignore_permissions=True)
        return

    item = frappe.get_cached_doc("Item", item_code) if item_code else None
    frappe.get_doc(
        {
            "doctype": "Finished Goods Status",
            "serial_no": serial_no,
            "item_code": item_code,
            "internal_model": item.custom_internal_model if item else None,
            "external_model": item.custom_external_model if item else None,
            "in_qty": 1,
            "in_date": posting_date,
            "status": "样品",
            "sub_status": "for-sample",
            "warehouse": warehouse,
        }
    ).insert(ignore_permissions=True)


def _get_serial_nos_from_item_row(row):
    """Return serial numbers from a voucher item row (Stock Entry Detail, Purchase Receipt Item, etc.)."""
    if row.get("serial_and_batch_bundle"):
        return frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": row.serial_and_batch_bundle, "serial_no": ("is", "set")},
            pluck="serial_no",
        )
    if row.get("serial_no"):
        from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

        return get_serial_nos(row.serial_no)
    return []
