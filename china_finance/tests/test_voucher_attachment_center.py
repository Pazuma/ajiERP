import frappe
from frappe.tests.utils import FrappeTestCase

from china_finance.services.voucher_attachment_center import _date_range


class TestVoucherAttachmentCenter(FrappeTestCase):
	def test_month_filter_uses_complete_month(self):
		start, end = _date_range(frappe._dict(month="2026-02"))
		self.assertEqual(str(start), "2026-02-01")
		self.assertEqual(str(end), "2026-02-28")

	def test_custom_date_filter_is_inclusive(self):
		start, end = _date_range(frappe._dict(from_date="2026-01-02", to_date="2026-03-04"))
		self.assertEqual(str(start), "2026-01-02")
		self.assertEqual(str(end), "2026-03-04")

	def test_rejects_reversed_date_range(self):
		with self.assertRaises(frappe.ValidationError):
			_date_range(frappe._dict(from_date="2026-03-04", to_date="2026-01-02"))
