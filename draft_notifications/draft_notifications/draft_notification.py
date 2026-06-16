import json

import frappe
from frappe import _
from frappe.utils import get_url_to_form


RULE_DOCTYPE = "Draft Notification Rule"
LOG_DOCTYPE = "Draft Notification Log"
DESK_NOTIFICATION_DOCTYPE = "Notification Log"
ALLOWED_METHOD_PREFIXES_CONF = "draft_notification_allowed_method_prefixes"


def handle_after_insert(doc, method=None):
	handle_document_event(doc, "After Insert")


def handle_on_update(doc, method=None):
	handle_document_event(doc, "On Update")


def handle_on_submit(doc, method=None):
	handle_document_event(doc, "On Submit")


def handle_on_cancel(doc, method=None):
	handle_document_event(doc, "On Cancel")


def handle_document_event(doc, trigger_event):
	if not frappe.db.exists("DocType", RULE_DOCTYPE):
		return

	if not has_enabled_rules(doc.doctype, trigger_event):
		return

	frappe.enqueue(
		"draft_notifications.draft_notifications.draft_notification.send_draft_notifications",
		queue="short",
		enqueue_after_commit=True,
		job_id=f"draft-notification::{trigger_event}::{doc.doctype}::{doc.name}",
		deduplicate=True,
		at_front=True,
		doctype=doc.doctype,
		name=doc.name,
		trigger_event=trigger_event,
	)


def send_draft_notifications(doctype, name, trigger_event="After Insert"):
	if not frappe.db.exists(doctype, name) or not frappe.db.exists("DocType", RULE_DOCTYPE):
		return

	doc = frappe.get_doc(doctype, name)

	for rule in get_enabled_rules(doctype, trigger_event):
		try:
			send_for_rule(doc, rule)
		except Exception:
			frappe.log_error(
				title=f"Draft notification rule failed: {rule.name}",
				message=frappe.get_traceback(),
			)


def send_for_rule(doc, rule):
	channel = get_notification_channel(rule)
	candidates = []

	if channel_uses_frappe_users(channel) or channel_uses_dingtalk_private_chat(channel):
		try:
			candidates = get_candidate_users(doc, rule)
		except Exception:
			frappe.log_error(
				title=f"Draft notification recipient error: {rule.name}",
				message=frappe.get_traceback(),
			)
			return

	if channel_uses_email(channel) or channel_uses_desk(channel):
		for user in unique(candidates):
			try:
				send_to_user(
					doc,
					rule,
					user,
					send_email=channel_uses_email(channel),
					send_desk=channel_uses_desk(channel),
					notification_channel=channel,
				)
			except Exception:
				traceback = frappe.get_traceback()
				create_log(doc, rule, user=user, status="Failed", reason=traceback, notification_channel=channel)
				frappe.log_error(title=f"Draft notification failed for user {user}", message=traceback)

	if channel_uses_dingtalk_private_chat(channel):
		send_dingtalk_private_chat_for_rule(doc, rule, receiver_users=candidates)


