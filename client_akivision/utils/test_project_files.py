from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from client_akivision.utils.project_files import _validate_pdf, validate_project_files


class TestProjectFiles(IntegrationTestCase):
	def test_rejects_non_pdf_extension(self):
		file_doc = frappe._dict(file_name="notes.txt", file_url="/private/files/notes.txt", is_private=1)
		with self.assertRaises(frappe.ValidationError):
			_validate_pdf(file_doc)

	def test_rejects_public_pdf(self):
		file_doc = frappe._dict(file_name="notes.pdf", file_url="/files/notes.pdf", is_private=0)
		with self.assertRaises(frappe.ValidationError):
			_validate_pdf(file_doc)

	def test_rejects_fake_pdf_content(self):
		file_doc = frappe._dict(
			file_name="notes.pdf",
			file_url="/private/files/notes.pdf",
			is_private=1,
			get_content=lambda: b"not a pdf",
		)
		with self.assertRaises(frappe.ValidationError):
			_validate_pdf(file_doc)

	def test_populates_server_audit_fields_for_new_file(self):
		row = frappe._dict(name="new-project-file-item-1", file_name="", pdf_file="/private/files/spec.pdf")
		doc = frappe._dict(name="PROJ-0001", custom_project_files=[row], get_doc_before_save=lambda: None)
		file_doc = frappe._dict(
			file_name="spec.pdf",
			file_url=row.pdf_file,
			is_private=1,
			attached_to_doctype="Project",
			attached_to_name=doc.name,
			get_content=lambda: b"%PDF-1.7\n",
		)
		with patch("client_akivision.utils.project_files._get_file", return_value=file_doc):
			validate_project_files(doc)

		self.assertEqual(row.file_name, "spec.pdf")
		self.assertEqual(row.uploaded_by, frappe.session.user)
		self.assertTrue(row.uploaded_on)

	def test_rejects_file_attached_to_another_project(self):
		row = frappe._dict(name="new-project-file-item-1", file_name="spec.pdf", pdf_file="/private/files/spec.pdf")
		doc = frappe._dict(name="PROJ-0001", custom_project_files=[row], get_doc_before_save=lambda: None)
		file_doc = MagicMock(
			file_name="spec.pdf",
			file_url=row.pdf_file,
			is_private=1,
			attached_to_doctype="Project",
			attached_to_name="PROJ-OTHER",
		)
		file_doc.get_content.return_value = b"%PDF-1.7\n"
		with patch("client_akivision.utils.project_files._get_file", return_value=file_doc):
			with self.assertRaises(frappe.ValidationError):
				validate_project_files(doc)
