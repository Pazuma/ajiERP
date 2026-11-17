"""Personal node workbench. Scope is enforced on every backend entry point."""
import frappe
from frappe.utils import cint, getdate, now_datetime, today
from client_akivision.utils.project_business_progress import MODE, refresh_project


def is_admin():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def require_user():
	if frappe.session.user == "Guest":
		frappe.throw("请先登录", frappe.PermissionError)


def validate_project(doc):
	if doc.is_new() and not doc.flags.get("keep_legacy_progress"):
		doc.custom_progress_mode = MODE
	old = doc.get_doc_before_save()
	if old and old.get("custom_progress_mode") == MODE and doc.get("custom_progress_mode") != MODE:
		frappe.throw("业务完成模式不能直接切回旧模式，以免绕过业务完成条件")
	if doc.get("custom_progress_mode") != MODE:
		return
	if old and old.custom_project_stage != doc.custom_project_stage:
		frappe.throw("项目阶段请通过项目操作按钮变更")
	if old and old.get("custom_progress_mode") != MODE and any(r.status != "待开始" for r in old.custom_project_progress_items):
		frappe.throw("已执行的旧模式项目暂不支持直接切换，请先核实历史节点后迁移")
	old_rows = {r.name: r for r in old.custom_project_progress_items} if old else {}
	for row in doc.custom_project_progress_items:
		if not row.responsible_user:
			frappe.throw(f"节点 {row.subject} 请填写负责人")
		user = frappe.db.get_value("User", row.responsible_user, ["enabled", "user_type"], as_dict=True)
		if not user or not user.enabled or user.user_type != "System User":
			frappe.throw("节点负责人必须是启用的系统用户")
		previous = old_rows.get(row.name)
		if previous:
			for field in ("status", "actual_started_on", "actual_completed_on", "completed_by", "completion_source", "business_exception", "business_details", "business_summary"):
				if row.get(field) != previous.get(field):
					frappe.throw("节点执行状态请通过工作台操作，不能直接修改")
		elif row.status not in (None, "", "待开始") or row.actual_completed_on:
			frappe.throw("新增节点必须从待开始状态执行")
	if old and old.get("custom_progress_mode") == MODE:
		for previous in old_rows.values():
			if previous.name not in {r.name for r in doc.custom_project_progress_items} and previous.status != "待开始":
				frappe.throw("已执行节点不能直接删除")


def checked_node(node):
	require_user()
	row = frappe.get_doc("Project Progress Item", node)
	if not is_admin() and row.responsible_user != frappe.session.user:
		frappe.throw("只能查看和处理自己的节点", frappe.PermissionError)
	project = frappe.get_doc("Project", row.parent)
	if not is_admin():
		project.check_permission("read")
	if project.custom_progress_mode != MODE:
		frappe.throw("该节点使用旧交接模式，请在项目页面处理")
	return row, project


@frappe.whitelist()
def get_nodes(start=0, page_length=30, responsible_user=None, status=None):
	require_user()
	filters = {"parenttype": "Project"}
	if not is_admin():
		filters["responsible_user"] = frappe.session.user
	elif responsible_user:
		filters["responsible_user"] = responsible_user
	# Scope and project permission are applied before totals or pagination.
	rows = frappe.get_all("Project Progress Item", filters=filters, fields=["name", "parent", "subject", "responsible_user", "status", "expected_end_date", "business_summary", "business_details", "business_exception", "last_synced_on", "idx"], order_by="expected_end_date asc, parent asc, idx asc")
	visible = []
	projects = {}
	for row in rows:
		if row.parent not in projects:
			projects[row.parent] = frappe.get_doc("Project", row.parent)
		project = projects[row.parent]
		if project.custom_progress_mode != MODE or (not is_admin() and not frappe.has_permission("Project", "read", doc=project)):
			continue
		row.project_name = project.project_name
		details = frappe.parse_json(row.pop("business_details", None) or "[]")
		# Return only the precomputed collaboration summary, never raw source details.
		row.business_summary = row.business_summary or ""
		row.business_exception = 0
		row.project_stage = project.custom_project_stage
		row.unlocked = not any(r.idx < row.idx and (r.status != "已完成" or r.business_exception) for r in project.custom_project_progress_items)
		row.overdue = bool(row.status != "已完成" and row.expected_end_date and getdate(row.expected_end_date) < getdate(today()))
		row.bucket = "已完成" if row.status == "已完成" else "已暂停" if project.custom_project_stage in ("暂停", "已取消", "已完成") or project.status in ("Completed", "Cancelled") else "未来节点" if not row.unlocked or project.custom_project_stage != "进行中" else "待处理" if row.status == "待开始" else "进行中"
		visible.append(row)
	counts = {key: sum(1 for r in visible if r.bucket == key) for key in ("待处理", "进行中", "未来节点", "已完成", "已暂停")}
	counts["已逾期"] = sum(1 for r in visible if r.overdue and r.bucket in ("待处理", "进行中"))
	counts["业务异常"] = 0
	if status:
		visible = [r for r in visible if (False if status == "业务异常" else r.overdue and r.bucket in ("待处理", "进行中") if status == "已逾期" else r.bucket == status)]
	start, length = max(cint(start), 0), min(max(cint(page_length), 1), 100)
	return {"rows": visible[start:start+length], "total": len(visible), "counts": counts, "is_admin": is_admin()}


