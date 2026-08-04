"""Naming safeguards for imported ERPNext documents."""

import re

import frappe
from frappe.model.naming import NamingSeries
from frappe.utils import cint, cstr


def sync_journal_entry_series(doc, method=None):
	"""Keep Journal Entry's native series ahead of explicitly imported names."""
	series = cstr(doc.get("naming_series"))
	if not series:
		return

	naming_series = NamingSeries(series)
	prefix = naming_series.get_prefix()
	latest = _latest_journal_entry_number(prefix)

	# During Data Import, Frappe intentionally preserves an explicit document name.
	# Include that name so the next native document cannot reuse its number.
	explicit_number = _suffix_number(doc.get("name"), prefix)
	latest = max(latest, explicit_number)

	current = cint(frappe.db.get_value("Series", prefix, "current", order_by="name") or 0)
	if latest > current:
		naming_series.update_counter(latest)


def _latest_journal_entry_number(prefix):
	names = frappe.db.sql(
		"""
		SELECT name
		FROM `tabJournal Entry`
		WHERE name LIKE %s
		""",
		(f"{prefix}%",),
		pluck="name",
	)

	return max((_suffix_number(name, prefix) for name in names), default=0)


def _suffix_number(name, prefix):
	if not name or not cstr(name).startswith(prefix):
		return 0

	match = re.fullmatch(rf"{re.escape(prefix)}(\d+)", cstr(name))
	return cint(match.group(1)) if match else 0
