from . import business_tools
from .erp_queries import QUERY_REGISTRY, query_recent_documents_by_name


COMMON_PARAMETERS = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "description": "返回数量限制"},
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
    },
}

WARNING_PARAMETERS = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer"},
        "threshold": {"type": "integer"},
    },
}

REPORT_PARAMETERS = {
    "type": "object",
    "properties": {
        "target_month": {"type": "string", "description": "YYYY-MM"},
    },
}

OVERDUE_PARAMETERS = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer"},
    },
}

EXPENSE_PARAMETERS = {
    "type": "object",
    "properties": {
        "target_month": {"type": "string", "description": "YYYY-MM"},
        "cost_center": {"type": "string", "description": "成本中心名称，例如 'jd-test'"},
        "limit": {"type": "integer"},
    },
}

VOUCHER_PARAMETERS = {
    "type": "object",
    "properties": {
        "file_url": {
            "type": "string",
            "description": "用户上传的银行交易明细 Excel 文件路径或 URL，例如 /private/files/bank.xlsx",
        }
    },
    "required": ["file_url"],
}

TOOL_REGISTRY = {
    "get_recent_sales_orders": {
        "description": "当用户询问销售订单时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Sales_Orders",
    },
    "get_recent_sales_invoices": {
        "description": "当用户询问销售发票时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Sales_Invoices",
    },
    "get_recent_purchase_receipts": {
        "description": "当用户询问采购入库时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Purchase_Receipts",
    },
    "get_recent_delivery_notes": {
        "description": "当用户询问销售出库时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Delivery_Notes",
    },
    "get_recent_supplier_quotations": {
        "description": "当用户询问供应商报价时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Supplier_Quotations",
    },
    "get_recent_purchase_orders": {
        "description": "当用户询问采购订单时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Purchase_Orders",
    },
    "get_recent_purchase_invoices": {
        "description": "当用户询问采购发票时调用",
        "parameters": COMMON_PARAMETERS,
        "file_prefix": "ERPNext_Purchase_Invoices",
    },
    "get_low_stock_warnings": {
        "description": "当用户询问低库存预警时调用",
        "parameters": WARNING_PARAMETERS,
        "file_prefix": "ERPNext_Low_Stock",
    },
    "generate_sales_monthly_report": {
        "description": "当用户要求生成销售月报时调用",
        "parameters": REPORT_PARAMETERS,
        "file_prefix": "ERPNext_Sales_Report",
    },
    "get_overdue_sales_invoices": {
        "description": "当用户要求查询逾期账款或催款清单时调用",
        "parameters": OVERDUE_PARAMETERS,
        "file_prefix": "ERPNext_Overdue_Invoices",
        "restricted": True,
    },
    "get_financial_health_summary": {
        "description": "当用户要求查询财务体检、公司总资产、总负债、利润、亏损、财务基本盘时调用。不需要任何参数。",
        "parameters": {"type": "object", "properties": {}},
        "file_prefix": "ERPNext_Financial_Health",
        "restricted": True,
    },
    "get_cost_center_expenses": {
        "description": "当用户要求查询某个成本中心的花销、支出、烧钱情况或各项开销明细时调用",
        "parameters": EXPENSE_PARAMETERS,
        "file_prefix": "ERPNext_Cost_Center_Expenses",
        "restricted": True,
    },
    "get_asset_inventory_snapshot": {
        "description": "当用户要求查询公司固定资产、盘点家底、查看资产总值或资产清单时调用。不需要任何参数。",
        "parameters": {"type": "object", "properties": {}},
        "file_prefix": "ERPNext_Asset_Inventory",
        "restricted": True,
    },
    "get_top_valuable_assets": {
        "description": "当用户要求查询最值钱的资产、资产净值排行榜、资产贬值情况、剩余价值时调用。",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        "file_prefix": "ERPNext_Top_Assets",
        "restricted": True,
    },
    "get_employee_assets": {
        "description": "当用户要求查询某个员工名下资产、离职交接资产核查、员工保管的设备时调用。",
        "parameters": {"type": "object", "properties": {"employee_name": {"type": "string", "description": "要查询的员工名字，例如 '张三'"}}},
        "file_prefix": "ERPNext_Employee_Assets",
        "restricted": True,
    },
    "generate_financial_voucher_report": {
        "description": "当用户上传银行交易明细 Excel 并要求生成财务凭证、科目余额表、资产负债表或利润表时调用。必须把用户消息中的文件路径作为 file_url 传入。",
        "parameters": VOUCHER_PARAMETERS,
        "restricted": True,
        "returns_direct": True,
    },
}

RESTRICTED_FUNCTIONS = {
    name for name, config in TOOL_REGISTRY.items() if config.get("restricted")
}


def get_tools(is_boss):
    tools = []
    for name, config in TOOL_REGISTRY.items():
        if config.get("restricted") and not is_boss:
            continue
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": config["description"],
                "parameters": config["parameters"],
            },
        })
    return tools


def is_restricted_tool(function_name):
    return function_name in RESTRICTED_FUNCTIONS


def is_valid_tool(function_name):
    return function_name in TOOL_REGISTRY


def _dispatch_custom_tool(function_name, args, context):
    if function_name == "get_low_stock_warnings":
        return business_tools.get_low_stock_warnings(args.get("limit", 10), args.get("threshold", 10))
    if function_name == "generate_sales_monthly_report":
        return business_tools.generate_sales_monthly_report(args.get("target_month"))
    if function_name == "get_overdue_sales_invoices":
        return business_tools.get_overdue_sales_invoices(args.get("limit", 10))
    if function_name == "get_financial_health_summary":
        return business_tools.get_financial_health_summary()
    if function_name == "get_cost_center_expenses":
        return business_tools.get_cost_center_expenses(args.get("cost_center"), args.get("target_month"), args.get("limit", 10))
    if function_name == "get_asset_inventory_snapshot":
        return business_tools.get_asset_inventory_snapshot()
    if function_name == "get_top_valuable_assets":
        return business_tools.get_top_valuable_assets(args.get("limit", 5))
    if function_name == "get_employee_assets":
        return business_tools.get_employee_assets(args.get("employee_name"))
    if function_name == "generate_financial_voucher_report":
        from ai_assistant.ai_assistant import api
        file_url = args.get("file_url") or context.get("voucher_file_url")
        if not file_url:
            return {
                "status": "missing_file",
                "reply": "请先上传银行交易明细 Excel 源文件，然后再生成财务凭证报表。",
                "logs": ["大模型调用财务凭证工具但未提供 file_url。"],
            }
        ai_classifier = api.build_financial_voucher_ai_classifier(context["provider"], context["selected_model"])
        header_classifier = api.build_financial_voucher_header_classifier(context["provider"], context["selected_model"])
        tool_result = api.generate_financial_vouchers(
            file_url,
            ai_classifier=ai_classifier,
            header_classifier=header_classifier,
        )
        return api.build_financial_voucher_response(
            tool_result,
            ai_classifier=ai_classifier,
            provider_label=context["provider"]["label"],
            called_by_model=True,
        )
    raise ValueError(f"未知工具：{function_name}")


def dispatch_tool(function_name, args, context=None):
    context = context or {}
    args = args or {}
    if function_name in QUERY_REGISTRY:
        return query_recent_documents_by_name(
            function_name,
            args.get("limit", 5),
            args.get("start_date"),
            args.get("end_date"),
        )
    return _dispatch_custom_tool(function_name, args, context)


def tool_file_prefix(function_name):
    return TOOL_REGISTRY.get(function_name, {}).get("file_prefix", "ERPNext_AI_Assistant")

