from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from client_akivision.utils.production_reorder import (
	_get_request_item_names,
	_get_request_title,
	_has_open_request,
)


class TestProductionReorder(IntegrationTestCase):
	def test_auto_request_title_uses_item_name(self):
		self.assertEqual(
			_get_request_item_names([{"item_name": "螺丝", "item_code": "SCREW-001"}]),
			"螺丝",
		)

	def test_auto_request_title_deduplicates_multiple_items(self):
		self.assertEqual(
			_get_request_item_names(
				[
					{"item_name": "螺丝"},
					{"item_name": "螺丝"},
					{"item_name": "垫片"},
				]
			),
			"螺丝, 垫片",
		)

	def test_auto_request_title_falls_back_to_item_code(self):
		self.assertEqual(_get_request_item_names([{"item_code": "SCREW-001"}]), "SCREW-001")

	def test_auto_request_title_has_purchase_prefix(self):
		self.assertEqual(_get_request_title([{"item_name": "螺丝"}]), "采购申请-螺丝")

	def test_received_request_does_not_block_a_new_reorder_request(self):
		with patch("client_akivision.utils.production_reorder.frappe.db.sql", return_value=[]) as sql:
			self.assertFalse(_has_open_request("SCREW-001", "进行中 - T", "Purchase"))

		query = sql.call_args.args[0]
		self.assertIn("'Received'", query)
