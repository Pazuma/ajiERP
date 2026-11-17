"""Read-only tax calculation data for the China Finance tax worksheet."""

import re
from calendar import monthrange

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


TAX_USERS = ("System Manager", "Accounts Manager", "China Finance Manager", "China Tax User", "China Finance Auditor")
PERIOD_PATTERN = re.compile(r"^(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])$")
TAX_TYPES = {
	"VAT": _("增值税计算表"),
	"SURCHARGE": _("附加税费"),
	"STAMP_DUTY": _("印花税"),
	"UNION_DUES": _("工会经费"),
	"CORPORATE_INCOME_TAX": _("企业所得税"),
	"WATER_FUND": _("水利建设基金"),
	"DISABILITY_FUND": _("残疾人就业保障金"),
}


def _validate_request(company, period, tax_type):
	frappe.only_for(TAX_USERS)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("请选择有效的公司"))
	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("无权查看该公司的税务数据"), frappe.PermissionError)
	match = PERIOD_PATTERN.fullmatch(period or "")
	if not match:
		frappe.throw(_("税款所属期必须为 YYYY-MM"))
	if tax_type not in TAX_TYPES:
		frappe.throw(_("不支持的税种"))
	year, month = int(match.group("year")), int(match.group("month"))
	return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"


def _amount(sql, values):
	amount, count = frappe.db.sql(sql, values)[0]
	return flt(amount), count


def _row(line_no, item_code, label, amount=None, source=None, source_filters=None, emphasis=False):
	return {
		"line_no": line_no,
		"item_code": item_code,
		"label": label,
		"amount": amount,
		"source": source,
		"source_filters": source_filters or {},
		"emphasis": emphasis,
		"unit": "percent" if "(%)" in label else "number" if item_code in ("HEADCOUNT", "ACTUAL") else "currency",
		"source_state": "missing" if amount is None else "automatic",
	}


def _vat_calculation(company, period, from_date, to_date):
	output_tax, output_count = _amount(
		"""SELECT COALESCE(SUM(tax_amount), 0), COUNT(*) FROM `tabChina Tax Invoice`
			WHERE company=%s AND direction='销项' AND docstatus=1 AND invoice_status!='作废'
			AND invoice_date BETWEEN %s AND %s""",
		(company, from_date, to_date),
	)
	input_tax, input_count = _amount(
		"""SELECT COALESCE(SUM(tax_amount), 0), COUNT(*) FROM `tabChina Input Tax Deduction Batch`
		WHERE company=%s AND status='Deducted' AND deduction_period BETWEEN %s AND %s""",
		(company, from_date, to_date),
	)
	# The net amount is a diagnostic preview until carry-forward and adjustments are verified.
	payable = None
	credit = None
	rows = [
		_row(1, "OUTPUT_VAT", _("本期销项税额"), output_tax, "China VAT Ledger", {"company": company, "from_date": from_date, "to_date": to_date, "direction": "销项", "exclude_void": 1}),
		_row(2, "DEDUCTIBLE_INPUT_VAT", _("本期可抵扣进项税额"), input_tax, "China Input Tax Deduction Batch", {"company": company, "deduction_period": ["between", [from_date, to_date]], "status": "Deducted"}),
		_row(3, "INPUT_VAT_TRANSFER", _("进项税额转出"), None),
		_row(4, "OPENING_VAT_CREDIT", _("上期留抵税额"), None),
		_row(5, "VAT_EXEMPT", _("本期免交增值税"), None),
		_row(6, "VAT_PREPAID", _("本期已预缴增值税"), None),
		_row(7, "VAT_PAYABLE", _("本期应交增值税"), payable, emphasis=True),
		_row(8, "CLOSING_VAT_CREDIT", _("期末留抵税额"), credit, emphasis=True),
		_row(9, "VAT_BALANCE", _("本期应补缴增值税"), None, emphasis=True),
	]
	for row, count in zip(rows, (output_count, input_count)):
		row.update(source_count=count, source_state="automatic" if count else "missing")
	# Include identities and modification timestamps: an equal total does not
	# guarantee that the underlying evidence is still the reviewed evidence.
	rows[0]["source_records"] = frappe.get_all("China Tax Invoice", filters={"company": company,
		"direction": "销项", "docstatus": 1, "invoice_status": ["!=", "作废"],
		"invoice_date": ["between", [from_date, to_date]]}, fields=["name", "modified", "tax_amount"], order_by="name")
	rows[1]["source_records"] = frappe.get_all("China Input Tax Deduction Batch", filters={"company": company,
		"status": "Deducted", "deduction_period": ["between", [from_date, to_date]]},
		fields=["name", "modified", "tax_amount"], order_by="name")
	return {
		"status": "Incomplete",
		"is_estimate": True,
		"rows": rows,
		"warnings": [_('无来源记录不等于已核实零申报；销售发票不直接计入本表。上期留抵、进项转出、减免及预缴需财务核实。')],
	}


