frappe.pages["project-progress-timeout"].on_page_load = function (wrapper) {
	new ProjectProgressTimeoutPage(wrapper);
};

class ProjectProgressTimeoutPage {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("项目节点超时表"), single_column: true });
		this.page_no = 1;
		this.page_size = 20;
		this.company = this.page.add_field({ fieldtype: "Link", fieldname: "company", label: __("公司"), options: "Company", default: frappe.defaults.get_user_default("Company"), change: () => this.reset() });
		this.from_date = this.page.add_field({ fieldtype: "Date", fieldname: "from_date", label: __("开始日期"), default: frappe.datetime.year_start(), change: () => this.reset() });
		this.to_date = this.page.add_field({ fieldtype: "Date", fieldname: "to_date", label: __("截止日期"), default: frappe.datetime.get_today(), change: () => this.reset() });
		this.page.set_primary_action(__("刷新"), () => this.load(), "refresh");
		this.page.set_secondary_action(__("导出 Excel"), () => this.export_data(), "download");
		this.$body = $("<div class='project-timeout-page'></div>").appendTo(this.page.main);
		this.render();
		this.load();
	}

	filters() { return { company: this.company.get_value(), from_date: this.from_date.get_value(), to_date: this.to_date.get_value(), project_timeout_page: this.page_no, project_timeout_page_length: this.page_size }; }
	reset() { this.page_no = 1; this.load(); }

	render() {
		this.$body.html(`<style>${this.styles()}</style><div class='pt-filter-hint'>${__("仅显示已完成且实际完成日期晚于计划完成日期的项目节点")}</div><div class='pt-list'><div class='pt-head'><div>${__("项目编号")}</div><div>${__("项目名称")}</div><div>${__("节点名称")}</div><div>${__("计划完成日期")}</div><div>${__("实际完成时间")}</div><div>${__("备注")}</div></div><div class='pt-rows'></div><div class='pt-footer'><div class='pt-sizes'></div><div class='pt-info'></div><div class='pt-nav'><button class='btn btn-default btn-xs pt-prev'>‹</button><button class='btn btn-default btn-xs pt-next'>›</button></div></div></div>`);
		this.$body.on("click", ".pt-prev", () => { if (this.page_no > 1) { this.page_no--; this.load(); } });
		this.$body.on("click", ".pt-next", () => { if (this.page_no < this.pages) { this.page_no++; this.load(); } });
	}

	async load() {
		this.$body.find(".pt-rows").html(`<div class='pt-state'>${__("正在加载...")}</div>`);
		try {
			const response = await frappe.call({ method: "client_akivision.client_akivision.api.operations_kpi.get_project_progress_timeout_data", args: { filters: this.filters() } });
			const result = response.message || {};
			this.total = Number(result.total || 0); this.pages = Math.max(1, Math.ceil(this.total / this.page_size));
			this.render_rows(result.rows || []); this.render_pager();
		} catch (error) { this.$body.find(".pt-rows").html(`<div class='pt-state'>${__("加载失败，请刷新重试")}</div>`); }
	}

	render_rows(rows) {
		const $rows = this.$body.find(".pt-rows").empty();
		if (!rows.length) { $rows.html(`<div class='pt-state'>${__("当前筛选范围内暂无超时节点")}</div>`); return; }
		rows.forEach((row) => { const $item = $("<div class='pt-row'></div>"); const $link = $("<a class='pt-link'></a>").text(row.project || "-").on("click", () => frappe.set_route("Form", "Project", row.project)); $item.append($("<div></div>").append($link)); [row.project_name, row.step_name, this.format_date(row.expected_end_date), this.format_datetime(row.actual_completed_on), row.remarks || "-"].forEach((value) => $item.append($("<div class='ellipsis'></div>").text(value || "-"))); $rows.append($item); });
	}

	render_pager() { const start = this.total ? (this.page_no - 1) * this.page_size + 1 : 0; const end = Math.min(this.page_no * this.page_size, this.total); this.$body.find(".pt-info").text(`${start}-${end} / ${this.total}`); this.$body.find(".pt-prev").prop("disabled", this.page_no <= 1); this.$body.find(".pt-next").prop("disabled", this.page_no >= this.pages); const $sizes = this.$body.find(".pt-sizes").empty(); [20, 100, 500, 2500].forEach((size) => $("<button class='btn btn-xs'></button>").toggleClass("btn-default active", size === this.page_size).toggleClass("btn-link", size !== this.page_size).text(size).on("click", () => { this.page_size = size; this.reset(); }).appendTo($sizes)); }
	format_date(value) { return value ? frappe.datetime.str_to_user(String(value).slice(0, 10)) : "-"; }
	format_datetime(value) { return value ? frappe.datetime.str_to_user(String(value).split(".")[0]) : "-"; }
	export_data() { open_url_post(frappe.request.url, { cmd: "client_akivision.client_akivision.api.operations_kpi_export.export_project_progress_timeouts", filters: this.filters() }); }
	styles() { return `.project-timeout-page{padding:18px 24px}.pt-filter-hint{margin:0 0 12px;color:var(--text-muted);font-size:12px}.pt-list{border:1px solid var(--border-color);background:var(--card-bg)}.pt-head,.pt-row{display:grid;grid-template-columns:1fr 1.4fr 1.4fr 1fr 1.4fr 2fr;gap:0}.pt-head{background:var(--control-bg);color:var(--text-muted);font-weight:600}.pt-head>div,.pt-row>div{padding:11px 14px;border-bottom:1px solid var(--border-color);min-width:0}.pt-row:hover>div{background:var(--highlight-color)}.pt-link{color:var(--text-color);font-weight:500}.pt-link:hover{color:var(--blue-500);text-decoration:underline}.pt-footer{display:flex;align-items:center;gap:16px;padding:8px 14px;color:var(--text-muted)}.pt-sizes,.pt-nav{display:flex;gap:6px}.pt-nav{margin-left:auto}.pt-state{padding:72px 20px;text-align:center;color:var(--text-muted)}@media(max-width:900px){.pt-list{overflow-x:auto}.pt-head,.pt-row{min-width:980px}}`; }
}
