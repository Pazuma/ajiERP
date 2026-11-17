"""Render an existing statement without modifying business records (run in bench sites)."""
from pathlib import Path

import frappe

from client_akivision.utils import customer_reconciliation_pdf as export


def main():
    frappe.init(site="aki_test.localhost")
    frappe.connect()
    frappe.set_user("Administrator")
    output = Path("/workspace/docs/china-finance-test-evidence/customer-statement-layout")
    output.mkdir(parents=True, exist_ok=True)
    original_render = export.render_pdf

    def capture(template, data, orientation):
        html = frappe.render_template(template, data)
        assert all(label not in html for label in ("凭证数：", "财务流水：", "数据口径：", "<th>发票</th>", "<th>开票状态</th>", "<th>收款状态</th>"))
        assert html.count("<th>") == 15
        assert "截至 2026-10-21 待结清金额" in html
        (output / "customer-statement.html").write_text(html)
        return original_render(template, data, orientation)

    try:
        export.render_pdf = capture
        export.download_saved_customer_reconciliation_statement("CNR-2026-00009")
        pdf = frappe.local.response.filecontent
        (output / "customer-statement.pdf").write_bytes(pdf)
        print(f"Validated 15 columns and hidden internal fields; PDF: {len(pdf)} bytes")
    finally:
        export.render_pdf = original_render
        frappe.db.rollback()
        frappe.destroy()


if __name__ == "__main__":
    main()
