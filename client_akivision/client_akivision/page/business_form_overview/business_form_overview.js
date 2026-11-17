frappe.pages["business-form-overview"].on_page_load = function (wrapper) {
	new BusinessFormOverview(wrapper);
};

class BusinessFormOverview {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("业务表单总表"), single_column: true });
		this.page_no = 1;
		this.page_size = 20;
		this.forms = [];
		this.loading = false;
		this.page.set_primary_action(__("刷新"), () => this.load(), "refresh");
		this.page.set_secondary_action(__("导出"), () => this.export_data(), "download");
		this.$body = $("<div class='business-form-overview-page'></div>").appendTo(this.page.main);
		this.render();
		this.bind_events();
		this.load();
	}

	render() {
		this.$body.html(`
			<style>${this.styles()}</style>
			<div class="bfo-filter-bar">
				<label class="bfo-filter bfo-search"><span>${__("单号/关键词")}</span><input data-filter="text" type="search"></label>
				<label class="bfo-filter"><span>${__("业务分类")}</span><select data-filter="category"><option value="">${__("全部分类")}</option></select></label>
				<label class="bfo-filter"><span>${__("具体表单")}</span><select data-filter="doctype"><option value="">${__("全部表单")}</option></select></label>
				<label class="bfo-filter"><span>${__("状态")}</span><select data-filter="status"><option value="">${__("全部状态")}</option></select></label>
				<label class="bfo-filter"><span>${__("查看范围")}</span><select data-filter="view"><option value="all">${__("全部可见")}</option><option value="mine">${__("我提交的")}</option><option value="assigned">${__("我负责的")}</option></select></label>
				<button class="btn btn-default btn-sm bfo-clear">${frappe.utils.icon("filter", "sm")} ${__("清除筛选")}</button>
			</div>
			<div class="bfo-list-shell">
				<div class="bfo-list-scroll">
					<div class="bfo-grid bfo-head">
						<div><input class="bfo-check-all" type="checkbox" aria-label="${__("全选")}"></div><div>${__("单据编号")}</div><div>${__("具体表单")}</div><div>${__("分类")}</div><div>${__("状态")}</div><div>${__("提交时间")}</div><div>${__("持续时间")}</div><div>${__("提交人")}</div><div>${__("负责人")}</div><div>${__("最后更新时间")}</div>
					</div>
					<div class="bfo-results"></div>
				</div>
				<div class="bfo-footer">
					<div class="bfo-page-sizes"><span>${__("每页")}</span>${[20, 50, 100].map((size) => `<button class="btn btn-xs ${size === this.page_size ? "btn-default active" : "btn-link"}" data-size="${size}">${size}</button>`).join("")}</div>
					<div class="bfo-page-info"></div>
					<div class="bfo-pager"><button class="btn btn-default btn-sm bfo-prev" title="${__("上一页")}">${frappe.utils.icon("left", "sm")}</button><button class="btn btn-default btn-sm bfo-next" title="${__("下一页")}">${frappe.utils.icon("right", "sm")}</button></div>
				</div>
			</div>`);
	}

	bind_events() {
		let search_timer;
		this.$body.on("change", "select[data-filter]", (event) => {
			if (event.currentTarget.dataset.filter === "category") this.update_form_options();
			this.reset_and_load();
		});
		this.$body.on("input", "input[data-filter='text']", () => {
			clearTimeout(search_timer);
			search_timer = setTimeout(() => this.reset_and_load(), 350);
		});
		this.$body.on("click", ".bfo-clear", () => {
			this.$body.find("[data-filter]").val("");
			this.$body.find("[data-filter='view']").val("all");
			this.update_form_options();
			this.reset_and_load();
		});
		this.$body.on("click", "[data-size]", (event) => {
			this.page_size = Number(event.currentTarget.dataset.size);
			this.$body.find("[data-size]").removeClass("btn-default active").addClass("btn-link");
			$(event.currentTarget).removeClass("btn-link").addClass("btn-default active");
			this.reset_and_load();
		});
		this.$body.on("click", ".bfo-prev", () => { if (this.page_no > 1) { this.page_no--; this.load(); } });
		this.$body.on("click", ".bfo-next", () => { if (this.has_more) { this.page_no++; this.load(); } });
		this.$body.on("change", ".bfo-check-all", (event) => this.$body.find(".bfo-row-check").prop("checked", event.currentTarget.checked));
	}

	reset_and_load() { this.page_no = 1; this.load(); }

	filters() {
		const values = {};
		this.$body.find("[data-filter]").each((_, element) => { values[element.dataset.filter] = $(element).val(); });
		return values;
	}

	async load() {
		if (this.loading) return;
		this.loading = true;
		this.$body.find(".bfo-results").html(`<div class="bfo-state">${frappe.utils.icon("spinner", "md")}<span>${__("正在加载...")}</span></div>`);
		try {
			const response = await frappe.call({ method: "client_akivision.client_akivision.api.business_form_overview.get_business_form_overview", args: { filters: this.filters(), page: this.page_no, page_size: this.page_size } });
			const data = response.message || {};
			this.has_more = Boolean(data.has_more);
			this.total = Number(data.total || 0);
			this.forms = data.forms || [];
			this.populate_filters(data);
			this.render_rows(data.rows || []);
			this.render_pager();
		} catch (error) {
			this.$body.find(".bfo-results").html(`<div class="bfo-state bfo-error">${frappe.utils.icon("error", "md")}<span>${__("加载失败，请刷新重试")}</span></div>`);
		} finally {
			this.loading = false;
		}
	}

	populate_filters(data) {
		const category = this.$body.find("[data-filter='category']");
		if (!category.data("loaded")) {
			(data.categories || []).forEach((value) => category.append($("<option>").val(value).text(value)));
			(data.statuses || []).forEach((item) => this.$body.find("[data-filter='status']").append($("<option>").val(item.value).text(item.label)));
			category.data("loaded", true);
		}
		this.update_form_options();
	}

	update_form_options() {
		const field = this.$body.find("[data-filter='doctype']");
		const selected = field.val();
		const category = this.$body.find("[data-filter='category']").val();
		field.empty().append($("<option>").val("").text(__("全部表单")));
		this.forms.filter((item) => !category || item.category === category).forEach((item) => field.append($("<option>").val(item.doctype).text(item.label)));
		if ([...field[0].options].some((option) => option.value === selected)) field.val(selected);
	}

	render_rows(rows) {
		const result = this.$body.find(".bfo-results").empty();
		this.$body.find(".bfo-check-all").prop("checked", false);
		if (!rows.length) {
			result.html(`<div class="bfo-state">${frappe.utils.icon("list", "md")}<span>${__("没有符合条件的业务单据")}</span></div>`);
			return;
		}
		rows.forEach((row) => {
			const status = this.status_display(row.business_status);
			const link = $("<a class='bfo-document ellipsis'></a>").text(row.name || "-").on("click", () => frappe.set_route("Form", row.doctype, row.name));
			const grid = $("<div class='bfo-grid bfo-row'></div>");
			grid.append($("<div></div>").append($("<input class='bfo-row-check' type='checkbox'>").attr("aria-label", row.name)));
			grid.append($("<div></div>").append(link));
			[row.form_label, row.category].forEach((value) => grid.append($("<div class='ellipsis'></div>").text(value || "-")));
			grid.append($("<div></div>").append($("<span class='bfo-status'></span>").addClass(status.tone).text(status.label)));
			grid.append($("<div class='ellipsis'></div>").text(this.format_date(row.submitted_at)));
			grid.append($("<div class='ellipsis'></div>").text(row.duration_display || "-"));
			grid.append($("<div class='ellipsis'></div>").text(row.owner || "-"));
			grid.append($("<div class='ellipsis'></div>").text(row.assignee || "-"));
			grid.append($("<div class='ellipsis'></div>").text(this.format_datetime(row.modified)));
			result.append(grid);
		});
	}

	render_pager() {
		const start = this.total ? (this.page_no - 1) * this.page_size + 1 : 0;
		const end = Math.min(this.page_no * this.page_size, this.total);
		this.$body.find(".bfo-page-info").text(`${start}-${end} / ${this.total}`);
		this.$body.find(".bfo-prev").prop("disabled", this.page_no <= 1);
		this.$body.find(".bfo-next").prop("disabled", !this.has_more);
	}

	status_display(value) {
		const key = String(value ?? "").toLowerCase();
		const labels = {
			"to deliver and bill": __("待交付和开票"),
			"to deliver": __("待交付"),
			"to bill": __("待开票"),
			"not started": __("未开始"),
			"in process": __("进行中"),
			"material transferred for manufacture": __("物料已转移待生产"),
			"on hold": __("暂缓"),
			"draft": __("草稿"),
			"open": __("待处理"),
			"pending": __("待处理"),
		};
		if (["1", "submitted", "已提交"].includes(key)) return { label: __("已提交"), tone: "blue" };
		if (["2", "cancelled", "canceled", "已取消"].includes(key)) return { label: __("已取消"), tone: "gray" };
		if (/complete|closed|finish|已完成/.test(key)) return { label: __("已完成"), tone: "green" };
		if (/reject|驳回/.test(key)) return { label: __("已驳回"), tone: "red" };
		if (labels[key] || /pending|open|process|to |待|审批/.test(key)) return { label: labels[key] || value || __("待处理"), tone: "orange" };
		return { label: value || "-", tone: "gray" };
	}

	format_date(value) { return value ? frappe.datetime.str_to_user(String(value).slice(0, 10)) : "-"; }
	format_datetime(value) { return value ? frappe.datetime.str_to_user(String(value).split(".")[0]) : "-"; }

	export_data() {
		open_url_post(frappe.request.url, { cmd: "client_akivision.client_akivision.api.business_form_overview.export_business_form_overview", filters: this.filters() });
	}

	styles() {
		return `
		.business-form-overview-page{min-width:0;color:var(--text-color)}
		.bfo-filter-bar{display:grid;grid-template-columns:minmax(180px,1.3fr) repeat(4,minmax(130px,1fr)) auto;gap:10px;padding:12px 0 14px;align-items:end}
		.bfo-filter{display:flex;min-width:0;height:36px;align-items:center;gap:8px;padding:0 11px;border-radius:7px;background:var(--control-bg);color:var(--text-muted);font-size:var(--text-sm)}
		.bfo-filter span{white-space:nowrap}.bfo-filter input,.bfo-filter select{width:100%;min-width:0;border:0;outline:0;background:transparent;color:var(--text-color)}
		.bfo-clear{height:36px;white-space:nowrap;display:flex;align-items:center;gap:5px}
		.bfo-list-shell{border-top:1px solid var(--border-color)}.bfo-list-scroll{overflow-x:auto}
		.bfo-grid{display:grid;grid-template-columns:36px minmax(170px,1.35fr) minmax(110px,.8fr) minmax(72px,.5fr) minmax(100px,.7fr) minmax(110px,.8fr) minmax(120px,.9fr) minmax(120px,.9fr) minmax(100px,.75fr) minmax(155px,1.1fr);min-width:1280px;align-items:center}
		.bfo-grid>div{min-width:0;padding:0 10px}.bfo-head{height:38px;background:var(--subtle-fg);color:var(--text-muted);font-size:var(--text-sm);font-weight:500;border-radius:7px}
		.bfo-row{min-height:46px;border-bottom:1px solid var(--border-color);font-size:var(--text-sm)}.bfo-row:hover{background:var(--highlight-color)}
		.bfo-document{display:block;color:var(--text-color);font-weight:500;cursor:pointer}.bfo-document:hover{color:var(--primary);text-decoration:underline}
		.bfo-status{display:inline-flex;align-items:center;min-height:22px;padding:2px 9px;border-radius:11px;font-size:var(--text-xs);white-space:nowrap}.bfo-status.blue{color:var(--blue-700);background:var(--blue-100)}.bfo-status.green{color:var(--green-700);background:var(--green-100)}.bfo-status.orange{color:var(--orange-700);background:var(--orange-100)}.bfo-status.red{color:var(--red-700);background:var(--red-100)}.bfo-status.gray{color:var(--gray-700);background:var(--gray-100)}
		.bfo-state{height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;color:var(--text-muted)}.bfo-error{color:var(--red-600)}
		.bfo-footer{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;min-height:52px;border-bottom:1px solid var(--border-color);color:var(--text-muted);font-size:var(--text-sm)}
		.bfo-page-sizes,.bfo-pager{display:flex;align-items:center;gap:5px}.bfo-pager{justify-self:end}.bfo-page-info{justify-self:center}.bfo-page-sizes .btn{min-width:32px}.bfo-pager .btn{width:32px;height:30px;padding:4px}
		@media(max-width:1100px){.bfo-filter-bar{grid-template-columns:repeat(3,minmax(140px,1fr))}.bfo-clear{justify-self:start}}
		@media(max-width:650px){.bfo-filter-bar{grid-template-columns:1fr 1fr}.bfo-search{grid-column:1/-1}.bfo-footer{grid-template-columns:1fr auto}.bfo-page-info{display:none}}
		`;
	}
}
