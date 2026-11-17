"""Manual accounting voucher entry backed by ERPNext Journal Entry.

The legacy immediate-posting API is intentionally retained.  New callers use
the draft APIs below so incomplete data never enters ERPNext's Journal Entry,
GL Entry, or statutory-voucher flows.
"""

from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate


ENTRY_ROLES = ("Accounts User", "Accounts Manager", "China Finance Manager", "System Manager")
MAX_AMOUNT = Decimal("9999999.99")
MAX_ATTACHMENT_COUNT = 999
VOUCHER_WORDS = ("收", "付", "转", "记")
MANAGER_ROLES = ("Accounts Manager", "China Finance Manager", "System Manager")


def _ensure_entry_access():
	frappe.only_for(ENTRY_ROLES)
	if not frappe.has_permission("Journal Entry", "create"):
		frappe.throw(_("无权新增记账凭证"), frappe.PermissionError)


def _parse_amount(value, row_number, label):
	try:
		amount = Decimal(str(value or 0))
	except (InvalidOperation, ValueError):
		frappe.throw(_("第 {0} 行{1}金额格式无效").format(row_number, label))
	if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2 or amount > MAX_AMOUNT:
		frappe.throw(_("第 {0} 行{1}金额超出允许范围").format(row_number, label))
	return amount


def _get_settings(company):
	settings = frappe.db.get_value(
		"China Finance Settings",
		{"company": company, "enabled": 1},
		[
			"name",
			"activation_date",
			"voucher_mode",
			"default_voucher_word",
			"enforce_role_separation",
		],
		as_dict=True,
	)
	if not settings:
		frappe.throw(_("当前公司尚未启用中国财务"))
	return settings


def _allowed_voucher_words(settings):
	return ("记",) if settings.voucher_mode == "统一记字" else VOUCHER_WORDS


def _validate_voucher_word(value, settings):
	value = (value or settings.default_voucher_word or "记").strip()
	if value not in _allowed_voucher_words(settings):
		frappe.throw(
			_("凭证字 {0} 不符合当前公司的凭证字模式").format(value)
		)
	return value


def _parse_attachment_count(value):
	try:
		count = int(str(value if value not in (None, "") else 0))
	except (TypeError, ValueError):
		frappe.throw(_("附件张数必须是非负整数"))
	if count < 0 or count > MAX_ATTACHMENT_COUNT:
		frappe.throw(_("附件张数必须在 0 到 {0} 之间").format(MAX_ATTACHMENT_COUNT))
	return count


def _parse_payload(payload):
	if isinstance(payload, str):
		payload = frappe.parse_json(payload)
	if not isinstance(payload, dict):
		frappe.throw(_("草稿内容格式无效"))
	return frappe._dict(payload)


def _can_manage_draft(draft):
	return draft.prepared_by == frappe.session.user or any(role in frappe.get_roles() for role in MANAGER_ROLES)


def _get_draft(name, require_owner=True):
	if not name or not frappe.db.exists("China Manual Voucher Draft", name):
		frappe.throw(_("手工凭证草稿不存在"))
	draft = frappe.get_doc("China Manual Voucher Draft", name)
	if require_owner and not _can_manage_draft(draft):
		frappe.throw(_("无权操作该手工凭证草稿"), frappe.PermissionError)
	return draft


def _normalize_draft_entries(entries):
	if isinstance(entries, str):
		entries = frappe.parse_json(entries)
	if entries in (None, ""):
		return []
	if not isinstance(entries, list):
		frappe.throw(_("凭证明细格式无效"))

	normalized = []
	for index, row in enumerate(entries, start=1):
		row = frappe._dict(row or {})
		debit = _parse_amount(row.get("debit"), index, _("借方"))
		credit = _parse_amount(row.get("credit"), index, _("贷方"))
		account = (row.get("account") or "").strip()
		remarks = (row.get("remarks") or "").strip()
		if not account and not debit and not credit and not remarks:
			continue
		normalized.append(
			{
				"remarks": remarks,
				"account": account,
				"debit": flt(debit),
				"credit": flt(credit),
			}
		)
	return normalized