@frappe.whitelist()
def get_node_details(node):
	row, project = checked_node(node)
	details = frappe.parse_json(row.business_details or "[]")
	# Check source-document access separately; never leak invoice or order details.
	safe_details = []
	for detail in details:
		if not detail.get("doctype") or not frappe.has_permission(detail["doctype"], "read", doc=detail.get("name")):
			safe_details.append({"summary": "关联单据无查看权限"})
			continue
		detail = dict(detail)
		if detail.get("doctype") == "Purchase Order" and not frappe.has_permission("Quality Inspection", "read"):
			detail.pop("quality", None)
		safe_details.append(detail)
	return {"subject": row.subject, "status": row.status, "exception": "", "details": safe_details}


@frappe.whitelist()
def act_on_node(node, action, reason=None):
	row, project = checked_node(node)
	frappe.db.sql("select name from `tabProject` where name=%s for update", project.name)
	row.reload()
	project.reload()
	if not is_admin() and row.responsible_user != frappe.session.user:
		frappe.throw("节点负责人已变更", frappe.PermissionError)
	if project.custom_project_stage != "进行中" or project.status in ("Completed", "Cancelled"):
		frappe.throw("项目未启动、已暂停或已结束，不能执行节点")
	if action == "return":
		if not is_admin() or not (reason or "").strip():
			frappe.throw("只有管理员可填写原因退回节点", frappe.PermissionError)
		frappe.db.set_value("Project Progress Item", node, {"status": "进行中", "actual_completed_on": None, "completed_by": None, "completion_source": None})
	else:
		if any(r.idx < row.idx and (r.status != "已完成" or r.business_exception) for r in project.custom_project_progress_items):
			frappe.throw("前置节点尚未完成或存在异常")
		if row.status == "已完成":
			frappe.throw("节点已经完成")
		values = {"status": "进行中", "actual_started_on": row.actual_started_on or now_datetime()}
		if action == "complete":
			if not (reason or "").strip():
				frappe.throw("请填写完成说明")
			if row.completion_rule != "Manual":
				links = frappe.get_all("Project Progress Reference", filters={"project": project.name, "progress_item": node}, fields=["reference_doctype", "reference_name"])
				if not links or any(l.reference_doctype in ("Purchase Order", "Work Order", "Sales Order") or frappe.db.get_value(l.reference_doctype, l.reference_name, "docstatus") != 1 for l in links):
					frappe.throw("业务节点按实际履约自动完成；其他单据须全部提交")
			values.update(status="已完成", actual_completed_on=now_datetime(), completed_by=frappe.session.user, completion_source="人工确认", remarks=reason)
		elif action != "start":
			frappe.throw("不支持的操作")
		frappe.db.set_value("Project Progress Item", node, values)
	project.add_comment("Info", frappe.as_json({"node": node, "action": action, "reason": reason, "user": frappe.session.user}))
	refresh_project(project.name)
	return {"ok": True}


@frappe.whitelist()
def refresh_node(node):
	row, project = checked_node(node)
	refresh_project(project.name)
	return {"ok": True}


@frappe.whitelist()
def close_project(project):
	require_user()
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	if not is_admin() and "Projects Manager" not in frappe.get_roles():
		frappe.throw("只有项目管理人员可确认结项", frappe.PermissionError)
	refresh_project(project)
	doc.reload()
	if doc.custom_project_stage != "进行中" or not doc.custom_project_progress_items or any(r.status != "已完成" or r.business_exception for r in doc.custom_project_progress_items):
		frappe.throw("全部节点完成且无业务异常后才能结项")
	doc.db_set("custom_project_stage", "已完成")
	doc.add_comment("Info", "项目全部业务节点完成，管理人员确认结项")
	return {"ok": True}
