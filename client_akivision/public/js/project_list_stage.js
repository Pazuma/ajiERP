(function () {
	function get_project_stage_indicator(stage) {
		const color = { 待处理: "orange", 进行中: "blue", 已完成: "green", 已取消: "red", 暂停: "gray" }[stage] || "gray";
		return [__(stage), color, `custom_project_stage,=,${stage}`];
	}

	function enhance_project_list() {
		if (!document.getElementById("client-project-progress-total-style")) $("<style id='client-project-progress-total-style'>.project-progress-total{display:flex;align-items:center;gap:6px;min-width:150px}.project-progress-total:before{content:'';position:absolute;width:130px;height:8px;background:var(--gray-100);border-radius:8px}.project-progress-total span{position:relative;display:block;height:8px;background:var(--green-500);border-radius:8px;z-index:1}.project-progress-total b{margin-left:136px;font-size:var(--text-xs);font-weight:500;white-space:nowrap}</style>").appendTo(document.head);
		const route = frappe.get_route ? frappe.get_route() : [];
		if (!Array.isArray(route) || route[0] !== "List" || route[1] !== "Project") return;

		const settings = frappe.listview_settings.Project = frappe.listview_settings.Project || {};
		settings.add_fields = Array.from(new Set([...(settings.add_fields || []), "percent_complete", "custom_project_stage", "custom_current_progress_step", "custom_current_progress_duration", "custom_expected_progress", "custom_actual_process_progress", "custom_progress_health"]));

		if (!settings._client_akivision_project_stage_indicator) {
			const native_get_indicator = settings.get_indicator;
			settings._client_akivision_project_stage_indicator = true;
			settings.formatters = settings.formatters || {};
			const native_step_formatter = settings.formatters.custom_current_progress_step;
			settings.formatters.custom_current_progress_step = function (value, field, doc) {
				const formatted = native_step_formatter ? native_step_formatter(value, field, doc) : (value || "");
				return doc.custom_current_progress_duration && doc.custom_current_progress_duration !== "-"
					? `${formatted}（${frappe.utils.escape_html(doc.custom_current_progress_duration)}）`
					: formatted;
			};
			settings.formatters.custom_actual_process_progress = function (value) {
				const percent = Math.max(0, Math.min(100, Number(value || 0)));
				return `<div class="project-progress-total" title="${percent.toFixed(2)}%"><span style="width:${percent}%"></span><b>${percent.toFixed(2)}%</b></div>`;
			};
			settings.get_indicator = function (doc) {
				if (doc.custom_project_stage) return get_project_stage_indicator(doc.custom_project_stage);
				return native_get_indicator ? native_get_indicator(doc) : [__(doc.status), frappe.utils.guess_colour(doc.status), `status,=,${doc.status}`];
			};
		}

		const listview = window.cur_list;
		if (!listview || listview.doctype !== "Project") return;
		listview.fields = listview.fields || [];
		[
			["custom_project_stage", "Project"],
			["percent_complete", "Project"],
			["custom_current_progress_step", "Project"],
			["custom_current_progress_duration", "Project"],
			["custom_expected_progress", "Project"],
			["custom_actual_process_progress", "Project"],
			["custom_progress_health", "Project"],
		].forEach((field_to_add) => {
			const fieldname = field_to_add[0];
			const has_field = listview.fields.some((field) => Array.isArray(field) ? field[0] === fieldname : field === fieldname);
			if (!has_field) listview.fields.push(fieldname);
		});
		if (!listview._client_akivision_project_stage_refreshed) {
			const names = (listview.data || []).map((row) => row.name).filter(Boolean).slice(0, 100);
			if (!names.length) return;
			listview._client_akivision_project_stage_refreshed = true;
			setTimeout(() => {
				Promise.all(names.map((project) => frappe.call({
					method: "client_akivision.utils.project_progress.recalculate_project_progress",
					args: { project },
					freeze: false,
				}).catch(() => null))).finally(() => listview.refresh());
			}, 0);
		}
	}

	frappe.after_ajax(enhance_project_list);
	$(document).on("page-change", enhance_project_list);
	setInterval(enhance_project_list, 500);
})();
