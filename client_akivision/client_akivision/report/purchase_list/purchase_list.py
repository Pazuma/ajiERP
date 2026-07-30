import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {
            "label": _("单号 / 物料编码 / 入库单号"),
            "fieldname": "name",
            "fieldtype": "Data",
            "width": 220,
        },
        {"label": _("日期"), "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": _("供应商"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"label": _("供应商名称"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 140},
        {"label": _("物料名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
        {"label": _("单位"), "fieldname": "uom", "fieldtype": "Data", "width": 70},
        {"label": _("数量"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": _("含税单价"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
        {"label": _("税率"), "fieldname": "tax_rate", "fieldtype": "Percent", "width": 80},
        {"label": _("含税金额"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": _("对账金额"), "fieldname": "reconciled_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("是否已对账"), "fieldname": "reconciled_status", "fieldtype": "Data", "width": 110},
        {"label": _("最新交期"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 120},
        {"label": _("机种"), "fieldname": "internal_model", "fieldtype": "Data", "width": 100},
        {"label": _("已交"), "fieldname": "received_qty", "fieldtype": "Float", "width": 90},
        {"label": _("未交"), "fieldname": "pending_qty", "fieldtype": "Float", "width": 90},
        {"label": _("交货次数"), "fieldname": "delivery_sequence", "fieldtype": "Data", "width": 110},
        {"label": _("仓库"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 120},
        {"label": _("备注"), "fieldname": "description", "fieldtype": "Data", "width": 180},
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    purchase_orders = frappe.db.sql(
        f"""
        SELECT
            po.name,
            po.transaction_date,
            po.supplier,
            po.supplier_name,
            po.status,
            po.company,
            po.total,
            po.grand_total,
            po.rounded_total
        FROM `tabPurchase Order` po
        WHERE po.docstatus < 2 {conditions}
        ORDER BY po.transaction_date DESC, po.name DESC
        """,
        filters,
        as_dict=True,
    )

    po_names = [po.name for po in purchase_orders]
    if not po_names:
        return []

    # Fetch PO items
    items_by_po = {}
    poi_names = []
    item_codes = set()
    for item in frappe.db.sql(
        """
        SELECT
            poi.name AS poi_name,
            poi.parent,
            poi.idx,
            poi.item_code,
            poi.item_name,
            poi.stock_uom AS uom,
            poi.qty,
            poi.rate,
            poi.amount,
            poi.received_qty,
            (poi.qty - poi.received_qty) AS pending_qty,
            poi.schedule_date,
            poi.description,
            poi.warehouse
        FROM `tabPurchase Order Item` poi
        WHERE poi.parent IN %(po_names)s
        ORDER BY poi.idx
        """,
        {"po_names": po_names},
        as_dict=True,
    ):
        item_codes.add(item.item_code)
        poi_names.append(item.poi_name)
        items_by_po.setdefault(item.parent, []).append(item)

    # Fetch PR items linked to PO items
    pr_items_by_poi = {}
    for pr_item in frappe.db.sql(
        """
        SELECT
            pri.name AS pri_name,
            pri.parent,
            pri.purchase_order_item,
            pri.item_code,
            pri.item_name,
            pri.stock_uom AS uom,
            pri.qty,
            pri.amount,
            pri.warehouse,
            pr.posting_date,
            pr.status,
            pr.total AS pr_total,
            pr.grand_total AS pr_grand_total,
            pr.rounded_total AS pr_rounded_total
        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
        WHERE pri.purchase_order_item IN %(poi_names)s
          AND pr.docstatus = 1
        ORDER BY pr.posting_date
        """,
        {"poi_names": poi_names},
        as_dict=True,
    ):
        pr_items_by_poi.setdefault(pr_item.purchase_order_item, []).append(pr_item)

    # Fetch item internal model
    internal_models = {}
    if item_codes:
        for row in frappe.db.get_all(
            "Item",
            filters={"name": ["in", list(item_codes)]},
            fields=["name", "custom_internal_model"],
        ):
            internal_models[row.name] = row.custom_internal_model

    # Fetch PO tax rates (first tax row per PO)
    tax_rates_by_po = {}
    for tax in frappe.db.sql(
        """
        SELECT
            parent,
            rate
        FROM `tabPurchase Taxes and Charges`
        WHERE parent IN %(po_names)s
          AND docstatus < 2
        ORDER BY idx
        """,
        {"po_names": po_names},
        as_dict=True,
    ):
        if tax.parent not in tax_rates_by_po:
            tax_rates_by_po[tax.parent] = flt(tax.rate)

    # Reconciliation: (a) advance payments referencing the PO directly
    po_prepaid = {}
    for row in frappe.db.sql(
        """
        SELECT
            per.reference_name AS po_name,
            SUM(per.allocated_amount) AS paid
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE per.reference_doctype = 'Purchase Order'
          AND per.reference_name IN %(po_names)s
          AND pe.docstatus = 1
        GROUP BY per.reference_name
        """,
        {"po_names": po_names},
        as_dict=True,
    ):
        po_prepaid[row.po_name] = flt(row.paid)

    # Reconciliation: (b) invoice payments for each submitted Purchase Receipt.
    # A PI's paid portion = grand_total - outstanding_amount (covers both direct
    # payments and allocated advances). One PR may map to several PIs.
    pr_paid = {}
    for row in frappe.db.sql(
        """
        SELECT
            pii.purchase_receipt AS pr_name,
            SUM(pi.grand_total - pi.outstanding_amount) AS paid
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        INNER JOIN `tabPurchase Receipt` pr ON pr.name = pii.purchase_receipt
        WHERE pi.docstatus = 1
          AND pr.docstatus = 1
          AND pii.purchase_order IN %(po_names)s
          AND pii.purchase_receipt IS NOT NULL
          AND pii.purchase_receipt != ''
        GROUP BY pii.purchase_receipt
        """,
        {"po_names": po_names},
        as_dict=True,
    ):
        pr_paid[row.pr_name] = flt(row.paid)

    data = []
    for po in purchase_orders:
        po_items = items_by_po.get(po.name, [])
        po_tax_rate = tax_rates_by_po.get(po.name)

        # Compute PO-level aggregates
        po_qty = sum(flt(item.qty) for item in po_items)
        po_received = sum(flt(item.received_qty) for item in po_items)
        po_pending = sum(flt(item.pending_qty) for item in po_items)

        # Tax-inclusive totals come from the document itself; reconciliation compares against it.
        # po.total = Σ item.amount; po.grand_total = 含税总额. Prorating grand_total by each
        # item's amount share works for BOTH tax modes (price already tax-inclusive, or tax
        # added on top) and never double-counts tax.
        grand_total = flt(po.grand_total or po.rounded_total)
        po_total = flt(po.total)

        # Reconciled amount = advance paid against the PO + invoice payments on its receipts.
        po_pr_names = {
            pr_item.parent
            for item in po_items
            for pr_item in pr_items_by_poi.get(item.poi_name, [])
        }
        reconciled_amount = po_prepaid.get(po.name, 0.0) + sum(
            pr_paid.get(pr_name, 0.0) for pr_name in po_pr_names
        )
        reconciled_status = "已对账" if abs(reconciled_amount - grand_total) < 0.01 else "未对账"

        # Level 0: PO row
        data.append(
            {
                "name": po.name,
                "parent": None,
                "indent": 0,
                "is_group": 1,
                "date": po.transaction_date,
                "supplier": po.supplier,
                "supplier_name": po.supplier_name,
                "qty": po_qty,
                "rate": None,  # PO 行无单一含税价，留空避免显示 CNY 0.00 造成歧义
                "amount": grand_total,
                "reconciled_amount": reconciled_amount,
                "reconciled_status": reconciled_status,
                "tax_rate": po_tax_rate,
                "received_qty": po_received,
                "pending_qty": po_pending,
            }
        )

        for item in po_items:
            item_node = f"{po.name}#{item.idx}"
            pr_items = pr_items_by_poi.get(item.poi_name, [])

            # Level 1: PO Item row
            data.append(
                {
                    "name": item_node,
                    "parent": po.name,
                    "indent": 1,
                    "is_group": 1,
                    "name_display": item.item_code,
                    "item_name": item.item_name,
                    "uom": item.uom,
                    "qty": flt(item.qty),
                    "rate": flt(item.rate),
                    "amount": _taxed(item.amount, grand_total, po_total),
                    "tax_rate": po_tax_rate,
                    "schedule_date": item.schedule_date,
                    "internal_model": internal_models.get(item.item_code),
                    "received_qty": flt(item.received_qty),
                    "pending_qty": flt(item.pending_qty),
                    "warehouse": item.warehouse,
                    "description": item.description,
                    "delivery_sequence": f"总交货{len(pr_items)}次",
                }
            )

            # Level 2: PR Item rows with cumulative received and delivery sequence
            cumulative = 0
            for sequence, pr_item in enumerate(pr_items, start=1):
                cumulative += flt(pr_item.qty)
                data.append(
                    {
                        "name": f"{item_node}#{pr_item.pri_name}",
                        "parent": item_node,
                        "indent": 2,
                        "is_group": 0,
                        "name_display": pr_item.parent,
                        "date": pr_item.posting_date,
                        "item_name": pr_item.item_name,
                        "uom": pr_item.uom,
                        "qty": flt(pr_item.qty),
                        "rate": flt(item.rate),
                        "amount": _taxed(
                            pr_item.amount,
                            flt(pr_item.pr_grand_total or pr_item.pr_rounded_total),
                            pr_item.pr_total,
                        ),
                        "reconciled_amount": pr_paid.get(pr_item.parent, 0.0),
                        "tax_rate": po_tax_rate,
                        "schedule_date": item.schedule_date,
                        "received_qty": cumulative,
                        "pending_qty": flt(item.qty) - cumulative,
                        "delivery_sequence": f"交货{sequence}",
                        "warehouse": pr_item.warehouse,
                    }
                )

    # Append a report-level total row after all purchase orders and receipts.
    if data:
        data.append(
            {
                "name": "__total__",
                "name_display": _("合计"),
                "parent": None,
                "indent": 0,
                "is_group": 0,
                "qty": sum(flt(row.get("qty")) for row in data if row.get("indent", 0) == 0),
                "amount": sum(flt(row.get("amount")) for row in data if row.get("indent", 0) == 0),
                "reconciled_amount": sum(
                    flt(row.get("reconciled_amount")) for row in data if row.get("indent", 0) == 0
                ),
                "received_qty": sum(flt(row.get("received_qty")) for row in data if row.get("indent", 0) == 0),
                "pending_qty": sum(flt(row.get("pending_qty")) for row in data if row.get("indent", 0) == 0),
            }
        )

    return data


def _taxed(net_amount, grand_total, po_total):
    """Tax-inclusive value of a net amount, prorated from the document's grand total.

    Using grand_total * (net / po_total) instead of net * (1 + rate) keeps it correct
    whether the order's prices are tax-inclusive (tax already inside rate) or
    tax-exclusive (tax added on top), and avoids double-counting tax.
    """
    po_total = flt(po_total)
    if not po_total:
        return flt(net_amount)
    return flt(grand_total) * flt(net_amount) / po_total


def get_conditions(filters):
    conditions = []
    if filters.get("company"):
        conditions.append("AND po.company = %(company)s")
    if filters.get("supplier"):
        conditions.append("AND po.supplier = %(supplier)s")
    if filters.get("from_date"):
        conditions.append("AND po.transaction_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("AND po.transaction_date <= %(to_date)s")
    if filters.get("item_code"):
        conditions.append(
            "AND EXISTS (SELECT 1 FROM `tabPurchase Order Item` poi WHERE poi.parent = po.name AND poi.item_code = %(item_code)s)"
        )
    return " ".join(conditions)
