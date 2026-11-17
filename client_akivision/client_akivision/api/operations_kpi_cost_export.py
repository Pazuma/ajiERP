"""Cost-only export sharing the page's permission checks and calculations."""
from io import BytesIO

import frappe
import xlsxwriter
from frappe.desk.utils import provide_binary_file

from client_akivision.client_akivision.api.operations_kpi_cost import normalise_cost_filters
from client_akivision.utils.operations_kpi_cost import build_cost_dashboard_data
from client_akivision.utils.operations_kpi_cost_permissions import check_cost_dashboard_access


@frappe.whitelist()
def export_cost_dashboard(filters=None):
    check_cost_dashboard_access()
    filters = normalise_cost_filters(filters)
    # Same bounded full calculation; output every product, not only the displayed page.
    filters.page, filters.page_length = 1, 20000
    data = build_cost_dashboard_data(filters)
    provide_binary_file("成本看板", "xlsx", build_cost_workbook(data))


def build_cost_workbook(data):
    output = BytesIO()
    book = xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False,
                                        "strings_to_urls": False})
    bold = book.add_format({"bold": True, "bg_color": "#DBEAFE"})
    def sheet(name, headers, rows):
        ws = book.add_worksheet(name)
        ws.freeze_panes(1, 0)
        ws.set_column(0, len(headers) - 1, 24)
        ws.write_row(0, 0, headers, bold)
        for index, row in enumerate(rows, 1):
            ws.write_row(index, 0, row)
    sheet("口径与范围", ["项目", "内容"],
        [[k, v] for k, v in data["filters"].items()] + [["币种", data["currency"]],
        ["生成时间", data["generated_at"]]] + [["提示", s] for s in data["warnings"]])
    labels = {"gross_margin": "参考综合毛利率", "budget_execution": "主营成本预算执行率",
        "rework_scrap_ratio": "返工报废成本占比", "unit_cost_variance": "单位成本差异率",
        "revenue": "参考收入", "sales_cost": "参考销售成本", "gross_profit": "参考毛利",
        "production_cost": "根工单成品入库成本"}
    sheet("成本指标", ["指标", "值（比例为小数）", "单位", "状态", "说明"],
        [[labels[k], m["value"], m["datatype"], m["status"], m["reason"]] for k, m in data["metrics"].items()])
    sheet("财务月度趋势", ["月份", "参考收入", "参考销售成本", "参考毛利"],
        [[r[k] for k in ("period", "revenue", "sales_cost", "gross_profit")] for r in data["trend"]])
    sheet("产品制造入库成本", ["产品", "库存单位", "入库数量", "入库成本", "单位成本", "凭证数"],
        [[r[k] for k in ("item_code", "stock_uom", "qty", "production_cost", "unit_cost", "entry_count")]
         for r in data["product_rows"]])
    sheet("参考科目范围", ["科目", "科目类型"], [[r["name"], r["account_type"]] for r in data["accounts"]])
    book.close()
    return output.getvalue()
