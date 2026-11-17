import re


def validate_invoice(data):
	warnings = []
	labels = {"invoice_number": "发票号码", "invoice_date": "开票日期", "seller_name": "销售方名称", "seller_tax_id": "销售方税号", "buyer_name": "购买方名称"}
	missing = [label for field, label in labels.items() if not data.get(field)]
	if missing:
		warnings.append("缺少必填字段：" + "、".join(missing))
	if not data.get("items"):
		warnings.append("未可靠识别到发票明细，请人工录入或核对 PDF 版式")
	for field, label in (("seller_tax_id", "销售方税号"), ("buyer_tax_id", "购买方税号")):
		value = data.get(field)
		if value and not re.fullmatch(r"[0-9A-Z]{15,20}", value):
			warnings.append(f"{label}格式需人工核对")
	if data.get("confidence_score", 0) < 80:
		warnings.append("整体识别置信度较低，请逐项核对")
	return warnings