def _validate_submission_entries(entries, company, remarks=None):
	clean_entries = []
	total_debit = total_credit = Decimal("0")
	for index, row in enumerate(entries, start=1):
		account = row.get("account")
		debit = _parse_amount(row.get("debit"), index, _("借方"))
		credit = _parse_amount(row.get("credit"), index, _("贷方"))
		if not account and not debit and not credit and not row.get("remarks"):
			continue
		if not account:
			frappe.throw(_("第 {0} 行未选择会计科目").format(index))
		if (debit and credit) or not (debit or credit):
			frappe.throw(_("第 {0} 行必须且只能填写借方或贷方金额").format(index))
		if not frappe.db.exists("Account", {"name": account, "company": company, "is_group": 0}):
			frappe.throw(_("第 {0} 行会计科目无效或不属于当前公司").format(index))
		clean_entries.append(
			{
				"account": account,
				"debit_in_account_currency": flt(debit),
				"credit_in_account_currency": flt(credit),
				"user_remark": row.get("remarks") or remarks,
			}
		)
		total_debit += debit
		total_credit += credit

	if len(clean_entries) < 2:
		frappe.throw(_("凭证至少需要两条分录"))
	if total_debit != total_credit:
		frappe.throw(_("借贷不平衡：借方 {0}，贷方 {1}").format(total_debit, total_credit))
	return clean_entries


def _workflow_is_ready(doctype="Journal Entry"):
	return bool(frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}, "name"))


def _closed_accounting_period(company, posting_date, doctype="Journal Entry"):
	"""Return the currently effective accounting-period lock, if any.

	This mirrors ERPNext's lookup for a UI pre-check only.  Journal Entry /
	GL Entry continue to perform the authoritative validation when submitted.
	"""
	rows = frappe.db.sql(
		"""
		SELECT ap.name, ap.exempted_role
		FROM `tabAccounting Period` ap
		INNER JOIN `tabClosed Document` cd ON cd.parent = ap.name
		WHERE ap.company = %s
			AND ap.disabled = 0
			AND cd.closed = 1
			AND cd.document_type = %s
			AND %s BETWEEN ap.start_date AND ap.end_date
		ORDER BY ap.start_date DESC
		LIMIT 1
		""",
		(company, doctype, posting_date),
		as_dict=True,
	)
	if not rows:
		return None
	period = rows[0]
	if period.exempted_role and period.exempted_role in frappe.get_roles():
		return None
	return period.name


def _posting_precheck(company, posting_date, settings):
	posting_date = getdate(posting_date)
	result = {
		"can_post": True,
		"blocking_reason": "",
		"accounts_frozen_till_date": None,
		"closed_accounting_periods": [],
	}
	if posting_date > getdate(nowdate()):
		result.update(
			can_post=False,
			blocking_reason=_("记账日期不能晚于今天：{0}").format(posting_date),
		)
		return result
	if posting_date < getdate(settings.activation_date):
		result.update(
			can_post=False,
			blocking_reason=_("凭证日期不能早于中国财务启用日期"),
		)
		return result

	frozen_till = frappe.db.get_value("Company", company, "accounts_frozen_till_date")
	result["accounts_frozen_till_date"] = str(frozen_till) if frozen_till else None
	if frozen_till and posting_date <= getdate(frozen_till):
		allowed_role = frappe.db.get_value("Company", company, "role_allowed_for_frozen_entries")
		if allowed_role not in frappe.get_roles() or frappe.session.user == "Administrator":
			result.update(
				can_post=False,
				blocking_reason=_("会计期间已冻结至 {0}").format(frozen_till),
			)
			return result

	closed_period = _closed_accounting_period(company, posting_date)
	if closed_period:
		result.update(
			can_post=False,
			blocking_reason=_("会计期间已关闭：{0}").format(closed_period),
			closed_accounting_periods=[closed_period],
		)
	return result


@frappe.whitelist()
def get_manual_voucher_context(company=None):
	"""Return the defaults required by the Chinese-style voucher page."""
	_ensure_entry_access()
	company = company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("请先选择公司"))
	frappe.has_permission("Company", "read", company, throw=True)

	settings = _get_settings(company)
	return {
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"posting_date": nowdate(),
		"voucher_word": settings.default_voucher_word or "记",
		"activation_date": str(settings.activation_date),
	}


@frappe.whitelist()
def get_manual_voucher_context_v2(company=None, posting_date=None):
	"""Return the new page context plus a non-authoritative posting pre-check."""
	context = get_manual_voucher_context(company)
	settings = _get_settings(context["company"])
	posting_date = posting_date or context["posting_date"]
	context.update(
		{
			"posting_date": str(getdate(posting_date)),
			"voucher_words": list(_allowed_voucher_words(settings)),
			"voucher_mode": settings.voucher_mode,
			"enforce_role_separation": cint(settings.enforce_role_separation),
			"workflow_ready": _workflow_is_ready(),
			"posting_precheck": _posting_precheck(context["company"], posting_date, settings),
		}
	)
	return context


