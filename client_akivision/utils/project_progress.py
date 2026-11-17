"""Project milestone progress, reusable templates, and linked-document synchronization."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, date_diff, flt, getdate, now_datetime, today


SUPPORTED_REFERENCE_DOCTYPES = (
	"Sales Order", "Purchase Order", "Material Request", "BOM", "Work Order",
	"Delivery Note", "Purchase Receipt", "Sales Invoice", "Purchase Invoice", "Stock Entry",
)

PROGRESS_REFERENCE_FIELDS = [
	{"fieldname": "custom_progress_milestone_code", "label": "关联步骤", "fieldtype": "Autocomplete", "insert_after": "project"},
	{"fieldname": "custom_progress_step_name", "label": "步骤名称", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_progress_milestone_code"},
	{"fieldname": "custom_progress_actual_completed_on", "label": "实际完成时间", "fieldtype": "Datetime", "read_only": 1, "insert_after": "custom_progress_step_name"},
]

MATERIAL_REQUEST_PROGRESS_FIELDS = [
	{"fieldname": "custom_progress_project", "label": "关联项目", "fieldtype": "Link", "options": "Project", "insert_after": "schedule_date"},
	] + [
	{**field, "insert_after": "custom_progress_project" if index == 0 else field["insert_after"]}
	for index, field in enumerate(PROGRESS_REFERENCE_FIELDS)
]

PROJECT_FIELDS = [
	{"fieldname": "custom_progress_mode", "label": "节点推进模式", "fieldtype": "Select", "options": "旧交接模式\n业务完成模式", "default": "旧交接模式", "insert_after": "custom_project_stage"},
	{"fieldname": "custom_progress_tab", "label": "流程进度", "fieldtype": "Tab Break", "insert_after": "monitor_progress_tab"},
	{"fieldname": "custom_progress_section", "label": "进度计划与执行", "fieldtype": "Section Break", "insert_after": "custom_progress_tab"},
	{"fieldname": "custom_project_stage", "label": "项目阶段", "fieldtype": "Select", "options": "待处理\n进行中\n已完成\n已取消\n暂停", "default": "待处理", "read_only": 1, "insert_after": "custom_progress_section"},
	{"fieldname": "custom_progress_template", "label": "进度模板", "fieldtype": "Link", "options": "Project Progress Template", "insert_after": "custom_project_stage"},
	{"fieldname": "custom_expected_progress", "label": "预期进度", "fieldtype": "Percent", "read_only": 1, "insert_after": "custom_progress_template"},
	{"fieldname": "custom_actual_process_progress", "label": "流程实际进度", "fieldtype": "Percent", "read_only": 1, "insert_after": "custom_expected_progress"},
	{"fieldname": "custom_progress_variance", "label": "进度偏差", "fieldtype": "Percent", "read_only": 1, "insert_after": "custom_actual_process_progress"},
	{"fieldname": "custom_progress_health", "label": "进度状态", "fieldtype": "Select", "options": "未配置\n正常\n关注\n延期\n已完成", "read_only": 1, "insert_after": "custom_progress_variance"},
	{"fieldname": "custom_current_progress_step", "label": "当前进度节点", "fieldtype": "Data", "read_only": 1, "in_list_view": 1, "insert_after": "custom_progress_health"},
	{"fieldname": "custom_current_progress_duration", "label": "当前节点耗时", "fieldtype": "Data", "read_only": 1, "in_list_view": 1, "insert_after": "custom_current_progress_step"},
	{"fieldname": "custom_progress_last_synced_on", "label": "最近同步时间", "fieldtype": "Datetime", "read_only": 1, "insert_after": "custom_current_progress_duration"},
	{"fieldname": "custom_project_progress_items", "label": "进度节点", "fieldtype": "Table", "options": "Project Progress Item", "insert_after": "custom_progress_last_synced_on"},
]


def ensure_schema():
	for doctype in ("project_progress_item", "project_progress_template_item", "project_progress_template", "project_progress_reference"):
		frappe.reload_doc("client_akivision", "doctype", doctype, force=True)
	fields = {"Project": PROJECT_FIELDS, "Material Request": MATERIAL_REQUEST_PROGRESS_FIELDS}
	for doctype in SUPPORTED_REFERENCE_DOCTYPES:
		if doctype != "Material Request":
			fields[doctype] = PROGRESS_REFERENCE_FIELDS
	create_custom_fields(fields, update=True)
	for doctype in fields:
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def _project_fieldname(doctype):
	return "custom_progress_project" if doctype == "Material Request" else "project"


def _get_selected_project(doc):
	return doc.get(_project_fieldname(doc.doctype))


def _get_progress_item(project, milestone_code):
	if not project or not milestone_code:
		return None
	return frappe.db.get_value(
		"Project Progress Item",
		{"parent": project, "parenttype": "Project", "milestone_code": milestone_code},
		["name", "parent", "milestone_code", "subject", "completion_rule", "reference_doctype", "expected_end_date"],
		as_dict=True,
	)


def _normalize_milestone_code(milestone_code):
	if not milestone_code:
		return milestone_code
	return str(milestone_code).split(" - ", 1)[0].strip()


@frappe.whitelist()
def get_project_progress_steps(project, reference_doctype=None, txt=None, only_open=0):
	if not project or not frappe.db.exists("Project", project):
		return []
	if not frappe.has_permission("Project", "read", doc=project):
		frappe.throw(_("没有权限查看项目 {0}").format(project), frappe.PermissionError)
	filters = {"parent": project, "parenttype": "Project", "completion_rule": "Document Submitted"}
	rows = frappe.get_all(
		"Project Progress Item",
		filters=filters,
		fields=["name", "milestone_code", "subject", "status", "reference_doctype", "expected_end_date", "idx"],
		order_by="idx asc",
	)
	if reference_doctype:
		rows = [row for row in rows if not row.reference_doctype or row.reference_doctype == reference_doctype]
	if frappe.utils.cint(only_open):
		rows = [row for row in rows if row.status != "已完成"]
	search = (txt or "").strip().lower()
	if search:
		rows = [row for row in rows if search in row.milestone_code.lower() or search in row.subject.lower()]
	return rows


def validate_progress_selection(doc, method=None):
	if doc.doctype not in SUPPORTED_REFERENCE_DOCTYPES:
		return
	project = _get_selected_project(doc)
	milestone_code = _normalize_milestone_code(doc.get("custom_progress_milestone_code"))
	if not project:
		doc.custom_progress_milestone_code = None
		doc.custom_progress_step_name = None
		return
	if not milestone_code:
		doc.custom_progress_step_name = None
		return
	doc.custom_progress_milestone_code = milestone_code
	if not frappe.has_permission("Project", "read", doc=project):
		frappe.throw(_("没有权限关联项目 {0}").format(project), frappe.PermissionError)
	row = _get_progress_item(project, milestone_code)
	if not row:
		frappe.throw(_("关联步骤 {0} 不属于项目 {1}").format(milestone_code, project))
	if row.completion_rule != "Document Submitted":
		frappe.throw(_("手工完成节点不能关联业务单据"))
	if row.reference_doctype and row.reference_doctype != doc.doctype:
		frappe.throw(_("节点 {0} 只允许关联 {1}").format(row.subject, row.reference_doctype))
	doc.custom_progress_step_name = row.subject


def _delete_progress_references(doctype, name):
	for reference in frappe.get_all(
		"Project Progress Reference",
		filters={"reference_doctype": doctype, "reference_name": name},
		fields=["name", "project", "progress_item"],
	):
		frappe.delete_doc("Project Progress Reference", reference.name, ignore_permissions=True)
		recalculate_progress_item(reference.project, reference.progress_item)
		_sync_progress_item_reference_fields(reference.project, reference.progress_item)


def _sync_progress_item_reference_fields(project, progress_item):
	"""Mirror the latest linked document into the Project child table for visibility."""
	if not project or not progress_item:
		return
	row = frappe.get_doc("Project Progress Item", progress_item)
	links = frappe.get_all(
		"Project Progress Reference",
		filters={"project": project, "progress_item": progress_item, "status": ["!=", "Cancelled"]},
		fields=["reference_doctype", "reference_name"],
		order_by="modified desc",
		limit=1,
	)
	values = {
		"reference_doctype": links[0].reference_doctype if links else None,
		"reference_name": links[0].reference_name if links else None,
	}
	if row.reference_doctype != values["reference_doctype"]:
		row.db_set("reference_doctype", values["reference_doctype"], update_modified=False)
	if row.reference_name != values["reference_name"]:
		row.db_set("reference_name", values["reference_name"], update_modified=False)


def sync_progress_selection(doc, method=None):
	if doc.doctype not in SUPPORTED_REFERENCE_DOCTYPES or doc.is_new():
		return
	project = _get_selected_project(doc)
	milestone_code = _normalize_milestone_code(doc.get("custom_progress_milestone_code"))
	existing = frappe.db.get_value(
		"Project Progress Reference",
		{"reference_doctype": doc.doctype, "reference_name": doc.name},
		["name", "project", "progress_item"],
		as_dict=True,
	)
	if not project or not milestone_code:
		if existing:
			_delete_progress_references(doc.doctype, doc.name)
		return
	row = _get_progress_item(project, milestone_code)
	if not row:
		return
	status = "Completed" if doc.docstatus == 1 else "Cancelled" if doc.docstatus == 2 else "Draft"
	completed_on = doc.get("custom_progress_actual_completed_on") if status == "Completed" else None
	values = {
		"project": project,
		"progress_item": row.name,
		"milestone_code": row.milestone_code,
		"step_name": row.subject,
		"status": status,
		"actual_completed_on": completed_on,
		"completed_by": frappe.session.user if completed_on else None,
	}
	old_target = (existing.project, existing.progress_item) if existing else None
	if existing:
		frappe.db.set_value("Project Progress Reference", existing.name, values, update_modified=False)
	else:
		frappe.get_doc({
			"doctype": "Project Progress Reference",
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			**values,
		}).insert(ignore_permissions=True)
	if old_target and old_target != (project, row.name):
		recalculate_progress_item(*old_target)
		_sync_progress_item_reference_fields(*old_target)
	recalculate_progress_item(project, row.name)
	_sync_progress_item_reference_fields(project, row.name)


def remove_progress_selection(doc, method=None):
	if doc.doctype in SUPPORTED_REFERENCE_DOCTYPES:
		_delete_progress_references(doc.doctype, doc.name)


def _validate_reference(row):
	if row.completion_rule != "Document Submitted":
		return
	if row.reference_doctype and row.reference_doctype not in SUPPORTED_REFERENCE_DOCTYPES:
		frappe.throw(_("节点 {0} 暂不支持关联表单 {1}").format(row.subject, row.reference_doctype))
	if row.reference_doctype and not frappe.get_meta(row.reference_doctype).is_submittable:
		frappe.throw(_("节点 {0} 的关联表单必须支持提交").format(row.subject))
	if row.reference_name and not row.reference_doctype:
		frappe.throw(_("节点 {0} 选择关联单据前必须先选择表单").format(row.subject))
	if row.reference_name and not frappe.db.exists(row.reference_doctype, row.reference_name):
		frappe.throw(_("节点 {0} 的关联单据不存在").format(row.subject))
	if row.reference_name and frappe.get_meta(row.reference_doctype).has_field("project"):
		reference_project = frappe.db.get_value(row.reference_doctype, row.reference_name, "project")
		if reference_project and reference_project != row.parent:
			frappe.throw(_("节点 {0} 的关联单据属于其他项目").format(row.subject))


def _expected_contribution(row, project_start, as_of):
	start = getdate(row.expected_start_date or project_start or as_of)
	end = getdate(row.expected_end_date)
	if as_of < start:
		return 0
	if as_of >= end or end <= start:
		return flt(row.weight)
	return flt(row.weight) * (date_diff(as_of, start) / max(1, date_diff(end, start)))


def _duration_days(started_on, ended_on=None):
	if not started_on:
		return None
	end_date = getdate(ended_on or today())
	return max(1, date_diff(end_date, getdate(started_on)) + 1)


def _sync_row_duration(row, ended_on=None):
	"""Persist the natural-day duration and human-readable status for one node."""
	started_on = row.get("actual_started_on")
	if row.status == "已完成" and not started_on:
		started_on = ended_on or row.get("actual_completed_on") or now_datetime()
		row.db_set("actual_started_on", started_on, update_modified=False)
		row.actual_started_on = started_on
	elif row.status in ("进行中", "延期", "待交接") and not started_on:
		started_on = now_datetime()
		row.db_set("actual_started_on", started_on, update_modified=False)
		row.actual_started_on = started_on
	if not started_on:
		row.db_set("duration_days", 0, update_modified=False)
		row.db_set("duration_display", "-", update_modified=False)
		row.duration_days = 0
		row.duration_display = "-"
		return "-"
	days = _duration_days(started_on, ended_on or (row.get("actual_completed_on") if row.status == "已完成" else None))
	if row.status == "已完成":
		display = _("{0}天").format(days)
	elif row.status == "待交接":
		display = _("待交接，已进行{0}天").format(days)
	else:
		display = _("已进行{0}天").format(days)
	row.db_set("duration_days", days, update_modified=False)
	row.db_set("duration_display", display, update_modified=False)
	row.duration_days = days
	row.duration_display = display
	return display


def _ensure_milestone_codes(rows):
	used = {row.milestone_code for row in rows if row.milestone_code}
	next_number = 1
	for row in rows:
		if row.milestone_code:
			continue
		while f"STEP-{next_number:03d}" in used:
			next_number += 1
		row.milestone_code = f"STEP-{next_number:03d}"
		used.add(row.milestone_code)
		next_number += 1


def calculate_project_progress(doc, as_of=None):
	rows = list(doc.get("custom_project_progress_items") or [])
	_ensure_milestone_codes(rows)
	as_of = getdate(as_of or today())
	if not rows:
		doc.custom_expected_progress = 0
		doc.custom_actual_process_progress = 0
		doc.custom_progress_variance = 0
		doc.custom_progress_health = "未配置"
		doc.custom_current_progress_step = "-"
		doc.custom_current_progress_duration = "-"
		return {"expected": 0, "actual": 0, "variance": 0, "health": "未配置"}
	codes = [row.milestone_code for row in rows]
	if len(codes) != len(set(codes)):
		frappe.throw(_("项目进度节点编码不能重复"))
	for row in rows:
		if flt(row.weight) <= 0:
			frappe.throw(_("节点 {0} 的权重必须大于零").format(row.subject))
		if not row.expected_end_date:
			frappe.throw(_("节点 {0} 必须填写计划完成日期").format(row.subject))
		if row.expected_start_date and getdate(row.expected_end_date) < getdate(row.expected_start_date):
			frappe.throw(_("节点 {0} 的计划完成日期不能早于计划开始日期").format(row.subject))
		_validate_reference(row)
		has_new_references = row.name and frappe.db.exists("Project Progress Reference", {"progress_item": row.name})
		if doc.get("custom_progress_mode") != "业务完成模式" and row.completion_rule == "Document Submitted" and row.reference_doctype and row.reference_name and not has_new_references:
			submitted = frappe.db.get_value(row.reference_doctype, row.reference_name, "docstatus") == 1
			if submitted and row.status not in ("待交接", "已完成"):
				row.status = "待交接"
				row.completed_by = frappe.session.user
			elif not submitted and row.status == "待交接":
				row.status = "延期" if getdate(row.expected_end_date) < as_of else "进行中"
				row.actual_completed_on = None
				row.completed_by = None
	total_weight = sum(flt(row.weight) for row in rows)
	if abs(total_weight - 100) > 0.01:
		frappe.throw(_("项目进度节点权重合计必须等于 100%"))
	expected = sum(_expected_contribution(row, doc.expected_start_date, as_of) for row in rows)
	actual = sum(flt(row.weight) for row in rows if row.status == "已完成")
	overdue = any(row.status != "已完成" and getdate(row.expected_end_date) < as_of for row in rows)
	if actual >= 100 - 0.01:
		health = "已完成"
	elif overdue:
		health = "延期"
	elif actual + 0.01 < expected:
		health = "关注"
	else:
		health = "正常"
	doc.custom_expected_progress = flt(expected, 2)
	doc.custom_actual_process_progress = flt(actual, 2)
	doc.custom_progress_variance = flt(actual - expected, 2)
	doc.custom_progress_health = health
	current = next((row for row in rows if row.status != "已完成"), None)
	doc.custom_current_progress_step = (current.subject if current else "已完成") or "-"
	doc.custom_current_progress_duration = (current.get("duration_display") or "-") if current else "-"
	return {"expected": doc.custom_expected_progress, "actual": doc.custom_actual_process_progress, "variance": doc.custom_progress_variance, "health": health}


def validate_project_progress(doc, method=None):
	from client_akivision.utils.project_workbench import validate_project
	validate_project(doc)
	if not doc.get("custom_project_stage"):
		doc.custom_project_stage = "待处理"
	if not doc.is_new():
		current_rows = {row.name for row in doc.get("custom_project_progress_items") or [] if row.name}
		linked_rows = frappe.get_all(
			"Project Progress Reference", filters={"project": doc.name}, pluck="progress_item"
		)
		if missing := set(linked_rows) - current_rows:
			frappe.throw(_("进度节点已有关联单据，请先解除关联后再删除节点：{0}").format(", ".join(sorted(missing))))
	calculate_project_progress(doc)


def _update_row_status(row, submitted, user=None, completed_on=None):
	if frappe.db.get_value("Project", row.parent, "custom_progress_mode") == "业务完成模式":
		from client_akivision.utils.project_business_progress import refresh_project
		return refresh_project(row.parent)
	now = now_datetime()
	if submitted:
		# A submitted reference means the node is ready for handoff. The node
		# only becomes completed when the next node is explicitly started.
		row.db_set("status", "待交接", update_modified=False)
		row.db_set("actual_completed_on", None, update_modified=False)
		row.db_set("completed_by", user or frappe.session.user, update_modified=False)
	else:
		status = "延期" if row.expected_end_date and getdate(row.expected_end_date) < getdate(today()) else "进行中"
		row.db_set("status", status, update_modified=False)
		row.db_set("actual_completed_on", None, update_modified=False)
		row.db_set("completed_by", None, update_modified=False)
	row.db_set("last_synced_on", now, update_modified=False)
	row.reload()
	_sync_row_duration(row)


def recalculate_progress_item(project, progress_item):
	if frappe.db.get_value("Project", project, "custom_progress_mode") == "业务完成模式":
		from client_akivision.utils.project_business_progress import refresh_project
		return refresh_project(project)
	row = frappe.db.get_value(
		"Project Progress Item",
		{"name": progress_item, "parent": project, "parenttype": "Project"},
		["name", "expected_end_date"],
		as_dict=True,
	)
	if not row:
		return
	links = frappe.get_all(
		"Project Progress Reference",
		filters={"project": project, "progress_item": progress_item},
		fields=["status", "actual_completed_on"],
	)
	if not links:
		_persist_project_totals(project)
		return
	completed, completed_on = _get_reference_completion(links)
	_update_row_status(frappe.get_doc("Project Progress Item", progress_item), completed, completed_on=completed_on)
	_persist_project_totals(project)


def _get_reference_completion(links):
	completed = bool(links) and all(link.status == "Completed" for link in links)
	completed_on = max(
		(link.actual_completed_on for link in links if link.actual_completed_on),
		default=None,
	) if completed else None
	return completed, completed_on


def _ordered_progress_rows(doc):
	return sorted(list(doc.get("custom_project_progress_items") or []), key=lambda row: row.idx or 0)


def _finish_previous_open_step(rows, target_row, started_on):
	previous_rows = [row for row in rows if (row.idx or 0) < (target_row.idx or 0) and row.status != "已完成"]
	if not previous_rows:
		return None
	previous = previous_rows[-1]
	if not previous.get("actual_started_on"):
		previous.db_set("actual_started_on", started_on, update_modified=False)
		previous.actual_started_on = started_on
	previous.db_set("status", "已完成", update_modified=False)
	previous.db_set("actual_completed_on", started_on, update_modified=False)
	previous.db_set("completed_by", frappe.session.user, update_modified=False)
	previous.db_set("last_synced_on", now_datetime(), update_modified=False)
	previous.reload()
	_sync_row_duration(previous, started_on)
	return previous


def _start_progress_row(row, started_on=None):
	started_on = started_on or now_datetime()
	if row.status == "已完成":
		frappe.throw(_("已完成节点不能重新开始：{0}").format(row.subject))
	if not row.get("actual_started_on"):
		row.db_set("actual_started_on", started_on, update_modified=False)
		row.actual_started_on = started_on
	row.db_set("status", "进行中", update_modified=False)
	row.status = "进行中"
	row.db_set("last_synced_on", now_datetime(), update_modified=False)
	row.reload()
	_sync_row_duration(row)
	return started_on


def _persist_project_totals(project):
	doc = frappe.get_doc("Project", project)
	# Once a project is running, only start the very first node automatically.
	# Later nodes must be explicitly started, so the previous node can be closed
	# at the actual handoff time.
	if doc.get("custom_project_stage") == "进行中" and doc.get("custom_progress_mode") != "业务完成模式":
		rows = _ordered_progress_rows(doc)
		current_row = next((row for row in rows if row.status in ("进行中", "待交接", "延期")), None)
		if not current_row and rows:
			first_unfinished = next((row for row in rows if row.status != "已完成"), None)
			if first_unfinished and first_unfinished.idx == rows[0].idx and first_unfinished.status == "待开始":
				_start_progress_row(first_unfinished)
				current_row = first_unfinished
		if current_row:
			_sync_row_duration(current_row)
	for row in doc.get("custom_project_progress_items") or []:
		if row.status == "已完成":
			_sync_row_duration(row, row.get("actual_completed_on"))
	result = calculate_project_progress(doc)
	project_stage = doc.get("custom_project_stage") or "待处理"
	if result["actual"] >= 100 - 0.01 and doc.get("custom_progress_mode") != "业务完成模式":
		project_stage = "已完成"
	elif project_stage == "已完成" and doc.get("custom_progress_mode") != "业务完成模式":
		project_stage = "进行中"
	frappe.db.set_value("Project", project, {
		"percent_complete": result["actual"],
		"custom_expected_progress": result["expected"],
		"custom_actual_process_progress": result["actual"],
		"custom_progress_variance": result["variance"],
		"custom_progress_health": result["health"],
		"custom_current_progress_step": doc.get("custom_current_progress_step") or "-",
		"custom_current_progress_duration": doc.get("custom_current_progress_duration") or "-",
		"custom_progress_last_synced_on": now_datetime(),
		"custom_project_stage": project_stage,
	}, update_modified=False)
	return result


def sync_progress_from_reference(doc, method=None):
	if doc.doctype not in SUPPORTED_REFERENCE_DOCTYPES:
		return
	new_links = frappe.get_all(
		"Project Progress Reference",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
		fields=["name", "project", "progress_item"],
	)
	if new_links:
		completed = doc.docstatus == 1
		completed_on = now_datetime() if completed else None
		values = {
			"status": "Completed" if completed else "Cancelled",
			"actual_completed_on": completed_on,
			"completed_by": frappe.session.user if completed else None,
		}
		for link in new_links:
			frappe.db.set_value("Project Progress Reference", link.name, values, update_modified=False)
		if frappe.get_meta(doc.doctype).has_field("custom_progress_actual_completed_on"):
			frappe.db.set_value(doc.doctype, doc.name, "custom_progress_actual_completed_on", completed_on, update_modified=False)
			doc.custom_progress_actual_completed_on = completed_on
		for project, progress_item in {(link.project, link.progress_item) for link in new_links}:
			recalculate_progress_item(project, progress_item)
			_sync_progress_item_reference_fields(project, progress_item)
		return
	rows = frappe.get_all("Project Progress Item", filters={"reference_doctype": doc.doctype, "reference_name": doc.name, "completion_rule": "Document Submitted"}, fields=["name", "parent", "expected_end_date"])
	for row in rows:
		_update_row_status(frappe.get_doc("Project Progress Item", row.name), doc.docstatus == 1)
	for project in {row.parent for row in rows}:
		_persist_project_totals(project)


@frappe.whitelist()
def get_reference_progress_links(reference_doctype, reference_name):
	if reference_doctype not in SUPPORTED_REFERENCE_DOCTYPES:
		return []
	doc = frappe.get_doc(reference_doctype, reference_name)
	doc.check_permission("read")
	new_rows = frappe.get_all(
		"Project Progress Reference",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
		fields=["project as parent", "progress_item", "step_name as subject", "status", "actual_completed_on"],
	)
	for row in new_rows:
		row.status = "待交接" if row.status == "Completed" else "进行中"
		row.weight = frappe.db.get_value("Project Progress Item", row.progress_item, "weight") or 0
	rows = frappe.get_all(
		"Project Progress Item",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
		fields=["parent", "subject", "status", "weight", "actual_completed_on"],
		order_by="parent asc, idx asc",
	)
	seen = {(row.parent, row.subject) for row in new_rows}
	rows = new_rows + [row for row in rows if (row.parent, row.subject) not in seen]
	return [row for row in rows if frappe.has_permission("Project", "read", doc=row.parent)]


@frappe.whitelist()
def get_project_progress_reference_summary(project):
	if not project or not frappe.db.exists("Project", project):
		return []
	if not frappe.has_permission("Project", "read", doc=project):
		frappe.throw(_("没有权限查看项目 {0}").format(project), frappe.PermissionError)
	rows = frappe.get_all(
		"Project Progress Item",
		filters={"parent": project, "parenttype": "Project"},
		fields=["name", "milestone_code", "subject", "status", "actual_completed_on", "idx"],
		order_by="idx asc",
	)
	if not rows:
		return []
	links = frappe.get_all(
		"Project Progress Reference",
		filters={"project": project},
		fields=[
			"progress_item", "reference_doctype", "reference_name", "status",
			"actual_completed_on", "completed_by",
		],
		order_by="modified asc",
	)
	links_by_row = {}
	for link in links:
		if not frappe.has_permission(link.reference_doctype, "read", doc=link.reference_name):
			continue
		link.status_label = {
			"Draft": _("草稿"),
			"Completed": _("已完成"),
			"Cancelled": _("已取消"),
		}.get(link.status, link.status)
		link.doctype_label = _(link.reference_doctype)
		links_by_row.setdefault(link.progress_item, []).append(link)
	for row in rows:
		row.references = links_by_row.get(row.name, [])
		# Older nodes may only have the original single-document binding.
		legacy = frappe.db.get_value("Project Progress Item", row.name, ["reference_doctype", "reference_name"], as_dict=True)
		if legacy.reference_doctype and legacy.reference_name and not any(
			link.reference_doctype == legacy.reference_doctype and link.reference_name == legacy.reference_name
			for link in row.references
		) and frappe.has_permission(legacy.reference_doctype, "read", doc=legacy.reference_name):
			row.references.append(frappe._dict(reference_doctype=legacy.reference_doctype,
				reference_name=legacy.reference_name, doctype_label=_(legacy.reference_doctype)))
		row.reference_count = len(row.references)
		row.completed_reference_count = len([link for link in row.references if link.status == "Completed"])
	return rows


def scheduled_recalculate_project_progress():
	"""Refresh date-driven expected progress and health without changing Project status."""
	for project in frappe.get_all("Project", filters={"is_active": "Yes"}, pluck="name"):
		if not frappe.db.exists("Project Progress Item", {"parent": project}):
			continue
		try:
			_persist_project_totals(project)
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("项目进度每日重算失败：{0}").format(project))


@frappe.whitelist()
def recalculate_project_progress(project):
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	if doc.get("custom_progress_mode") == "业务完成模式":
		from client_akivision.utils.project_business_progress import refresh_project
		return {"project": project, **(refresh_project(project) or {})}
	for row in doc.get("custom_project_progress_items") or []:
		has_new_references = row.name and frappe.db.exists("Project Progress Reference", {"progress_item": row.name})
		if row.completion_rule == "Document Submitted" and row.reference_doctype and row.reference_name and not has_new_references:
			submitted = frappe.db.get_value(row.reference_doctype, row.reference_name, "docstatus") == 1
			_update_row_status(row, submitted)
	result = _persist_project_totals(project)
	return {"project": project, **result}


@frappe.whitelist()
def start_project(project):
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	if doc.is_new():
		frappe.throw(_("请先保存项目后再开始"))
	if doc.get("custom_project_stage") == "已完成" or doc.status == "Completed":
		frappe.throw(_("已完成项目不能重新开始"))
	if doc.get("custom_project_stage") == "已取消" or doc.status == "Cancelled":
		frappe.throw(_("已取消项目不能开始"))
	rows = list(doc.get("custom_project_progress_items") or [])
	if not rows:
		frappe.throw(_("请先维护流程进度节点，再开始项目"))
	doc.db_set("custom_project_stage", "进行中", update_modified=True)
	first_open_row = next((row for row in rows if row.status != "已完成"), None)
	if first_open_row and first_open_row.status == "待开始" and doc.get("custom_progress_mode") != "业务完成模式":
		_start_progress_row(first_open_row)
	if doc.get("custom_progress_mode") == "业务完成模式":
		from client_akivision.utils.project_business_progress import refresh_project
		return {"project": project, **(refresh_project(project) or {})}
	result = _persist_project_totals(project)
	return {"project": project, "project_stage": "进行中", **result}


@frappe.whitelist()
def start_progress_step(project, row_name=None, milestone_code=None):
	"""Start one progress node and close the immediately previous open node."""
	doc = frappe.get_doc("Project", project)
	if doc.get("custom_progress_mode") == "业务完成模式":
		from client_akivision.utils.project_workbench import act_on_node
		target = next((r for r in doc.custom_project_progress_items if r.name == row_name or (milestone_code and r.milestone_code == milestone_code)), None)
		return act_on_node(target.name if target else "", "start")
	doc.check_permission("write")
	if doc.get("custom_project_stage") in ("已完成", "已取消") or doc.status in ("Completed", "Cancelled"):
		frappe.throw(_("当前项目不能开始新的进度节点"))
	rows = _ordered_progress_rows(doc)
	target = next((row for row in rows if row.name == row_name or (milestone_code and row.milestone_code == milestone_code)), None)
	if not target:
		frappe.throw(_("找不到要开始的进度节点"))
	if target.status == "已完成":
		frappe.throw(_("该进度节点已经完成：{0}").format(target.subject))
	open_rows = [row for row in rows if row.status != "已完成"]
	if open_rows:
		active = open_rows[0]
		allowed_targets = {active.name}
		if active.status in ("待交接", "进行中", "延期"):
			next_row = next((row for row in rows if (row.idx or 0) > (active.idx or 0) and row.status != "已完成"), None)
			if next_row:
				allowed_targets.add(next_row.name)
		if target.name not in allowed_targets:
			frappe.throw(_("请先处理当前节点：{0}").format(active.subject))
	started_on = _start_progress_row(target)
	previous = _finish_previous_open_step(rows, target, started_on)
	if doc.get("custom_project_stage") != "进行中":
		doc.db_set("custom_project_stage", "进行中", update_modified=True)
	result = _persist_project_totals(project)
	return {
		"project": project,
		"started_node": target.subject,
		"completed_previous_node": previous.subject if previous else None,
		**result,
	}


@frappe.whitelist()
def complete_project_from_last_step(project):
	"""Close the last handoff-ready node and complete the project."""
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	if doc.get("custom_progress_mode") == "业务完成模式":
		from client_akivision.utils.project_workbench import close_project
		return close_project(project)
	if doc.get("custom_project_stage") == "已完成" or doc.status == "Completed":
		frappe.throw(_("项目已经完成"))
	if doc.get("custom_project_stage") == "已取消" or doc.status == "Cancelled":
		frappe.throw(_("已取消项目不能完成"))
	rows = _ordered_progress_rows(doc)
	if not rows:
		frappe.throw(_("项目没有配置进度节点"))
	last_row = rows[-1]
	if last_row.status != "待交接":
		frappe.throw(_("最后节点“{0}”当前不是待交接状态，不能完成项目").format(last_row.subject))
	unfinished_previous = [row for row in rows[:-1] if row.status != "已完成"]
	if unfinished_previous:
		frappe.throw(_("前置节点尚未完成：{0}").format("、".join(row.subject for row in unfinished_previous)))
	completed_on = now_datetime()
	last_row.db_set("status", "已完成", update_modified=False)
	last_row.status = "已完成"
	last_row.db_set("actual_completed_on", completed_on, update_modified=False)
	last_row.actual_completed_on = completed_on
	last_row.db_set("completed_by", frappe.session.user, update_modified=False)
	last_row.completed_by = frappe.session.user
	last_row.db_set("last_synced_on", completed_on, update_modified=False)
	last_row.reload()
	_sync_row_duration(last_row, completed_on)
	result = _persist_project_totals(project)
	return {
		"project": project,
		"completed_node": last_row.subject,
		"project_stage": frappe.db.get_value("Project", project, "custom_project_stage"),
		**result,
	}


@frappe.whitelist()
def apply_progress_template(project, template, mode="append", responsible_user=None):
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	template_doc = frappe.get_doc("Project Progress Template", template)
	if not template_doc.enabled:
		frappe.throw(_("进度模板已停用"))
	if mode not in ("append", "replace_unlinked"):
		frappe.throw(_("无效的模板应用方式"))
	if mode == "replace_unlinked":
		kept = [
			row for row in doc.custom_project_progress_items
			if row.reference_name or row.status == "已完成"
			or (row.name and frappe.db.exists("Project Progress Reference", {"progress_item": row.name}))
		]
		doc.set("custom_project_progress_items", [row.as_dict() for row in kept])
	existing = {row.milestone_code for row in doc.custom_project_progress_items}
	start = getdate(doc.expected_start_date or today())
	for source in template_doc.items:
		if source.milestone_code in existing:
			continue
		doc.append("custom_project_progress_items", {
			"progress_category": source.progress_category,
			"milestone_code": source.milestone_code, "subject": source.subject, "weight": source.weight,
			"expected_start_date": add_days(start, source.start_day_offset),
			"expected_end_date": add_days(start, source.end_day_offset),
			"completion_rule": source.completion_rule, "reference_doctype": source.reference_doctype,
			"status": "待开始", "source_template_item": source.name, "remarks": source.remarks,
			"responsible_user": responsible_user,
		})
	doc.custom_progress_template = template_doc.name
	doc.save()
	return {"project": doc.name, "template": template_doc.name, "row_count": len(doc.custom_project_progress_items)}


@frappe.whitelist()
def save_project_progress_as_template(project, template_name):
	frappe.only_for(("System Manager", "Projects Manager"))
	doc = frappe.get_doc("Project", project)
	doc.check_permission("read")
	if frappe.db.exists("Project Progress Template", template_name):
		frappe.throw(_("进度模板 {0} 已存在").format(template_name))
	start = getdate(doc.expected_start_date or today())
	items = []
	for row in doc.custom_project_progress_items:
		items.append({
			"progress_category": row.progress_category,
			"milestone_code": row.milestone_code, "subject": row.subject, "weight": row.weight,
			"start_day_offset": date_diff(getdate(row.expected_start_date or start), start),
			"end_day_offset": date_diff(getdate(row.expected_end_date), start),
			"completion_rule": row.completion_rule, "reference_doctype": row.reference_doctype,
			"remarks": row.remarks,
		})
	template = frappe.get_doc({"doctype": "Project Progress Template", "template_name": template_name, "project_type": doc.project_type, "items": items}).insert()
	doc.db_set("custom_progress_template", template.name)
	return {"name": template.name, "row_count": len(items)}


@frappe.whitelist()
def set_manual_progress_complete(project, row_name, completed, reason=None):
	if frappe.db.get_value("Project", project, "custom_progress_mode") == "业务完成模式":
		if not frappe.utils.cint(completed):
			frappe.throw("新模式请通过工作台的异常退回操作处理")
		from client_akivision.utils.project_workbench import act_on_node
		if frappe.db.get_value("Project Progress Item", row_name, "parent") != project:
			frappe.throw("节点不属于当前项目", frappe.PermissionError)
		return act_on_node(row_name, "complete", reason)
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	row = next((item for item in doc.custom_project_progress_items if item.name == row_name), None)
	if not row or row.completion_rule != "Manual":
		frappe.throw(_("只能手工处理当前项目的手工完成节点"))
	if not completed and not (reason or "").strip():
		frappe.throw(_("撤销节点完成必须填写原因"))
	_update_row_status(row, frappe.utils.cint(completed))
	if reason:
		row.db_set("remarks", reason)
	return {"project": project, **_persist_project_totals(project)}
