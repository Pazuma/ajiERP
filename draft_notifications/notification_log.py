import frappe
from frappe.utils import cint


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_badge_state():
	"""Report expired sessions explicitly; never query notifications for guests."""
	if frappe.session.user == "Guest":
		return {"session_expired": True}
	filters = {"for_user": frappe.session.user}
	return {
		"unread_count": frappe.db.count("Notification Log", {**filters, "read": 0}),
		"latest": next(iter(frappe.get_list(
			"Notification Log",
			fields=["name", "subject", "document_type", "document_name", "link", "read", "creation"],
			filters=filters, order_by="creation desc", limit_page_length=1,
		)), None),
	}


@frappe.whitelist()
def get_notification_logs(limit: int = 20):
	"""Return current user's notification logs without HTTP caching.

	Frappe's default method is cached and Administrator can see logs for every
	user through permissions. The Desk bell needs fresh logs for the active user.
	"""
	if frappe.session.user == "Guest":
		return {"notification_logs": [], "user_info": frappe._dict()}

	limit = cint(limit) or 20
	limit = max(1, min(limit, 100))
	notification_logs = frappe.db.get_list(
		"Notification Log",
		fields=["*"],
		filters={"for_user": frappe.session.user},
		limit=limit,
		order_by="creation desc",
	)

	users = [log.from_user for log in notification_logs if log.from_user]
	users = [*set(users)]
	user_info = frappe._dict()

	for user in users:
		frappe.utils.add_user_info(user, user_info)

	return {"notification_logs": notification_logs, "user_info": user_info}