@frappe.whitelist()
def create_manual_voucher(company, posting_date, entries, remarks=None):
	"""Create a submitted Journal Entry; the standard hook creates its audit voucher."""
	_ensure_entry_access()
	frappe.has_permission("Company", "read", company, throw=True)
	if isinstance(entries, str):
		entries = frappe.parse_json(entries)
	if not isinstance(entries, list):
		frappe.throw(_("凭证明细格式无效"))

	clean_entries = _validate_submission_entries(entries, company, remarks)
	settings = _get_settings(company)
	if getdate(posting_date) > getdate(nowdate()):
		frappe.throw(_("记账日期不能晚于今天：{0}").format(getdate(posting_date)))
	if getdate(posting_date) < getdate(settings.activation_date):
		frappe.throw(_("凭证日期不能早于中国财务启用日期"))

	journal = frappe.get_doc({
		"doctype": "Journal Entry",
		"voucher_type": "Journal Entry",
		"company": company,
		"posting_date": getdate(posting_date),
		"user_remark": remarks,
		"accounts": clean_entries,
	})
	journal.insert()
	journal.submit()
	voucher = frappe.db.get_value(
		"China Accounting Voucher",
		{"source_key": f"Posting|Journal Entry|{journal.name}"},
		["name", "statutory_number"],
		as_dict=True,
	)
	return {"journal_entry": journal.name, "china_accounting_voucher": voucher}


@frappe.whitelist()
def save_manual_voucher_draft(draft=None, payload=None):
	"""Persist an editable manual-voucher draft without creating a Journal Entry."""
	_ensure_entry_access()
	payload = _parse_payload(payload)
	company = payload.get("company")
	if not company:
		frappe.throw(_("请先选择公司"))
	frappe.has_permission("Company", "read", company, throw=True)
	settings = _get_settings(company)
	posting_date = getdate(payload.get("posting_date") or nowdate())
	if posting_date > getdate(nowdate()):
		frappe.throw(_("记账日期不能晚于今天：{0}").format(posting_date))
	voucher_word = _validate_voucher_word(payload.get("voucher_word"), settings)
	attachment_count = _parse_attachment_count(payload.get("attachment_count"))
	entries = _normalize_draft_entries(payload.get("entries"))
	remarks = (payload.get("remarks") or "").strip()

	if draft:
		doc = _get_draft(draft)
		if doc.status != "Draft":
			frappe.throw(_("只有草稿状态的凭证可以继续编辑"))
		if doc.company != company:
			frappe.throw(_("草稿公司不能修改"))
	else:
		doc = frappe.new_doc("China Manual Voucher Draft")
		doc.prepared_by = frappe.session.user

	doc.update(
		{
			"company": company,
			"posting_date": posting_date,
			"voucher_word": voucher_word,
			"attachment_count": attachment_count,
			"remarks": remarks,
			"status": "Draft",
		}
	)
	doc.set("entries", entries)
	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return _draft_payload(doc)


@frappe.whitelist()
def get_manual_voucher_draft(name):
	"""Load a draft owned by the current preparer (or a finance manager)."""
	_ensure_entry_access()
	return _draft_payload(_get_draft(name))


@frappe.whitelist()
def list_my_manual_voucher_drafts(company=None):
	"""List the current preparer's editable drafts; managers may still open by name."""
	_ensure_entry_access()
	filters = {"prepared_by": frappe.session.user, "status": ["in", ("Draft", "Rejected")]}
	if company:
		frappe.has_permission("Company", "read", company, throw=True)
		filters["company"] = company
	return frappe.get_all(
		"China Manual Voucher Draft",
		filters=filters,
		fields=[
			"name",
			"company",
			"posting_date",
			"voucher_word",
			"attachment_count",
			"status",
			"modified",
		],
		order_by="modified desc",
	)


