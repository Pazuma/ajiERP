import frappe
from frappe import _
from frappe.utils import get_url_to_form


RULE_DOCTYPE = "Draft Notification Rule"
LOG_DOCTYPE = "Draft Notification Log"
DESK_NOTIFICATION_DOCTYPE = "Notification Log"
ALLOWED_METHOD_PREFIXES_CONF = "draft_notification_allowed_method_prefixes"


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


def send_to_user(doc, rule, user, ignore_deduplicate=False):
	user_email = get_enabled_user_email(user)
	if not user_email:
		return create_log(doc, rule, user=user, status="Skipped", reason="User is disabled or has no email")

	if not ignore_deduplicate and rule.deduplicate and already_sent(doc, rule, user):
		return create_log(doc, rule, user=user, email=user_email, status="Skipped", reason="Already sent")

	if rule.respect_permissions and not can_read_doc(doc, user):
		return create_log(doc, rule, user=user, email=user_email, status="Skipped", reason="No read permission")

	try:
		subject = render_subject(doc, rule)
		message = render_message(doc, rule)
		create_desk_notification(doc, rule, user, user_email, subject, message)

		email_queue = frappe.sendmail(
			recipients=[user_email],
			subject=subject,
			message=message,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			delayed=True,
		)
		return create_log(
			doc,
			rule,
			user=user,
			email=user_email,
			status="Queued",
			email_queue=email_queue.name if email_queue else None,
		)
	except Exception:
		traceback = frappe.get_traceback()
		frappe.log_error(title=f"Draft notification send failed: {doc.doctype} {doc.name}", message=traceback)
		return create_log(doc, rule, user=user, email=user_email, status="Failed", reason=traceback)


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
		validate_custom_method(rule.custom_method)
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


def create_desk_notification(doc, rule, user, user_email, subject, message):
	if not frappe.db.exists("DocType", DESK_NOTIFICATION_DOCTYPE):
		return

	if already_notified(doc, rule, user, subject):
		return

	try:
		frappe.get_doc(
			{
				"doctype": DESK_NOTIFICATION_DOCTYPE,
				"type": "Alert",
				"for_user": user,
				"from_user": doc.owner,
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": subject,
				"email_content": message,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title=f"Draft notification desk alert failed for user {user_email}",
			message=frappe.get_traceback(),
		)


def already_notified(doc, rule, user, subject):
	if not rule.deduplicate:
		return False

	return bool(
		frappe.db.exists(
			DESK_NOTIFICATION_DOCTYPE,
			{
				"type": "Alert",
				"for_user": user,
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": subject,
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
		return frappe.get_doc(
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
		return None


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


@frappe.whitelist()
def retry_failed_log(log_name):
	if not frappe.has_permission(LOG_DOCTYPE, "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	log = frappe.get_doc(LOG_DOCTYPE, log_name)
	if log.status != "Failed":
		frappe.throw(_("Only failed draft notification logs can be retried."))

	if not log.rule or not frappe.db.exists(RULE_DOCTYPE, log.rule):
		frappe.throw(_("Draft notification rule is missing."))

	if not log.reference_doctype or not log.reference_name:
		frappe.throw(_("Reference document is missing."))

	if not frappe.db.exists(log.reference_doctype, log.reference_name):
		frappe.throw(_("Reference document no longer exists."))

	doc = frappe.get_doc(log.reference_doctype, log.reference_name)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft documents can be retried."))

	rule = frappe.get_doc(RULE_DOCTYPE, log.rule)
	retry_log = send_to_user(doc, rule, log.user, ignore_deduplicate=True)
	return {"status": retry_log.status if retry_log else None, "log": retry_log.name if retry_log else None}


@frappe.whitelist()
def retry_failed_logs(limit=100):
	if not frappe.has_permission(LOG_DOCTYPE, "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	log_names = frappe.get_all(
		LOG_DOCTYPE,
		filters={"status": "Failed"},
		pluck="name",
		limit=int(limit or 100),
	)

	retried = []
	for log_name in log_names:
		try:
			result = retry_failed_log(log_name)
			retried.append({"source_log": log_name, **result})
		except Exception:
			frappe.log_error(title=f"Draft notification retry failed: {log_name}", message=frappe.get_traceback())

	return {"retried": retried}


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
		frappe.db.set_value(
			LOG_DOCTYPE,
			log.name,
			{"status": "Failed", "reason": "Recipient not found in Email Queue"},
		)
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


def validate_custom_method(method_path):
	if not method_path:
		frappe.throw(_("Custom Method is required."))

	if method_path.startswith("_") or "._" in method_path:
		frappe.throw(_("Custom Method cannot point to private modules or methods."))

	allowed_prefixes = get_allowed_custom_method_prefixes()
	if not any(method_path.startswith(prefix) for prefix in allowed_prefixes):
		frappe.throw(
			_("Custom Method must start with one of these prefixes: {0}").format(", ".join(allowed_prefixes))
		)


def get_allowed_custom_method_prefixes():
	configured_prefixes = frappe.conf.get(ALLOWED_METHOD_PREFIXES_CONF)
	if configured_prefixes:
		if isinstance(configured_prefixes, str):
			configured_prefixes = configured_prefixes.split(",")
		return [prefix.strip() for prefix in configured_prefixes if prefix and prefix.strip()]

	return [f"{app}." for app in frappe.get_installed_apps() if app != "frappe"]


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
