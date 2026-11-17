import frappe
from frappe.tests.utils import FrappeTestCase

from china_finance.services.manual_voucher import (
	_allowed_voucher_words,
	_parse_attachment_count,
	_validate_voucher_word,
)
from china_finance.services.voucher import get_voucher_sequence_scope


class TestManualVoucher(FrappeTestCase):
	def test_unified_voucher_mode_only_allows_ji(self):
		settings = frappe._dict(voucher_mode="统一记字", default_voucher_word="记")

		self.assertEqual(_allowed_voucher_words(settings), ("记",))
		self.assertEqual(_validate_voucher_word("记", settings), "记")
		with self.assertRaises(frappe.ValidationError):
			_validate_voucher_word("收", settings)

	def test_collect_payment_transfer_mode_allows_all_words(self):
		settings = frappe._dict(voucher_mode="收付转记", default_voucher_word="记")

		self.assertEqual(_validate_voucher_word("收", settings), "收")
		self.assertEqual(_validate_voucher_word("付", settings), "付")
		self.assertEqual(_validate_voucher_word("转", settings), "转")
		self.assertEqual(_validate_voucher_word("记", settings), "记")

	def test_attachment_count_is_non_negative_integer(self):
		self.assertEqual(_parse_attachment_count("3"), 3)
		self.assertEqual(_parse_attachment_count(None), 0)
		with self.assertRaises(frappe.ValidationError):
			_parse_attachment_count("-1")
		with self.assertRaises(frappe.ValidationError):
			_parse_attachment_count("1.5")

	def test_voucher_sequence_scope_follows_configured_reset_period(self):
		voucher = frappe._dict(
			company="测试公司",
			fiscal_year="2026",
			accounting_period="2026-09",
			voucher_word="记",
		)

		period_scope = get_voucher_sequence_scope(voucher, frappe._dict(sequence_reset="会计期间"))
		year_scope = get_voucher_sequence_scope(voucher, frappe._dict(sequence_reset="会计年度"))

		self.assertEqual(period_scope["sequence_key"], "测试公司|2026|2026-09|记|formal")
		self.assertEqual(period_scope["accounting_period"], "2026-09")
		self.assertFalse(period_scope["annual"])
		self.assertEqual(year_scope["sequence_key"], "测试公司|2026|记|formal")
		self.assertIsNone(year_scope["accounting_period"])
		self.assertTrue(year_scope["annual"])
