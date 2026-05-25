import frappe
from frappe.utils import get_url_to_form


RULE_DOCTYPE = "Draft Notification Rule"
LOG_DOCTYPE = "Draft Notification Log"


def handle_after_insert(doc, method=None):
	if doc.docstatus != 0 or not frappe.db.exists("DocType", RULE_DOCTYPE):
		return

	if not has_enabled_rules(doc.doctype):
		return

	frappe.enqueue(
		"draft_notifications.draft_notifications.draft_notification.send_draft_notifications",
		queue="short",
		enqueue_after_commit=True,
		job_id=f"draft-notification::{doc.doctype}::{doc.name}",
		deduplicate=True,
		doctype=doc.doctype,
		name=doc.name,
	)


def send_draft_notifications(doctype, name):
	if not frappe.db.exists(doctype, name) or not frappe.db.exists("DocType", RULE_DOCTYPE):
		return

	doc = frappe.get_doc(doctype, name)
	if doc.docstatus != 0:
		return

	for rule in get_enabled_rules(doctype):
		send_for_rule(doc, rule)


def send_for_rule(doc, rule):
	try:
		candidates = get_candidate_users(doc, rule)
	except Exception:
		frappe.log_error(
			title=f"Draft notification recipient error: {rule.name}",
			message=frappe.get_traceback(),
		)
		return

	for user in unique(candidates):
		try:
			send_to_user(doc, rule, user)
		except Exception:
			traceback = frappe.get_traceback()
			create_log(doc, rule, user=user, status="Failed", reason=traceback)
			frappe.log_error(title=f"Draft notification failed for user {user}", message=traceback)


def send_to_user(doc, rule, user):
	user_email = get_enabled_user_email(user)
	if not user_email:
		create_log(doc, rule, user=user, status="Skipped", reason="User is disabled or has no email")
		return

	if rule.deduplicate and already_sent(doc, rule, user):
		create_log(doc, rule, user=user, email=user_email, status="Skipped", reason="Already sent")
		return

	if rule.respect_permissions and not can_read_doc(doc, user):
		create_log(doc, rule, user=user, email=user_email, status="Skipped", reason="No read permission")
		return

	try:
		email_queue = frappe.sendmail(
			recipients=[user_email],
			subject=render_subject(doc, rule),
			message=render_message(doc, rule),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			delayed=True,
		)
		status, reason = send_email_queue_now(email_queue)
		create_log(
			doc,
			rule,
			user=user,
			email=user_email,
			status=status,
			reason=reason,
			email_queue=email_queue.name if email_queue else None,
		)
	except Exception:
		traceback = frappe.get_traceback()
		create_log(doc, rule, user=user, email=user_email, status="Failed", reason=traceback)
		frappe.log_error(title=f"Draft notification send failed: {doc.doctype} {doc.name}", message=traceback)


def send_email_queue_now(email_queue):
	if not email_queue:
		return "Queued", None

	try:
		email_queue.send()
	except Exception:
		frappe.log_error(title=f"Immediate draft notification email failed: {email_queue.name}", message=frappe.get_traceback())

	queue = frappe.db.get_value("Email Queue", email_queue.name, ["status", "error"], as_dict=True)
	if not queue:
		return "Queued", None

	if queue.status == "Sent":
		return "Sent", None
	if queue.status == "Error":
		return "Failed", queue.error or "Email Queue status is Error"
	if queue.status == "Partially Sent":
		return "Failed", queue.error or "Email Queue was partially sent"

	return "Queued", queue.error


def has_enabled_rules(doctype):
	return bool(
		frappe.db.exists(
			RULE_DOCTYPE,
			{
				"enabled": 1,
				"document_type": doctype,
			},
		)
	)


def get_enabled_rules(doctype):
	return frappe.get_all(
		RULE_DOCTYPE,
		filters={
			"enabled": 1,
			"document_type": doctype,
		},
		fields=[
			"name",
			"recipient_type",
			"role",
			"user_field",
			"custom_method",
			"respect_permissions",
			"include_owner",
			"deduplicate",
			"subject",
			"message",
		],
	)


def get_candidate_users(doc, rule):
	users = []

	if rule.recipient_type == "Fixed Users":
		users.extend(get_fixed_users(rule.name))
	elif rule.recipient_type == "Users With Role":
		users.extend(get_users_with_role(rule.role))
	elif rule.recipient_type == "User Field":
		users.append(doc.get(rule.user_field))
	elif rule.recipient_type == "Owner":
		users.append(doc.owner)
	elif rule.recipient_type == "Custom Method":
		users.extend(as_list(frappe.get_attr(rule.custom_method)(doc)))

	if rule.include_owner:
		users.append(doc.owner)

	return [user for user in users if user and user not in ("Guest", "Administrator")]


