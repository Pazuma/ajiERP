import frappe

FIELDS = {
    "custom_excel_year": ("Int", "年份"), "custom_excel_month": ("Int", "月份"),
    "custom_excel_delivery_date": ("Date", "送货日期"), "custom_excel_customer_name": ("Data", "客户名称"),
    "custom_excel_customer_code": ("Data", "客户代码"), "custom_excel_order_no": ("Data", "订单号"),
    "custom_excel_delivery_note": ("Data", "送货单号"), "custom_excel_internal_model": ("Data", "内部机号"),
    "custom_excel_model": ("Data", "型号"), "custom_excel_total_amount": ("Currency", "总金额"),
    "custom_excel_unreceived_amount": ("Currency", "未收金额"), "custom_excel_agreed_payment_date": ("Date", "约定收款日期"),
    "custom_excel_receivable_days": ("Int", "应收账天数"), "custom_excel_payment_term_range": ("Data", "账期区间"),
    "custom_excel_sales_person": ("Data", "业务员"), "custom_excel_invoice_date": ("Date", "开票日期"),
    "custom_excel_invoice_issued": ("Data", "是否开发票"), "custom_excel_payment_status": ("Data", "收款状态"),
}

def execute():
    for fieldname, (fieldtype, label) in FIELDS.items():
        if not frappe.db.exists("Custom Field", {"dt": "Payment Entry", "fieldname": fieldname}):
            frappe.get_doc({"doctype": "Custom Field", "dt": "Payment Entry", "fieldname": fieldname, "fieldtype": fieldtype, "label": label, "insert_after": "custom_china_voucher_number"}).insert(ignore_permissions=True)
