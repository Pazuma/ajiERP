import unittest

from china_finance.services.invoice_recognition import normalize_recognition_result, validate_recognized_data


class TestInvoiceRecognition(unittest.TestCase):
	def test_normalize_recognition_result_keeps_supported_fields(self):
		data = normalize_recognition_result({
			"data": {
				"invoice_type": "增值税专用发票", "invoice_number": "12345678", "invoice_date": "2026-09-04",
				"seller_name": "销售方", "seller_tax_id": "91310000TEST", "currency": "CNY",
				"items": [{"item_name": "服务费", "net_amount": "100", "tax_rate": "6", "tax_amount": "6"}],
			}
		}, "进项")
		self.assertEqual(data["direction"], "进项")
		self.assertEqual(data["currency"], "CNY")
		self.assertEqual(data["items"][0]["net_amount"], 100.0)
		self.assertEqual(data["items"][0]["tax_amount"], 6.0)

	def test_validate_requires_invoice_header_and_items(self):
		warnings = validate_recognized_data({"items": [], "currency": "CNY"}, "进项")
		self.assertTrue(any("缺少必填字段" in warning for warning in warnings))
		self.assertIn("未识别到发票明细", warnings)

	def test_normalize_defaults_invoice_status_and_currency(self):
		data = normalize_recognition_result({"invoice_number": "A1", "items": []}, "销项")
		self.assertEqual(data["currency"], "CNY")
		self.assertEqual(data["invoice_status"], "蓝票")
		self.assertEqual(data["direction"], "销项")

	def test_normalize_ignores_provider_metadata(self):
		data = normalize_recognition_result({"request_id": "ocr-1", "warnings": ["review"], "data": {"invoice_number": "A1", "items": []}}, "进项")
		self.assertNotIn("request_id", data)
		self.assertNotIn("warnings", data)
