"""Rollback-only integration checks; no business fixtures are committed."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from frappe.utils import now_datetime
from client_akivision.utils.project_business_progress import refresh_project
from client_akivision.utils.project_workbench import act_on_node, get_node_details, get_nodes, close_project
from client_akivision.utils.project_business_progress import evaluate, reached


class TestProjectWorkbench(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("project_workbench_tests")
		self.project = frappe.get_doc({"doctype": "Project", "project_name": "工作台隔离测试-" + frappe.generate_hash(length=8), "expected_start_date": "2026-10-20", "custom_project_progress_items": [
			{"subject": "采购", "weight": 50, "expected_end_date": "2026-12-01", "completion_rule": "Document Submitted", "responsible_user": "Administrator"},
			{"subject": "资料", "weight": 50, "expected_end_date": "2026-12-02", "completion_rule": "Manual", "responsible_user": "Administrator"}
		]}).insert(ignore_permissions=True)
		self.first, self.second = self.project.custom_project_progress_items
		frappe.db.set_value("Project", self.project.name, "custom_project_stage", "进行中")
		frappe.get_doc({"doctype": "Project Progress Reference", "name": frappe.generate_hash(length=10), "project": self.project.name, "progress_item": self.first.name, "milestone_code": self.first.milestone_code, "step_name": "采购", "reference_doctype": "Purchase Order", "reference_name": "TEST-SOURCE", "status": "Completed"}).db_insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="project_workbench_tests")

	def test_full_sequence_and_cancellation_preserves_history(self):
		with patch("client_akivision.utils.project_business_progress.evaluate", return_value={"doctype": "Purchase Order", "name": "TEST-SOURCE", "complete": False, "summary": "入库80%", "exception": ""}):
			refresh_project(self.project.name)
			self.first.reload()
			self.assertNotEqual(self.first.status, "已完成")
			with self.assertRaises(frappe.ValidationError):
				act_on_node(self.second.name, "start")
		with patch("client_akivision.utils.project_business_progress.evaluate", return_value={"doctype": "Purchase Order", "name": "TEST-SOURCE", "complete": True, "summary": "入库100%", "exception": ""}):
			refresh_project(self.project.name)
			self.first.reload()
			completed_on = self.first.actual_completed_on
			self.assertEqual(self.first.status, "已完成")
			act_on_node(self.second.name, "complete", "资料已交付")
			self.assertEqual(frappe.db.get_value("Project", self.project.name, "custom_project_stage"), "进行中")
			close_project(self.project.name)
		with patch("client_akivision.utils.project_business_progress.evaluate", return_value={"doctype": "Purchase Order", "name": "TEST-SOURCE", "complete": False, "summary": "退货", "exception": ""}):
			refresh_project(self.project.name)
		self.first.reload()
		self.assertEqual(self.first.status, "已完成")
		self.assertEqual(self.first.actual_completed_on, completed_on)
		self.assertTrue(self.first.business_exception)
		self.assertEqual(frappe.db.get_value("Project", self.project.name, "custom_project_stage"), "已完成")

	def test_non_admin_cannot_read_or_mutate_another_owner(self):
		with patch("client_akivision.utils.project_workbench.is_admin", return_value=False):
			frappe.db.set_value("Project Progress Item", self.first.name, "responsible_user", "Guest")
			for call in (lambda: get_node_details(self.first.name), lambda: act_on_node(self.first.name, "start")):
				with self.assertRaises(frappe.PermissionError):
					call()
			data = get_nodes(responsible_user="Guest", page_length=100)
			self.assertFalse(any(r.name == self.first.name for r in data["rows"]))

	def test_project_state_cannot_be_forged(self):
		self.project.reload()
		self.project.custom_project_progress_items[0].status = "已完成"
		with self.assertRaises(frappe.ValidationError):
			self.project.save()

	def test_sales_requires_both_percentages(self):
		doc = frappe._dict(docstatus=1, per_delivered=100, per_billed=60, skip_delivery_note=0, grand_total=100, status="To Bill")
		doc.precision = lambda field: 2
		with patch("frappe.db.exists", return_value=True), patch("frappe.get_doc", return_value=doc):
			self.assertFalse(evaluate("Sales Order", "TEST")["complete"])
			doc.per_billed = 100
			self.assertTrue(evaluate("Sales Order", "TEST")["complete"])
			doc.per_delivered = 70
			self.assertFalse(evaluate("Sales Order", "TEST")["complete"])
			doc.docstatus = 2
			self.assertFalse(evaluate("Sales Order", "TEST")["complete"])

	def test_purchase_quantities_and_rejected_return_warehouse(self):
		from client_akivision.utils.project_business_progress import evaluate_purchase
		item = frappe._dict(name="LINE", idx=1, item_code="ITEM", qty=100, conversion_factor=1, stock_uom="Nos")
		item.precision = lambda field: 2
		doc = SimpleNamespace(name="PO", items=[item], status="To Receive")
		queries = []
		def sql(query, *args, **kwargs):
			queries.append(query)
			return [(80,)] if "sum(i.qty" in query and "tabPurchase Receipt Item" in query else [(0,)] if "sum(i.qty" in query else []
		with patch("frappe.db.get_value", return_value=1), patch("frappe.get_all", return_value=[]), patch("frappe.db.sql", side_effect=sql):
			self.assertFalse(evaluate_purchase(doc)["complete"])
			self.assertTrue(any("i.warehouse=original.rejected_warehouse" in query for query in queries))
		self.assertFalse(reached(99.98, 100, 2))
		self.assertTrue(reached(100, 100, 2))


def run_checks():
	suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestProjectWorkbench)
	with patch("frappe.enqueue"):
		result = unittest.TextTestRunner(verbosity=2).run(suite)
	if not result.wasSuccessful():
		raise AssertionError("项目工作台集成检查失败")
	return {"tests": result.testsRun, "success": True}
