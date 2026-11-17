"""Transactional management-accounting tests; no GL, payroll or bank writes."""

from uuid import uuid4

import frappe
from frappe.utils import nowdate

import china_finance.tests.test_sales_order_finance_accounting as source_fixtures
from china_finance.services.sales_commission import (
	approve_margin_basis, confirm_commission, create_commission_draft,
	create_commission_revision, effective_state,
)
from china_finance.services.sales_commission_payments import (
	confirm_disbursement, confirm_receipt_allocation, get_release_context, void_receipt_allocation,
)
from china_finance.services.sales_commission_permissions import SHEET, RECEIPT, PAYMENT
from china_finance.services.sales_commission_reports import execute


class TestSalesCommission(source_fixtures.TestSalesOrderFinanceAccounting):
	# Reuse only source fixture helpers; inherited finance regressions also remain
	# valid and run against the same transactional source documents.
	def setUp(self):
		super().setUp()
		self.person = self._person()
		self.second_person = self._person()
		frappe.db.set_value("Sales Order", self.order.name, dict(custom_sales_person=self.person,
			base_net_total=10000, base_grand_total=11300, net_total=10000, grand_total=11300))
		frappe.db.set_value("Sales Invoice", self.invoice.name, dict(base_net_total=10000, base_grand_total=11300, grand_total=11300))

	def _person(self, employee=None):
		doc = frappe.get_doc(dict(doctype="Sales Person", name="TEST-COM-" + uuid4().hex[:12],
			sales_person_name="TEST-COM-" + uuid4().hex[:12], enabled=1, is_group=0, employee=employee))
		doc.db_insert()
		return doc.name

	def _sheet(self, rate=2, **values):
		doc = frappe.get_doc(SHEET, create_commission_draft(self.order.name))
		doc.sales_people[0].commission_rate = rate
		doc.update(values)
		doc.save()
		return doc

	def _confirm(self, doc):
		confirm_commission(doc.name, str(doc.modified))
		return doc.reload()

	def _receipt(self, amount=5650, **values):
		doc = frappe.get_doc(dict(doctype=RECEIPT, sales_order=self.order.name, source_type="人工核实",
			source_reference="TEST-RECEIPT-" + uuid4().hex, direction="收款", amount=amount,
			verified_source_amount=11300, reason="测试财务已核实凭据", evidence="/private/files/test-evidence.pdf", posting_date=nowdate()))
		doc.update(values)
		doc.insert()
		return doc

	def _payment(self, sheet, amount=100, **values):
		doc = frappe.get_doc(dict(doctype=PAYMENT, sales_order=self.order.name, commission_sheet=sheet.name,
			sales_person=self.person, direction="发放", amount=amount, posting_date=nowdate(),
			payment_reference="TEST-PAY-" + uuid4().hex, evidence="/private/files/test-evidence.pdf"))
		doc.update(values)
		doc.insert()
		return doc

	def test_commission_multi_person_and_revision_delta(self):
		doc = self._sheet()
		doc.append("sales_people", dict(sales_person=self.second_person, commission_rate=1, remark="协作"))
		doc.save()
		self._confirm(doc)
		self.assertEqual(doc.commission_total, 300)
		self.assertEqual(create_commission_draft(self.order.name), doc.name)
		revision = frappe.get_doc(SHEET, create_commission_revision(doc.name, "调整比例"))
		revision.sales_people[0].commission_rate = 1.5
		revision.save()
		self._confirm(revision)
		self.assertEqual(revision.commission_total, 250)
		self.assertEqual(revision.commission_delta, -50)
		self.assertEqual(frappe.db.get_value(SHEET, doc.name, "status"), "已替代")
		rows = execute(dict(company=self.company, mode="期间计提变动", sales_order=self.order.name, from_date=nowdate(), to_date=nowdate()))[1]
		self.assertEqual(sum(row["period_amount"] for row in rows), 250)

	def test_commission_status_injection_and_history_immutable(self):
		doc = self._sheet()
		doc.flags.commission_confirm = True
		doc.status = "已确认"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		doc.reload()
		self._confirm(doc)
		doc.sales_people[0].commission_rate = 20
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_commission_missing_sources_and_invalid_double_ratio(self):
		doc = self._sheet(basis_type="实际回款金额")
		self.assertFalse(doc.source_ready)
		with self.assertRaises(frappe.ValidationError):
			self._confirm(doc)
		receipt = self._receipt()
		confirm_receipt_allocation(receipt.name, str(receipt.modified))
		doc.reload()
		doc.release_condition = "随回款比例发放"
		doc.save()
		self.assertFalse(doc.source_ready)
		with self.assertRaises(frappe.ValidationError):
			self._confirm(doc)

	def test_commission_receipt_ratio_and_cross_version_paid(self):
		receipt = self._receipt()
		confirm_receipt_allocation(receipt.name, str(receipt.modified))
		doc = self._confirm(self._sheet(release_condition="随回款比例发放"))
		self.assertEqual(get_release_context(doc.name)[0].available_amount, 100)
		payment = self._payment(doc, 100)
		confirm_disbursement(payment.name, str(payment.modified))
		self.assertEqual(get_release_context(doc.name)[0].available_amount, 0)
		revision = frappe.get_doc(SHEET, create_commission_revision(doc.name, "比例提高"))
		revision.sales_people[0].commission_rate = 3
		revision.save()
		self._confirm(revision)
		self.assertEqual(get_release_context(revision.name)[0].available_amount, 50)
		excess = self._payment(revision, 51)
		with self.assertRaises(frappe.ValidationError):
			confirm_disbursement(excess.name, str(excess.modified))

	def test_commission_receipt_capacity_and_void_freeze(self):
		receipt = self._receipt(6000)
		confirm_receipt_allocation(receipt.name, str(receipt.modified))
		excess = self._receipt(6000, source_reference=receipt.source_reference)
		with self.assertRaises(frappe.ValidationError):
			confirm_receipt_allocation(excess.name, str(excess.modified))
		doc = self._confirm(self._sheet(release_condition="随回款比例发放"))
		void_receipt_allocation(receipt.name, "重复分配复核")
		self.assertEqual(effective_state(doc), "待复核")
		self.assertEqual(get_release_context(doc.name)[0].available_amount, 0)

	def test_commission_manual_basis_and_source_change(self):
		doc = self._sheet(basis_type="手工指定基数", manual_basis=2000, manual_reason="特殊协议")
		self._confirm(doc)
		self.assertEqual(doc.commission_total, 40)
		frappe.db.set_value("Sales Order", self.order.name, "base_net_total", 9000)
		self.assertEqual(effective_state(doc), "待复核")
		payment = self._payment(doc, 10)
		with self.assertRaises(frappe.ValidationError):
			confirm_disbursement(payment.name, str(payment.modified))

	def test_commission_margin_requires_finance_approval_and_detects_stale(self):
		accounting = self._complete(self._draft())
		from china_finance.services.sales_order_finance_accounting import confirm_accounting
		confirm_accounting(accounting.name, str(accounting.modified))
		doc = self._sheet(basis_type="财务确认毛利")
		self.assertFalse(doc.source_ready)
		approve_margin_basis(doc.name, str(doc.modified))
		doc.reload()
		doc.save()
		self._confirm(doc)
		self.assertEqual(doc.basis_amount, 4000)
		self.assertEqual(doc.commission_total, 80)
		frappe.db.set_value("Sales Invoice Item", self.invoice_item.name, "net_amount", 9000)
		self.assertEqual(effective_state(doc), "待复核")

	def test_commission_refund_recovery_and_payment_period(self):
		doc = self._confirm(self._sheet())
		payment = self._payment(doc, 200)
		confirm_disbursement(payment.name, str(payment.modified))
		revision = frappe.get_doc(SHEET, create_commission_revision(doc.name, "比例降低"))
		revision.sales_people[0].commission_rate = 1
		revision.save()
		self._confirm(revision)
		self.assertEqual(get_release_context(revision.name)[0].recoverable_amount, 100)
		recovery = self._payment(revision, 100, direction="追回")
		confirm_disbursement(recovery.name, str(recovery.modified))
		self.assertEqual(get_release_context(revision.name)[0].recoverable_amount, 0)
		rows = execute(dict(company=self.company, sales_order=self.order.name, mode="期间实际发放", from_date=nowdate(), to_date=nowdate()))[1]
		self.assertEqual(sum(r["period_amount"] for r in rows), 100)

	def test_commission_sales_person_only_sees_own_projection(self):
		user = frappe.get_doc(dict(doctype="User", email=f"commission-{uuid4().hex[:10]}@example.test", first_name="Commission", send_welcome_email=0,
			roles=[dict(role="Sales User")])).insert(ignore_permissions=True)
		employee = frappe.get_doc(dict(doctype="Employee", name="TEST-COM-EMP-" + uuid4().hex[:10],
			employee_name="Commission Test", company=self.company, status="Active", user_id=user.name))
		employee.db_insert()
		frappe.db.set_value("Sales Person", self.person, "employee", employee.name)
		doc = self._sheet()
		doc.append("sales_people", dict(sales_person=self.second_person, commission_rate=1, remark="协作"))
		doc.save()
		self._confirm(doc)
		frappe.set_user(user.name)
		self.assertFalse(frappe.has_permission(SHEET, "read", doc=doc.name))
		with self.assertRaises(frappe.PermissionError):
			get_release_context(doc.name)
		rows = execute(dict(company=self.company, sales_order=self.order.name), personal=True)[1]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["sales_person"], self.person)
		self.assertEqual(rows[0]["commission_amount"], 200)
		for key in ("basis_amount", "commission_rate", "source_snapshot", "margin_basis"):
			self.assertNotIn(key, rows[0])