def _incomplete_calculation(tax_type):
	# A worksheet is not a filing figure until each required input and policy is verified.
	definitions = {
		"SURCHARGE": [("PAID_CONSUMPTION", "本期实际缴纳的消费税"), ("PAID_VAT", "本期实际缴纳的增值税"),
			("BASE", "计税依据"), ("CITY_RATE", "城建税的税率(%)"), ("CITY_DISCOUNT", "城建税折扣率(%)"),
			("CITY_PAYABLE", "本期应交城建税"), ("EDUCATION_RATE", "教育附加的税率(%)"),
			("EDUCATION_DISCOUNT", "教育附加的折扣率(%)"), ("EDUCATION_PAYABLE", "本期应交教育费附加"),
			("LOCAL_RATE", "地方教育附加的税率(%)"), ("LOCAL_DISCOUNT", "地方教育附加的折扣率(%)"),
			("LOCAL_PAYABLE", "本期应交地方教育费附加")],
		"STAMP_DUTY": [("BASE", "本期应税凭证计税金额"), ("RATE", "印花税税率(%)"),
			("DISCOUNT", "印花税折扣率(%)"), ("PAYABLE", "本期应交印花税")],
		"UNION_DUES": [("WAGES", "本期应发工资"), ("RATE", "工会经费费率(%)"),
			("DISCOUNT", "工会经费折扣率(%)"), ("PAYABLE", "本期应计提工会经费")],
		"CORPORATE_INCOME_TAX": [("PROFIT", "利润总额"), ("LOSS", "弥补以前年度亏损"),
			("TAXABLE", "实际利润额"), ("PORTION", "计税比例(%)"), ("RATE", "税率(%)"),
			("PAYABLE", "应纳所得税"), ("PREPAID", "本年实际已缴纳所得税额"),
			("PRIOR", "上年所得税汇算清缴应补（退）金额"), ("BALANCE", "本期应缴所得税额")],
		"WATER_FUND": [("BASE", "本期计费收入"), ("RATE", "地方水利建设基金费率(%)"),
			("DISCOUNT", "地方水利建设基金计费比率(%)"), ("PAYABLE", "本期应交地方水利建设基金")],
		"DISABILITY_FUND": [("WAGES", "上年在职职工工资"), ("HEADCOUNT", "上年在职职工人数"),
			("REQUIRED", "应安排残疾人就业比例(%)"), ("ACTUAL", "上年实际安排残疾人就业人数"),
			("AVERAGE", "上年在职职工年平均工资"), ("RATE", "计费比例(%)"),
			("PAYABLE", "本期应缴残疾人就业保障金")],
	}
	return {
		"status": "Incomplete",
		"is_estimate": True,
		"rows": [_row(index, code, _(label), None, emphasis=code in ("PAYABLE", "BALANCE", "CITY_PAYABLE", "EDUCATION_PAYABLE", "LOCAL_PAYABLE"))
			for index, (code, label) in enumerate(definitions[tax_type], 1)],
		"warnings": [_('{0}尚缺已核实计税依据及公司适用政策，不能用于申报复核。').format(TAX_TYPES[tax_type])],
	}


@frappe.whitelist()
def get_tax_calculation(company, period, tax_type="VAT"):
	"""Return a stable, read-only calculation contract for one tax type and period."""
	from_date, to_date = _validate_request(company, period, tax_type)
	result = _vat_calculation(company, period, from_date, to_date) if tax_type == "VAT" else _incomplete_calculation(tax_type)
	from china_finance.services.tax_worksheet import apply_worksheet
	result = apply_worksheet(company, period, tax_type, result)
	return {
		"company": company,
		"period": period,
		"tax_type": tax_type,
		"tax_type_label": TAX_TYPES[tax_type],
		"currency": frappe.db.get_value("Company", company, "default_currency") or "CNY",
		"calculated_at": now_datetime(),
		**result,
	}
