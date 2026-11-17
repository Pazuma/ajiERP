import unittest
from unittest.mock import patch
from zipfile import ZipFile
from io import BytesIO

import frappe

from client_akivision.utils.operations_kpi_cost import ratio, variance, read_rows
from client_akivision.utils.operations_kpi_cost_permissions import check_cost_dashboard_access
from client_akivision.client_akivision.api.operations_kpi_cost import normalise_cost_filters, get_cost_dashboard_data
from client_akivision.client_akivision.api.operations_kpi_cost_export import build_cost_workbook


class TestOperationsKPICost(unittest.TestCase):
    def test_variances_reconcile_and_negative_savings(self):
        result = variance(12, 10, 11, 10)
        self.assertEqual(result["price"] + result["usage"], result["total"])
        self.assertEqual(variance(9, 10, 10, 10)["total"], -10)
        self.assertIsNone(ratio(100, 0))

    def test_financial_roles_required(self):
        with patch.object(frappe, "session", frappe._dict(user="cost-test@example.com")), patch.object(
            frappe, "get_roles", return_value=["Sales User"]
        ):
            with self.assertRaises(frappe.PermissionError):
                check_cost_dashboard_access()

    def test_company_and_date_validation(self):
        with patch("client_akivision.client_akivision.api.operations_kpi_cost.check_cost_company") as company:
            with self.assertRaises(frappe.ValidationError):
                normalise_cost_filters({"company": "Test", "from_date": "2026-10-16", "to_date": "2026-01-01"})
            company.assert_called_once_with("Test")

    def test_no_silent_truncation(self):
        with patch.object(frappe, "get_list", return_value=[{}] * 20001):
            with self.assertRaises(frappe.ValidationError):
                read_rows("GL Entry", {}, ["name"])

    def test_real_read_only_payload_and_export(self):
        company = frappe.get_list("Company", pluck="name", limit_page_length=1)
        if not company:
            self.skipTest("No readable company")
        data = get_cost_dashboard_data({"company": company[0], "from_date": "2026-01-01", "to_date": "2026-10-16"})
        self.assertIsNone(data["metrics"]["unit_cost_variance"]["value"])
        self.assertEqual(data["schema_version"], "cost-v1")
        # A cell starting '=' must remain text, not become an Excel formula.
        data["warnings"].append("=1+1")
        content = build_cost_workbook(data)
        with ZipFile(BytesIO(content)) as workbook:
            self.assertEqual(len([p for p in workbook.namelist() if p.startswith("xl/worksheets/sheet")]), 5)
            self.assertNotIn(b"<f>", workbook.read("xl/worksheets/sheet1.xml"))


def run_checks():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestOperationsKPICost)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError("Cost dashboard checks failed")
    return {"passed": result.testsRun, "errors": len(result.errors), "failures": len(result.failures)}
