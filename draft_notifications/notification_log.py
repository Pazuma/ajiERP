import frappe
from frappe.utils import cint


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
