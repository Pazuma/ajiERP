frappe.pages["project-workbench"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "项目工作台", single_column: true });
	const api = "client_akivision.utils.project_workbench.";
	const esc = frappe.utils.escape_html;
	const buckets = ["待处理", "进行中", "已逾期", "业务异常", "未来节点", "已完成", "已暂停"];
	let start = 0;
	let owner;
	let total = 0;
	let isAdmin = false;
	let loading = false;
	const status = page.add_field({
		fieldname: "status", label: "状态", fieldtype: "Select", options: buckets.join("\n"),
		change: () => { start = 0; load(); },
	});
	const body = $('<main class="project-workbench-page"></main>').appendTo(page.body);
	page.set_primary_action("刷新", () => load(), "refresh");
	status.set_value("待处理");

	function chooseStatus(value) {
		if (status.get_value() !== value) status.set_value(value);
	}

	function addOwnerFilter() {
		if (owner || !isAdmin) return;
		owner = page.add_field({
			fieldname: "responsible_user", label: "负责人", fieldtype: "Link", options: "User",
			change: () => { start = 0; load(); },
		});
	}

	function renderSummary(data) {
		const summary = $('<section class="project-workbench-summary" aria-label="待办统计"></section>').appendTo(body);
		buckets.forEach((bucket) => {
			const count = data.counts[bucket] || 0;
			$('<button type="button" class="project-workbench-stat"></button>')
				.toggleClass("is-active", status.get_value() === bucket)
				.toggleClass("is-alert", ["已逾期", "业务异常"].includes(bucket) && count > 0)
				.attr("aria-pressed", status.get_value() === bucket)
				.append($('<span class="project-workbench-stat-label"></span>').text(bucket))
				.append($('<strong></strong>').text(count))
				.on("click", () => chooseStatus(bucket)).appendTo(summary);
		});
	}

	function renderFilterBar() {
		const bar = $('<div class="project-workbench-filter-bar"></div>').appendTo(body);
		$('<span class="project-workbench-filter-note"></span>')
			.text(isAdmin ? "按负责人查看项目节点" : "仅显示分配给我的项目节点").appendTo(bar);
		if (isAdmin && owner?.get_value()) {
			$('<button type="button" class="btn btn-default btn-sm">重置筛选</button>')
				.on("click", () => { owner.set_value(""); start = 0; load(); }).appendTo(bar);
		}
	}

	function openDetails(row) {
		frappe.call({ method: api + "get_node_details", args: { node: row.name } }).then((response) => {
			const detail = response.message;
			const dialog = new frappe.ui.Dialog({ title: row.subject, fields: [{ fieldtype: "HTML", fieldname: "content" }] });
			const entries = detail.details.map((item) => {
				const lines = [...(item.lines || []), ...(item.quality || [])].map((line) => `<p>${esc(line)}</p>`).join("");
				const link = item.doctype && item.name ? `<button class="btn btn-default btn-sm open-doc" data-dt="${esc(item.doctype)}" data-name="${esc(item.name)}">打开单据</button>` : "";
				return `<article class="project-workbench-detail"><strong>${esc(item.name || "")}</strong><p>${esc(item.summary || "")}</p>${lines}${link}</article>`;
			}).join("");
			dialog.fields_dict.content.$wrapper.html(`${detail.exception ? `<p class="text-danger">${esc(detail.exception)}</p>` : ""}${entries || '<p class="text-muted">暂无关联业务明细</p>'}`);
			dialog.fields_dict.content.$wrapper.find(".open-doc").on("click", function () {
				frappe.set_route("Form", $(this).attr("data-dt"), $(this).attr("data-name"));
				dialog.hide();
			});
			dialog.show();
		});
	}

	function completeNode(row) {
		frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: "完成说明（仅手工事项或非履约型单据）", reqd: 1 }, async (values) => {
			await frappe.call({ method: api + "act_on_node", args: { node: row.name, action: "complete", reason: values.reason }, freeze: true });
			load();
		}, "确认完成");
	}

	function openProcess(row) {
		const dialog = new frappe.ui.Dialog({ title: row.subject, fields: [{ fieldtype: "HTML", fieldname: "summary" }] });
		dialog.fields_dict.summary.$wrapper.html(`<div class="project-workbench-process-summary"><div>项目：${esc(row.project_name || row.parent)}</div><div>当前状态：${esc(row.bucket)}</div><div>业务进展：${esc(row.business_summary || "等待首次同步")}</div></div>`);
		dialog.set_secondary_action_label("同步业务进展");
		dialog.set_secondary_action(async () => {
			await frappe.call({ method: api + "refresh_node", args: { node: row.name }, freeze: true });
			dialog.hide();
			load();
		});
		if (row.bucket === "待处理") {
			dialog.set_primary_action("开始节点", async () => {
				await frappe.call({ method: api + "act_on_node", args: { node: row.name, action: "start" }, freeze: true });
				dialog.hide();
				load();
			});
		} else {
			dialog.set_primary_action("手工确认完成", () => { dialog.hide(); completeNode(row); });
		}
		dialog.show();
	}

	function renderRows(rows) {
		const section = $('<section class="project-workbench-list"></section>').appendTo(body);
		$('<div class="project-workbench-list-heading"><h4>待办节点</h4><span></span></div>').find("span").text(`共 ${total} 条`).end().appendTo(section);
		if (!rows.length) {
			const empty = $('<div class="project-workbench-empty"></div>').appendTo(section);
			$('<strong></strong>').text("暂无待办节点").appendTo(empty);
			$('<span></span>').text(status.get_value() === "待处理" ? "当前没有需要处理的项目节点" : "暂无符合当前筛选条件的项目节点").appendTo(empty);
			if (status.get_value() === "待处理") $('<button type="button" class="btn btn-default btn-sm">查看未来节点</button>').on("click", () => chooseStatus("未来节点")).appendTo(empty);
			return;
		}
		const table = $('<div class="table-responsive"><table class="table project-workbench-table"><thead><tr><th>项目 / 节点</th><th>负责人</th><th>计划完成</th><th>业务进展</th><th>操作</th></tr></thead><tbody></tbody></table></div>').appendTo(section).find("tbody");
		rows.forEach((row) => {
			const tr = $('<tr></tr>').appendTo(table);
			$('<td class="project-workbench-node"></td>')
				.append($('<a href="#"></a>').text(row.project_name || row.parent).on("click", (event) => { event.preventDefault(); frappe.set_route("Form", "Project", row.parent); }))
				.append($('<strong></strong>').text(row.subject))
				.append($('<span class="project-workbench-status"></span>').toggleClass("is-overdue", row.overdue).text(row.overdue ? "已逾期" : row.bucket)).appendTo(tr);
			$('<td></td>').text(row.responsible_user || "未分配").appendTo(tr);
			$('<td></td>').text(row.expected_end_date || "未设置").appendTo(tr);
			$('<td class="project-workbench-progress"></td>').text((row.business_summary || "等待首次同步") + (row.business_exception ? `；异常：${row.business_exception}` : "")).appendTo(tr);
			const actions = $('<td class="project-workbench-actions"></td>').appendTo(tr);
			$('<button type="button" class="btn btn-default btn-sm">查看</button>').on("click", () => openDetails(row)).appendTo(actions);
			if (["待处理", "进行中"].includes(row.bucket)) $('<button type="button" class="btn btn-primary btn-sm">处理</button>').on("click", () => openProcess(row)).appendTo(actions);
		});
		const pager = $('<div class="project-workbench-pager"></div>').appendTo(section);
		$('<button class="btn btn-default btn-sm">上一页</button>').prop("disabled", start === 0).on("click", () => { start = Math.max(0, start - 30); load(); }).appendTo(pager);
		$('<button class="btn btn-default btn-sm">下一页</button>').prop("disabled", start + 30 >= total).on("click", () => { start += 30; load(); }).appendTo(pager);
	}

	async function load() {
		if (loading) return;
		loading = true;
		try {
			const response = await frappe.call({ method: api + "get_nodes", args: { start, status: status.get_value(), responsible_user: owner?.get_value(), page_length: 30 } });
			const data = response.message;
			isAdmin = data.is_admin;
			addOwnerFilter();
			total = data.total;
			body.empty();
			renderSummary(data);
			renderFilterBar();
			renderRows(data.rows);
		} finally {
			loading = false;
		}
	}
	load();
};