@frappe.whitelist()
def submit_manual_voucher_draft(name):
	"""Validate a draft and create the linked standard Journal Entry exactly once."""
	_ensure_entry_access()
	draft = _get_draft(name)
	if draft.source_journal_entry:
		return _submission_result(draft)
	if draft.status not in ("Draft", "Rejected"):
		frappe.throw(_("当前草稿不能提交审核"))

	settings = _get_settings(draft.company)
	if getdate(draft.posting_date) > getdate(nowdate()):
		frappe.throw(_("记账日期不能晚于今天：{0}").format(getdate(draft.posting_date)))
	if getdate(draft.posting_date) < getdate(settings.activation_date):
		frappe.throw(_("凭证日期不能早于中国财务启用日期"))
	clean_entries = _validate_submission_entries(draft.entries, draft.company, draft.remarks)
	voucher_word = _validate_voucher_word(draft.voucher_word, settings)

	if settings.enforce_role_separation and not _workflow_is_ready():
		frappe.throw(_("当前公司已启用制单审核分离，但 Journal Entry 未配置活动审批工作流"))

	journal = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": draft.company,
			"posting_date": getdate(draft.posting_date),
			"user_remark": draft.remarks,
			"accounts": clean_entries,
		}
	)
	_set_manual_journal_metadata(journal, draft.name, voucher_word, draft.attachment_count)
	journal.insert()
	draft.db_set("source_journal_entry", journal.name, update_modified=False)
	draft.db_set("submitted_on", now_datetime(), update_modified=False)
	draft.db_set("status", "Pending Review" if settings.enforce_role_separation else "Draft", update_modified=True)

	if settings.enforce_role_separation:
		return _submission_result(frappe.get_doc("China Manual Voucher Draft", draft.name))

	journal.submit()
	draft.reload()
	return _submission_result(draft)


@frappe.whitelist()
def cancel_manual_voucher_draft(name):
	"""Cancel an unposted draft; posted records stay traceable through Journal Entry."""
	_ensure_entry_access()
	draft = _get_draft(name)
	if draft.source_journal_entry:
		frappe.throw(_("已生成来源 Journal Entry 的草稿不能取消，请按原生凭证取消/冲销流程处理"))
	if draft.status not in ("Draft", "Rejected"):
		frappe.throw(_("当前草稿不能取消"))
	draft.db_set("status", "Cancelled", update_modified=True)
	return _draft_payload(frappe.get_doc("China Manual Voucher Draft", name))


def sync_manual_voucher_draft_posted(journal):
	"""Called by the existing snapshot hook after a linked Journal Entry submits."""
	if journal.doctype != "Journal Entry" or not frappe.db.has_column(
		"Journal Entry", "custom_china_manual_voucher_draft"
	):
		return
	draft_name = getattr(journal, "custom_china_manual_voucher_draft", None)
	if not draft_name or not frappe.db.exists("China Manual Voucher Draft", draft_name):
		return
	draft = frappe.get_doc("China Manual Voucher Draft", draft_name)
	if draft.source_journal_entry != journal.name:
		return
	voucher = frappe.db.get_value(
		"China Accounting Voucher",
		{"source_key": f"Posting|Journal Entry|{journal.name}"},
		"name",
	)
	draft.db_set("status", "Posted", update_modified=False)
	draft.db_set("posted_on", now_datetime(), update_modified=False)
	draft.db_set(
		"reviewed_by",
		frappe.db.get_value(
			"Workflow Action",
			{"reference_doctype": "Journal Entry", "reference_name": journal.name, "status": "Completed"},
			"completed_by",
			order_by="modified desc",
		),
		update_modified=False,
	)
	draft.db_set("reviewed_on", now_datetime() if voucher else None, update_modified=True)


def _set_manual_journal_metadata(journal, draft_name, voucher_word, attachment_count):
	"""Set additive metadata only when the migration has created the fields."""
	if frappe.db.has_column("Journal Entry", "custom_china_voucher_word"):
		journal.custom_china_voucher_word = voucher_word
	if frappe.db.has_column("Journal Entry", "custom_china_attachment_count"):
		journal.custom_china_attachment_count = attachment_count
	if frappe.db.has_column("Journal Entry", "custom_china_manual_voucher_draft"):
		journal.custom_china_manual_voucher_draft = draft_name


def _draft_payload(draft):
	return {
		"name": draft.name,
		"company": draft.company,
		"posting_date": str(draft.posting_date),
		"voucher_word": draft.voucher_word,
		"attachment_count": cint(draft.attachment_count),
		"remarks": draft.remarks or "",
		"status": draft.status,
		"source_journal_entry": draft.source_journal_entry,
		"prepared_by": draft.prepared_by,
		"reviewed_by": draft.reviewed_by,
		"entries": [
			{
				"remarks": row.remarks or "",
				"account": row.account or "",
				"debit": flt(row.debit),
				"credit": flt(row.credit),
			}
			for row in draft.entries
		],
	}


def _submission_result(draft):
	voucher = None
	if draft.source_journal_entry:
		voucher = frappe.db.get_value(
			"China Accounting Voucher",
			{"source_key": f"Posting|Journal Entry|{draft.source_journal_entry}"},
			["name", "statutory_number"],
			as_dict=True,
		)
	return {
		"draft": _draft_payload(draft),
		"journal_entry": draft.source_journal_entry,
		"china_accounting_voucher": voucher,
	}
