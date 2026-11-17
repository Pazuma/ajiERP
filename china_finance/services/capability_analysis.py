import frappe
from frappe import _
from frappe.utils import flt

TYPES = {"SOLVENCY": _("偿债能力分析"), "OPERATION": _("运营能力分析"), "PROFITABILITY": _("盈利能力分析"), "DEVELOPMENT": _("发展能力分析")}

def _period_total(company, from_date, to_date, account_types=None):
	filters = [company, from_date, to_date]
	condition = ""
	if account_types:
		placeholders = ",".join(["%s"] * len(account_types)); condition = f" AND a.root_type IN ({placeholders})"; filters.extend(account_types)
	return flt(frappe.db.sql(f"""SELECT COALESCE(SUM(gl.debit-gl.credit),0) FROM `tabGL Entry` gl LEFT JOIN `tabAccount` a ON a.name=gl.account WHERE gl.company=%s AND gl.posting_date BETWEEN %s AND %s AND gl.is_cancelled=0 {condition}""", filters)[0][0])

def _row(no, indicator, formula, value, reference, description):
	return {"line_no": no, "indicator": indicator, "formula": formula, "value": value, "display_value": "--" if value is None else f"{value:.2%}", "reference": reference, "description": description, "source": "GL Entry"}

def _calculate(company, start, end, comparison_start, comparison_end, kind):
	assets = abs(_period_total(company, start, end, ("Asset",))); liabilities = abs(_period_total(company, start, end, ("Liability",))); income = abs(_period_total(company, start, end, ("Income",))); expense = abs(_period_total(company, start, end, ("Expense",))); profit = income - expense
	if kind == "SOLVENCY":
		rows = [_row(1, _("资产负债率"), "负债总额/资产总额", liabilities / assets if assets else None, _("越低长期偿债压力越小"), _("反映企业长期偿债能力。")), _row(2, _("流动比率"), "流动资产/流动负债", None, "1.5~2.0", _("反映短期偿债能力。")), _row(3, _("速动比率"), "(流动资产-存货)/流动负债", None, "0.6~1.0", _("反映短期偿债能力。")), _row(4, _("现金比率"), "货币资金/流动负债", None, "0.2", _("反映即时偿债能力。"))]
	elif kind == "PROFITABILITY":
		rows = [_row(1, _("销售净利率"), "净利润/营业收入", profit / income if income else None, _("越高越好"), _("反映销售收入的收益水平。")), _row(2, _("销售毛利率"), "(营业收入-营业成本)/营业收入", None, _("越高越好"), _("衡量主营业务盈利能力。")), _row(3, _("销售费用占收入比"), "销售费用/营业收入", None, _("历史比较"), _("反映费用控制水平。")), _row(4, _("管理费用占收入比"), "管理费用/营业收入", None, _("历史比较"), _("反映管理效率。")), _row(5, _("资产利润率"), "净利润/平均资产总额", profit / assets if assets else None, _("越高越好"), _("反映资产盈利能力。"))]
	elif kind == "DEVELOPMENT":
		prior_income = abs(_period_total(company, comparison_start, comparison_end, ("Income",))); growth = (income - prior_income) / prior_income if prior_income else None
		rows = [_row(1, _("营业收入增长率"), "(本期收入-上年同期收入)/上年同期收入", growth, _("与历史期间比较"), _("衡量经营规模增长。")), _row(2, _("利润总额增长率"), "(本期利润-上年同期利润)/上年同期利润", None, _("与历史期间比较"), _("衡量盈利增长趋势。")), _row(3, _("净利润增长率"), "(本期净利润-上年同期净利润)/上年同期净利润", None, _("与历史期间比较"), _("反映价值增长速度。")), _row(4, _("股东权益增长率"), "(期末权益-期初权益)/期初权益", None, _("与历史期间比较"), _("反映资本积累能力。"))]
	else:
		rows = [_row(1, _("存货周转率"), "营业成本/平均存货", None, _("行业或历史值"), _("反映存货周转效率。")), _row(2, _("应收账款周转率"), "营业收入/平均应收账款", None, _("越高通常越好"), _("反映回款效率。")), _row(3, _("应付账款周转率"), "营业成本/平均应付账款", None, _("结合账期判断"), _("反映供应商资金使用效率。")), _row(4, _("流动资产周转率"), "营业收入/平均流动资产", None, _("历史值"), _("反映流动资产周转速度。")), _row(5, _("总资产周转率"), "营业收入/平均资产总额", income / assets if assets else None, _("历史值"), _("反映资产运营效率。"))]
	warnings = [] if any(r["value"] is not None for r in rows) else [_('部分指标缺少科目映射或期初数据，结果仅供测算。')]
	return {"status": "Calculated" if not warnings else "Incomplete", "rows": rows, "warnings": warnings}

@frappe.whitelist()
def get_capability_analysis(company, from_date, to_date, analysis_type="SOLVENCY", comparison_from_date=None, comparison_to_date=None):
	frappe.only_for(("System Manager", "Accounts Manager", "China Finance Manager", "China Finance Auditor"))
	if analysis_type not in TYPES: frappe.throw(_("不支持的分析类型"))
	if not frappe.db.exists("Company", company): frappe.throw(_("请选择有效的公司"))
	result = _calculate(company, from_date, to_date, comparison_from_date or from_date, comparison_to_date or to_date, analysis_type)
	return {"company": company, "analysis_type": analysis_type, "analysis_label": TYPES[analysis_type], "from_date": from_date, "to_date": to_date, "comparison_from_date": comparison_from_date, "comparison_to_date": comparison_to_date, **result}