def get_fixed_users(rule_name):
	rule = frappe.get_doc(RULE_DOCTYPE, rule_name)
	return [row.user for row in rule.fixed_recipients if row.user]


def get_users_with_role(role):
	if not role:
		return []

	return frappe.get_all(
		"Has Role",
		filters={
			"role": role,
			"parenttype": "User",
		},
		pluck="parent",
	)


def get_enabled_user_email(user):
	if not user:
		return None

	user_data = frappe.db.get_value(
		"User",
		user,
		["enabled", "email"],
		as_dict=True,
	)
	if not user_data or not user_data.enabled or not user_data.email:
		return None

	return user_data.email


def can_read_doc(doc, user):
	return frappe.has_permission(
		doc.doctype,
		"read",
		doc=doc,
		user=user,
	)


def already_sent(doc, rule, user):
	if not frappe.db.exists("DocType", LOG_DOCTYPE):
		return False

	return bool(
		frappe.db.exists(
			LOG_DOCTYPE,
			{
				"rule": rule.name,
				"reference_doctype": doc.doctype,
				"reference_name": doc.name,
				"user": user,
				"status": ["in", ["Queued", "Sent"]],
			},
		)
	)


def render_subject(doc, rule):
	template = rule.subject or "New draft {{ doc.doctype }} {{ doc.name }}"
	return frappe.render_template(template, get_template_context(doc))


def render_message(doc, rule):
	template = rule.message or (
		"<p>A new draft {{ doc.doctype }} has been created: "
		'<a href="{{ doc_url }}">{{ doc.name }}</a></p>'
	)
	return frappe.render_template(template, get_template_context(doc))


def get_template_context(doc):
	return {
		"doc": doc,
		"doc_url": get_url_to_form(doc.doctype, doc.name),
	}


def create_log(doc, rule, status, user=None, email=None, reason=None, email_queue=None):
	if not frappe.db.exists("DocType", LOG_DOCTYPE):
		return

	try:
		frappe.get_doc(
			{
				"doctype": LOG_DOCTYPE,
				"rule": rule.name,
				"status": status,
				"user": user,
				"email": email,
				"email_queue": email_queue,
				"reference_doctype": doc.doctype,
				"reference_name": doc.name,
				"reason": reason,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Failed to create Draft Notification Log", message=frappe.get_traceback())


def sync_queued_logs():
	if not frappe.db.exists("DocType", LOG_DOCTYPE):
		return

	logs = frappe.get_all(
		LOG_DOCTYPE,
		filters={
			"status": "Queued",
			"email_queue": ["is", "set"],
		},
		fields=["name", "email", "email_queue"],
		limit=200,
	)

	for log in logs:
		sync_log_from_email_queue(log)


def sync_log_from_email_queue(log):
	if not frappe.db.exists("Email Queue", log.email_queue):
		frappe.db.set_value(LOG_DOCTYPE, log.name, {"status": "Failed", "reason": "Email Queue record not found"})
		return

	queue = frappe.db.get_value("Email Queue", log.email_queue, ["status", "error"], as_dict=True)
	if not queue:
		return

	if queue.status == "Sent":
		frappe.db.set_value(LOG_DOCTYPE, log.name, {"status": "Sent", "reason": None})
	elif queue.status == "Error":
		frappe.db.set_value(
			LOG_DOCTYPE,
			log.name,
			{
				"status": "Failed",
				"reason": queue.error or "Email Queue status is Error",
			},
		)
	elif queue.status == "Partially Sent":
		sync_partially_sent_log(log, queue)


def sync_partially_sent_log(log, queue):
	recipient = frappe.db.get_value(
		"Email Queue Recipient",
		{
			"parent": log.email_queue,
			"recipient": log.email,
		},
		["status", "error"],
		as_dict=True,
	)

	if not recipient:
		frappe.db.set_value(LOG_DOCTYPE, log.name, {"status": "Failed", "reason": "Recipient not found in Email Queue"})
	elif recipient.status == "Sent":
		frappe.db.set_value(LOG_DOCTYPE, log.name, {"status": "Sent", "reason": None})
	else:
		frappe.db.set_value(
			LOG_DOCTYPE,
			log.name,
			{
				"status": "Failed",
				"reason": recipient.error or queue.error or "Email Queue was partially sent",
			},
		)


def as_list(value):
	if not value:
		return []
	if isinstance(value, str):
		return [value]
	return list(value)


def unique(values):
	seen = set()
	result = []
	for value in values:
		if value in seen:
			continue
		seen.add(value)
		result.append(value)
	return result