def send_to_user(
	doc,
	rule,
	user,
	ignore_deduplicate=False,
	send_email=True,
	send_desk=True,
	notification_channel=None,
):
	user_data = get_enabled_user_data(user)
	if not user_data:
		return create_log(
			doc,
			rule,
			user=user,
			status="Skipped",
			reason="User is disabled or missing",
			notification_channel=notification_channel,
		)

	user_email = user_data.email
	if send_email and not user_email:
		return create_log(
			doc,
			rule,
			user=user,
			status="Skipped",
			reason="User has no email",
			notification_channel=notification_channel,
		)

	if not ignore_deduplicate and rule.deduplicate and already_sent(doc, rule, user):
		return create_log(
			doc,
			rule,
			user=user,
			email=user_email,
			status="Skipped",
			reason="Already sent",
			notification_channel=notification_channel,
		)

	if rule.respect_permissions and not can_read_doc(doc, user):
		return create_log(
			doc,
			rule,
			user=user,
			email=user_email,
			status="Skipped",
			reason="No read permission",
			notification_channel=notification_channel,
		)

	try:
		language = get_user_language(user)
		subject = render_subject(doc, rule, language)
		message = render_message(doc, rule, language)

		if send_desk:
			create_desk_notification(doc, rule, user, user_email, subject, message)

		if not send_email:
			return create_log(
				doc,
				rule,
				user=user,
				email=user_email,
				status="Sent",
				notification_channel=notification_channel,
			)

		email_queue = frappe.sendmail(
			recipients=[user_email],
			subject=subject,
			message=message,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			delayed=True,
		)
		log = create_log(
			doc,
			rule,
			user=user,
			email=user_email,
			status="Queued",
			email_queue=email_queue.name if email_queue else None,
			notification_channel=notification_channel,
		)
		queue_log_sync_after_commit(log)
		return log
	except Exception:
		traceback = frappe.get_traceback()
		frappe.log_error(title=f"Draft notification send failed: {doc.doctype} {doc.name}", message=traceback)
		return create_log(
			doc,
			rule,
			user=user,
			email=user_email,
			status="Failed",
			reason=traceback,
			notification_channel=notification_channel,
		)


def send_dingtalk_private_chat_for_rule(doc, rule, receiver_users=None):
	from draft_notifications.dingtalk_robot import send_private_chat_notification

	try:
		result = send_private_chat_notification(doc, rule, receiver_users=receiver_users)
		if not result:
			return None

		results = result if isinstance(result, list) else [result]
		failed_results = [item for item in results if item.get("failed_list")]
		status = "Failed" if failed_results else "Sent"
		reason = json.dumps(failed_results, ensure_ascii=False) if failed_results else None
		return create_log(
			doc,
			rule,
			status=status,
			reason=reason,
			notification_channel="DingTalk Private Chat",
			dingtalk_status=status,
			dingtalk_open_ding_id="",
			dingtalk_error=reason,
		)
	except Exception:
		traceback = frappe.get_traceback()
		create_log(
			doc,
			rule,
			status="Failed",
			reason=traceback,
			notification_channel="DingTalk Private Chat",
			dingtalk_status="Failed",
			dingtalk_error=traceback,
		)
		frappe.log_error(title=f"DingTalk private chat notification failed: {rule.name}", message=traceback)
		return None


def get_notification_channel(rule):
	return rule.get("notification_channel") or "Email"


def channel_uses_email(channel):
	return channel in ("Email", "Email + DingTalk Private Chat", "Email + DingTalk DING")


def channel_uses_desk(channel):
	return channel in (
		"Email",
		"Desk",
		"Email + DingTalk Private Chat",
		"Desk + DingTalk Private Chat",
		"Email + DingTalk DING",
		"Desk + DingTalk DING",
	)


def channel_uses_dingtalk_private_chat(channel):
	return channel in (
		"DingTalk Private Chat",
		"Email + DingTalk Private Chat",
		"Desk + DingTalk Private Chat",
		"DingTalk DING",
		"Email + DingTalk DING",
		"Desk + DingTalk DING",
	)


def channel_uses_frappe_users(channel):
	return channel_uses_email(channel) or channel_uses_desk(channel)


def has_enabled_rules(doctype, trigger_event="After Insert"):
	return bool(
		frappe.db.exists(
			RULE_DOCTYPE,
			{
				"enabled": 1,
				"document_type": doctype,
				"trigger_event": trigger_event,
			},
		)
	)


