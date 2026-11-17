from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from client_akivision.utils.sales_order_auto_fulfilment import (
	_get_pending_stock_qty,
	_notify_production_users,
	_run_non_blocking,
	create_draft_fulfilment_documents,
)


class TestSalesOrderAutoFulfilment(IntegrationTestCase):
	def test_pending_stock_qty_uses_conversion_factor(self):
		row = MagicMock(stock_qty=50, delivered_qty=3, conversion_factor=5)
		self.assertEqual(_get_pending_stock_qty(row), 35)

	def test_pending_stock_qty_never_becomes_negative(self):
		row = MagicMock(stock_qty=10, delivered_qty=12, conversion_factor=1)
		self.assertEqual(_get_pending_stock_qty(row), 0)

	def test_secondary_notification_failure_does_not_escape(self):
		callback = MagicMock(side_effect=RuntimeError("notification unavailable"))
		with (
			patch("client_akivision.utils.sales_order_auto_fulfilment.frappe.db.savepoint"),
			patch("client_akivision.utils.sales_order_auto_fulfilment.frappe.db.rollback") as rollback,
			patch("client_akivision.utils.sales_order_auto_fulfilment.frappe.log_error") as log_error,
		):
			result = _run_non_blocking("notification_test", "通知失败", callback)

		self.assertIsNone(result)
		rollback.assert_called_once_with(save_point="notification_test")
		log_error.assert_called_once()

	@patch("client_akivision.utils.sales_order_auto_fulfilment._get_production_users", return_value=[])
	def test_notification_is_skipped_without_production_users(self, _users):
		with patch(
			"frappe.desk.doctype.notification_log.notification_log.make_notification_logs"
		) as make_logs:
			_notify_production_users(frappe._dict(name="SAL-ORD-TEST"), ["WO-TEST-1"])
			make_logs.assert_not_called()

	@patch(
		"client_akivision.utils.sales_order_auto_fulfilment._get_production_users",
		return_value=["production@example.com"],
	)
	def test_multiple_work_orders_generate_one_merged_notification(self, _users):
		with patch(
			"frappe.desk.doctype.notification_log.notification_log.make_notification_logs"
		) as make_logs:
			_notify_production_users(frappe._dict(name="SAL-ORD-TEST"), ["WO-TEST-1", "WO-TEST-2"])

		make_logs.assert_called_once()
		doc, users = make_logs.call_args.args
		self.assertEqual(users, ["production@example.com"])
		self.assertEqual(doc.document_type, "Sales Order")
		self.assertEqual(doc.document_name, "SAL-ORD-TEST")
		self.assertIn("WO-TEST-1", doc.email_content)
		self.assertIn("WO-TEST-2", doc.email_content)

	@patch("client_akivision.utils.sales_order_auto_fulfilment._add_result_comment")
	@patch("client_akivision.utils.sales_order_auto_fulfilment._notify_production_users")
	@patch("client_akivision.utils.sales_order_auto_fulfilment._get_valid_bom", return_value="BOM-TEST")
	@patch("client_akivision.utils.sales_order_auto_fulfilment._is_production_candidate", return_value=True)
	@patch("client_akivision.utils.sales_order_auto_fulfilment._get_existing_work_order_qty", return_value={})
	@patch("client_akivision.utils.sales_order_auto_fulfilment._get_existing_pick_qty", return_value={})
	@patch("client_akivision.utils.sales_order_auto_fulfilment._has_open_pick_list", return_value=False)
	def test_partial_stock_creates_pick_list_and_shortage_work_order(
		self,
		_has_pick,
		_pick_qty,
		_work_qty,
		_candidate,
		_bom,
		notify,
		_comment,
	):
		item = frappe._dict(
			name="SO-ITEM-1",
			idx=1,
			item_code="FG-TEST",
			stock_qty=100,
			delivered_qty=0,
			conversion_factor=1,
			stock_reserved_qty=0,
		)
		sales_order = SimpleNamespace(
			name="SAL-ORD-TEST",
			docstatus=1,
			status="To Deliver and Bill",
			company="Test Company",
			items=[item],
		)
		pick_list = frappe._dict(
			name="PICK-TEST",
			locations=[frappe._dict(sales_order_item=item.name, stock_qty=60)],
		)
		work_order = frappe._dict(name="WO-TEST")

		with (
			patch("client_akivision.utils.sales_order_auto_fulfilment.frappe.db.sql"),
			patch("client_akivision.utils.sales_order_auto_fulfilment.frappe.get_doc", return_value=sales_order),
			patch("client_akivision.utils.sales_order_auto_fulfilment._create_draft_pick_list", return_value=pick_list),
			patch("client_akivision.utils.sales_order_auto_fulfilment._create_draft_work_order", return_value=work_order) as create_work_order,
		):
			result = create_draft_fulfilment_documents(sales_order.name)

		self.assertEqual(result["pick_list"], pick_list.name)
		self.assertEqual(result["work_orders"], [work_order.name])
		self.assertEqual(create_work_order.call_args.args[2], 40)
		notify.assert_called_once_with(sales_order, [work_order.name])
