import unittest
from unittest.mock import patch

import frappe
from client_akivision.client_akivision.report.china_cost_summary import china_cost_summary as report

from client_akivision.client_akivision.report.china_cost_summary.china_cost_summary import (
    allocate_cost,
    columns,
    pending_columns,
    posted_cost,
)


class TestChinaCostSummary(unittest.TestCase):
    def test_pending_includes_both_sources_and_excludes_matched(self):
        with patch.object(report, "invoice_rows", return_value=[{"status": "待核算"}, {"status": "已匹配"}]), patch.object(
            report, "work_order_rows", return_value=[{"status": "待核算"}]
        ):
            self.assertEqual([r["record_type"] for r in report.pending_rows({})], ["销售", "生产"])

    def test_cost_requires_source_document_permission(self):
        with patch.object(frappe, "has_permission", side_effect=[True, False]), patch.object(report, "read_rows") as read:
            self.assertIsNone(report.ledger_cost("Delivery Note", "hidden", "detail"))
            read.assert_not_called()

    def test_allocate_cost_rejects_overbilling_and_scales_partial_invoice(self):
        self.assertEqual(allocate_cost(120, 10, 5), 60)
        self.assertIsNone(allocate_cost(120, 10, 11))
        self.assertIsNone(allocate_cost(None, 10, 1))

    def test_posted_cost_keeps_inventory_outbound_sign(self):
        rows = [{"stock_value_difference": -25}, {"stock_value_difference": -5}]
        self.assertEqual(posted_cost(rows), 30)
        self.assertIsNone(posted_cost([]))

    def test_views_expose_traceability_fields(self):
        work_fields = {field["fieldname"] for field in columns(True)}
        pending_fields = {field["fieldname"] for field in pending_columns()}
        self.assertTrue({"work_order", "root_work_order", "source", "reason"} <= work_fields)
        self.assertTrue({"record_type", "invoice", "work_order", "status", "reason"} <= pending_fields)


def run_checks():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestChinaCostSummary)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError("China cost summary checks failed")
    return {"passed": result.testsRun, "errors": len(result.errors), "failures": len(result.failures)}


def run_site_checks():
    """Read-only execution against every readable company's three views."""
    results = []
    for company in frappe.get_list("Company", pluck="name"):
        for view in ("订单成本与毛利", "工单成本", "待核算项"):
            cols, rows, message = report.execute({"company": company, "from_date": "2026-01-01",
                "to_date": "2026-10-16", "view": view})
            assert len({c["fieldname"] for c in cols}) == len(cols)
            assert all(r.get("profit") is None for r in rows if r.get("sales_cost") is None)
            results.append({"company": company, "view": view, "rows": len(rows),
                "pending": sum(r["status"] == "待核算" for r in rows)})
    return results
