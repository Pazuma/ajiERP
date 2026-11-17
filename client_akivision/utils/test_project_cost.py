import frappe
from frappe.tests import IntegrationTestCase

from unittest.mock import patch

from client_akivision.utils.project_cost import (
	calculate_project_cost_detail_total,
	validate_project_cost_details,
)


def make_cost_doc(rows):
	return frappe._dict(
		custom_project_cost_details=[
			frappe._dict(idx=index, **row) for index, row in enumerate(rows, 1)
		]
	)


class TestProjectCost(IntegrationTestCase):
	@patch("client_akivision.utils.project_cost.frappe.db.sql", return_value=[[30]])
	def test_total_cost_includes_timesheets_and_manual_details(self, _sql):
		doc = make_cost_doc(
			[
				{
					"cost_type": "其他费用",
					"expense_description": "包装费",
					"amount": 20,
					"cost_date": "2026-09-15",
				}
			]
		)
		doc.name = "PROJ-0007"

		validate_project_cost_details(doc)

		self.assertEqual(doc.custom_project_cost_detail_total, 20)
		self.assertEqual(doc.total_costing_amount, 50)

	def test_calculates_material_and_non_material_cost_total(self):
		doc = make_cost_doc(
			[
				{
					"cost_type": "物料消耗",
					"item_code": "ITEM-001",
					"expense_description": "镜片 A",
					"amount": 1200,
					"cost_date": "2026-08-27",
				},
				{
					"cost_type": "测试费",
					"expense_description": "高低温测试",
					"amount": 800.25,
					"cost_date": "2026-08-27",
				},
			]
		)

		self.assertEqual(calculate_project_cost_detail_total(doc), 2000.25)
		self.assertEqual(doc.custom_project_cost_detail_total, 2000.25)

	def test_material_cost_requires_item_code(self):
		doc = make_cost_doc(
			[
				{
					"cost_type": "物料消耗",
					"expense_description": "镜片 A",
					"amount": 100,
					"cost_date": "2026-08-27",
				}
			]
		)

		with self.assertRaises(frappe.ValidationError):
			calculate_project_cost_detail_total(doc)

	def test_non_material_cost_rejects_item_code(self):
		doc = make_cost_doc(
			[
				{
					"cost_type": "测试费",
					"item_code": "ITEM-001",
					"expense_description": "高低温测试",
					"amount": 100,
					"cost_date": "2026-08-27",
				}
			]
		)

		with self.assertRaises(frappe.ValidationError):
			calculate_project_cost_detail_total(doc)

	def test_rejects_unknown_cost_type(self):
		doc = make_cost_doc(
			[
				{
					"cost_type": "未知费用",
					"expense_description": "未知费用",
					"amount": 100,
					"cost_date": "2026-08-27",
				}
			]
		)

		with self.assertRaises(frappe.ValidationError):
			calculate_project_cost_detail_total(doc)

	def test_rejects_negative_amount(self):
		doc = make_cost_doc(
			[
				{
					"cost_type": "其他费用",
					"expense_description": "服务费",
					"amount": -1,
					"cost_date": "2026-08-27",
				}
			]
		)

		with self.assertRaises(frappe.ValidationError):
			calculate_project_cost_detail_total(doc)

	def test_requires_amount_but_allows_zero(self):
		missing_amount = make_cost_doc(
			[
				{
					"cost_type": "测试费",
					"expense_description": "高低温测试",
					"cost_date": "2026-08-27",
				}
			]
		)
		with self.assertRaises(frappe.ValidationError):
			calculate_project_cost_detail_total(missing_amount)

		zero_amount = make_cost_doc(
			[
				{
					"cost_type": "测试费",
					"expense_description": "高低温测试",
					"amount": 0,
					"cost_date": "2026-08-27",
				}
			]
		)
		self.assertEqual(calculate_project_cost_detail_total(zero_amount), 0)
