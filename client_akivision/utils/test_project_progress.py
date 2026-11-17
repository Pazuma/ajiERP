import frappe
from frappe.tests import IntegrationTestCase

from client_akivision.utils.project_progress import _ensure_milestone_codes, _get_reference_completion, calculate_project_progress


def make_project(rows):
	return frappe._dict(
		expected_start_date="2026-09-01",
		custom_project_progress_items=[frappe._dict(parent="TEST-PROJECT", **row) for row in rows],
	)


class TestProjectProgress(IntegrationTestCase):
	def test_generates_missing_milestone_codes(self):
		rows = [
			frappe._dict(milestone_code="STEP-001"),
			frappe._dict(milestone_code=None),
			frappe._dict(milestone_code=None),
		]
		_ensure_milestone_codes(rows)
		self.assertEqual([row.milestone_code for row in rows], ["STEP-001", "STEP-002", "STEP-003"])

	def test_multiple_references_complete_on_last_document(self):
		links = [
			frappe._dict(status="Completed", actual_completed_on="2026-09-12 10:00:00"),
			frappe._dict(status="Completed", actual_completed_on="2026-09-13 14:30:00"),
		]
		self.assertEqual(_get_reference_completion(links), (True, "2026-09-13 14:30:00"))

	def test_incomplete_reference_reopens_step(self):
		links = [
			frappe._dict(status="Completed", actual_completed_on="2026-09-12 10:00:00"),
			frappe._dict(status="Cancelled", actual_completed_on=None),
		]
		self.assertEqual(_get_reference_completion(links), (False, None))

	def test_calculates_weighted_expected_and_actual_progress(self):
		doc = make_project([
			{"milestone_code": "A", "subject": "立项", "weight": 40, "expected_start_date": "2026-09-01", "expected_end_date": "2026-09-05", "completion_rule": "Manual", "status": "已完成"},
			{"milestone_code": "B", "subject": "验收", "weight": 60, "expected_start_date": "2026-09-05", "expected_end_date": "2026-09-15", "completion_rule": "Manual", "status": "进行中"},
		])
		result = calculate_project_progress(doc, "2026-09-10")
		self.assertEqual(result["actual"], 40)
		self.assertEqual(result["expected"], 70)
		self.assertEqual(result["variance"], -30)
		self.assertEqual(result["health"], "关注")

	def test_marks_overdue_incomplete_node(self):
		doc = make_project([
			{"milestone_code": "A", "subject": "验收", "weight": 100, "expected_start_date": "2026-09-01", "expected_end_date": "2026-09-05", "completion_rule": "Manual", "status": "进行中"},
		])
		self.assertEqual(calculate_project_progress(doc, "2026-09-10")["health"], "延期")

	def test_requires_total_weight_of_one_hundred(self):
		doc = make_project([
			{"milestone_code": "A", "subject": "验收", "weight": 80, "expected_end_date": "2026-09-05", "completion_rule": "Manual", "status": "待开始"},
		])
		with self.assertRaises(frappe.ValidationError):
			calculate_project_progress(doc, "2026-09-01")
