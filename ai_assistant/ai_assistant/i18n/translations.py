HEADER_TRANSLATIONS = {
    "en": {
        "订单编号": "Order Number", "客户名称": "Customer Name", "交易日期": "Transaction Date", "总金额(元)": "Total Amount (CNY)", "当前状态": "Status",
        "发票编号": "Invoice Number", "开票日期": "Posting Date", "入库单编号": "Receipt Number", "供应商名称": "Supplier Name", "入库日期": "Receipt Date",
        "出库单编号": "Delivery Note Number", "出库日期": "Posting Date", "报价单编号": "Quotation Number", "报价日期": "Quotation Date",
        "采购订单编号": "PO Number", "采购发票编号": "Purchase Invoice Number", "商品编码": "Item Code", "所在仓库": "Warehouse",
        "实际库存量": "Actual Qty", "预警警戒线": "Threshold", "统计月份": "Month", "排名": "Rank", "大客户名称": "Top Customer",
        "下单总笔数": "Total Orders", "总贡献金额(元)": "Total Revenue (CNY)", "最晚收款日": "Due Date", "发票总金额(元)": "Invoice Total (CNY)",
        "拖欠未付金额(元)": "Outstanding Amount (CNY)", "已逾期天数": "Overdue Days", "体检日期": "Date", "总资产(元)": "Total Assets (CNY)",
        "总负债(元)": "Total Liabilities (CNY)", "总计收入(元)": "Total Income (CNY)", "总计支出(元)": "Total Expense (CNY)", "净利润(元)": "Net Profit (CNY)",
        "成本中心": "Cost Center", "支出科目": "Expense Account", "净支出金额(元)": "Net Expense (CNY)", "资产编号": "Asset Number",
        "资产名称": "Asset Name", "所属部门": "Department", "存放位置": "Location", "价值(元)": "Value (CNY)", "采购原值(元)": "Purchase Value (CNY)",
        "当前净值(元)": "Net Value (CNY)", "贬值率(%)": "Depreciation Rate (%)", "被查员工": "Employee", "系统登记者": "Custodian",
    },
    "es": {
        "订单编号": "Número de Pedido", "客户名称": "Cliente", "交易日期": "Fecha de Transacción", "总金额(元)": "Monto Total (CNY)", "当前状态": "Estado",
        "发票编号": "Número de Factura", "开票日期": "Fecha de Contabilización", "入库单编号": "Número de Recibo", "供应商名称": "Proveedor", "入库日期": "Fecha de Recibo",
        "出库单编号": "Número de Entrega", "出库日期": "Fecha de Contabilización", "报价单编号": "Número de Cotización", "报价日期": "Fecha de Cotización",
        "采购订单编号": "Número de OC", "采购发票编号": "Factura de Compra", "商品编码": "Código de Artículo", "所在仓库": "Almacén",
        "实际库存量": "Cant. Actual", "预警警戒线": "Umbral", "统计月份": "Mes", "排名": "Rango", "大客户名称": "Mejor Cliente",
        "下单总笔数": "Total de Pedidos", "总贡献金额(元)": "Ingresos Totales (CNY)", "最晚收款日": "Fecha de Vencimiento", "发票总金额(元)": "Total de Factura (CNY)",
        "拖欠未付金额(元)": "Monto Pendiente (CNY)", "已逾期天数": "Días de Atraso", "体检日期": "Fecha", "总资产(元)": "Activos Totales (CNY)",
        "总负债(元)": "Pasivos Totales (CNY)", "总计收入(元)": "Ingresos Totales (CNY)", "总计支出(元)": "Gastos Totales (CNY)", "净利润(元)": "Beneficio Neto (CNY)",
        "成本中心": "Centro de Costos", "支出科目": "Cuenta de Gastos", "净支出金额(元)": "Gasto Neto (CNY)", "资产编号": "Número de Activo",
        "资产名称": "Nombre del Activo", "所属部门": "Departamento", "存放位置": "Ubicación", "价值(元)": "Valor (CNY)", "采购原值(元)": "Valor de Compra (CNY)",
        "当前净值(元)": "Valor Neto (CNY)", "贬值率(%)": "Tasa de Depreciación (%)", "被查员工": "Empleado", "系统登记者": "Custodio",
    },
}


def translate_headers(data, lang):
    if lang not in HEADER_TRANSLATIONS or not data:
        return data

    translations = HEADER_TRANSLATIONS[lang]
    translated = []
    for row in data:
        translated.append({translations.get(key, key): value for key, value in row.items()})
    return translated