def get_enabled_rules(doctype, trigger_event="After Insert"):
	return frappe.get_all(
		RULE_DOCTYPE,
		filters={
			"enabled": 1,
			"document_type": doctype,
			"trigger_event": trigger_event,
		},
		fields=[
			"name",
			"trigger_event",
			"recipient_type",
			"role",
			"user_field",
			"custom_method",
			"respect_permissions",
			"include_owner",
			"deduplicate",
			"subject",
			"message",
			"subject_zh",
			"message_zh",
			"subject_en",
			"message_en",
			"subject_es",
			"message_es",
			"notification_channel",
			"dingtalk_config",
			"dingtalk_message_template",
			"dingtalk_message_zh",
			"dingtalk_message_en",
			"dingtalk_message_es",
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
	user_data = get_enabled_user_data(user)
	return user_data.email if user_data and user_data.email else None


def get_enabled_user_data(user):
	if not user:
		return None

	user_data = frappe.db.get_value(
		"User",
		user,
		["enabled", "email"],
		as_dict=True,
	)
	if not user_data or not user_data.enabled:
		return None

	return user_data


def get_user_language(user):
	return frappe.db.get_value("User", user, "language") or frappe.local.lang or "en"


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


def render_subject(doc, rule, language=None):
	template = get_localized_template(rule, "subject", language) or "New draft {{ doc.doctype }} {{ doc.name }}"
	return frappe.render_template(template, get_template_context(doc))


def render_message(doc, rule, language=None):
	template = get_localized_template(rule, "message", language) or (
		"<p>A new draft {{ doc.doctype }} has been created: "
		'<a href="{{ doc_url }}">{{ doc.name }}</a></p>'
	)
	return frappe.render_template(template, get_template_context(doc))


def get_localized_template(rule, fieldname, language=None):
	language_key = get_language_key(language)
	localized_value = rule.get(f"{fieldname}_{language_key}") if language_key else None
	return localized_value or rule.get(fieldname)


def get_language_key(language):
	if not language:
		return None

	language = language.replace("_", "-").lower()
	if language.startswith("zh"):
		return "zh"
	if language.startswith("es"):
		return "es"
	if language.startswith("en"):
		return "en"
	return None


def get_template_context(doc):
	return {
		"doc": doc,
		"doc_url": get_url_to_form(doc.doctype, doc.name),
	}


def create_log(
	doc,
	rule,
	status,
	user=None,
	email=None,
	reason=None,
	email_queue=None,
	notification_channel=None,
	dingtalk_status=None,
	dingtalk_open_ding_id=None,
	dingtalk_error=None,
):
	if not frappe.db.exists("DocType", LOG_DOCTYPE):
		return

	try:
		return frappe.get_doc(
			{
				"doctype": LOG_DOCTYPE,
				"rule": rule.name,
				"notification_channel": notification_channel or get_notification_channel(rule),
				"status": status,
				"user": user,
				"email": email,
				"email_queue": email_queue,
				"reference_doctype": doc.doctype,
				"reference_name": doc.name,
				"dingtalk_status": dingtalk_status,
				"dingtalk_open_ding_id": dingtalk_open_ding_id,
				"dingtalk_error": dingtalk_error,
				"reason": reason,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Failed to create Draft Notification Log", message=frappe.get_traceback())
		return None


def queue_log_sync_after_commit(log):
	if not log or not log.email_queue:
		return

	frappe.db.after_commit.add(lambda: send_email_queue_and_sync_log(log.email_queue, log.name))


def send_email_queue_and_sync_log(email_queue_name, log_name):
	try:
		if frappe.db.exists("Email Queue", email_queue_name):
			frappe.get_doc("Email Queue", email_queue_name).send()
	except Exception:
		frappe.log_error(
			title=f"Draft notification email send failed: {email_queue_name}",
			message=frappe.get_traceback(),
		)
	finally:
		log = frappe.db.get_value(LOG_DOCTYPE, log_name, ["name", "email", "email_queue"], as_dict=True)
		if log:
			sync_log_from_email_queue(log)
			frappe.db.commit()


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
	rule = frappe.get_doc(RULE_DOCTYPE, log.rule)

	if log.notification_channel in ("DingTalk Private Chat", "DingTalk DING") or (not log.user and channel_uses_dingtalk_private_chat(get_notification_channel(rule))):
		retry_log = send_dingtalk_private_chat_for_rule(doc, rule)
	else:
		retry_log = send_to_user(doc, rule, log.user, ignore_deduplicate=True, notification_channel=log.notification_channel)

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
