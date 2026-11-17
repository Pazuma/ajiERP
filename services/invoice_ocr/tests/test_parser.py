from app.parser import parse_invoice
from app.validation import validate_invoice


def test_parse_digital_invoice_header_and_item():
	lines = [
		{"text": "电子发票（增值税专用发票）", "box": [0, 0, 100, 20], "score": 0.99},
		{"text": "发票号码：12345678901234567890", "box": [0, 20, 100, 40], "score": 0.99},
		{"text": "开票日期：2026年07月21日", "box": [0, 40, 100, 60], "score": 0.99},
		{"text": "购买方 名称：测试购买方\n统一社会信用代码/纳税人识别号：91441900BUYER001", "box": [0, 60, 100, 100], "score": 0.95},
		{"text": "*技术服务*服务费 100.00 6% 6.00", "box": [0, 100, 100, 120], "score": 0.96},
		{"text": "销售方 名称：测试销售方\n统一社会信用代码/纳税人识别号：91441900SELLER01", "box": [0, 140, 100, 180], "score": 0.95},
		{"text": "价税合计（小写）106.00", "box": [0, 180, 100, 200], "score": 0.99},
	]
	data = parse_invoice(lines)
	assert data["invoice_type"] == "数电专用发票"
	assert data["invoice_number"] == "12345678901234567890"
	assert data["invoice_date"] == "2026-07-21"
	assert data["buyer_name"] == "测试购买方"
	assert data["seller_name"] == "测试销售方"
	assert data["items"][0]["tax_rate"] == 6
	assert not validate_invoice(data)
