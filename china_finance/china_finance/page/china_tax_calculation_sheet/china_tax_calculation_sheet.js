frappe.pages["china-tax-calculation-sheet"].on_page_load = (wrapper) => {
	wrapper.china_tax_calculation_sheet = new ChinaTaxCalculationSheet(wrapper);
};

class ChinaTaxCalculationSheet {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.tax_types = [
			["VAT", __("增值税计算表")], ["SURCHARGE", __("附加税费")], ["STAMP_DUTY", __("印花税")],
			["UNION_DUES", __("工会经费")], ["CORPORATE_INCOME_TAX", __("企业所得税")],
			["WATER_FUND", __("水利建设基金")], ["DISABILITY_FUND", __("残疾人就业保障金")],
		];
		this.tax_type = "VAT";
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("税费计算表"), single_column: true });
		frappe.breadcrumbs.add("China Finance");
		this.page.add_action_item(__("下载"), () => this.export_csv());
		this.page.add_action_item(__("打印"), () => this.print());
		this.page.add_button(__("刷新"), () => this.refresh(), { icon: "refresh-cw" });
		this.manage_button = this.page.add_button(__("维护本期数据"), () => this.edit_worksheet());
		this.manage_button.hide();
		this.render();
		this.setup_filters();
		this.refresh();
	}

	render() {
		this.wrapper.querySelector(".layout-main-section").innerHTML = `<div class="cf-tax-calculation-sheet"><div class="cf-tax-filter-grid"></div><div class="cf-tax-status"></div><div class="cf-tax-workspace"><nav class="cf-tax-type-nav"></nav><section class="cf-tax-result"><div class="cf-tax-heading"><h4></h4><span class="cf-tax-status-pill"></span></div><div class="cf-tax-warning hidden"></div><div class="cf-tax-table-wrap"><table><thead><tr><th>${__("行次")}</th><th>${__("项目")}</th><th>${__("金额")}</th></tr></thead><tbody></tbody></table></div></section></div></div>`;
		this.root = this.wrapper.querySelector(".cf-tax-calculation-sheet");
		this.filter_grid = this.root.querySelector(".cf-tax-filter-grid");
		this.render_tax_types();
	}

	add_filter(df) {
		const parent = document.createElement("div");
		parent.className = "cf-tax-filter";
		this.filter_grid.appendChild(parent);
		return frappe.ui.form.make_control({ parent, df: { ...df, change: () => this.refresh() }, render_input: true });
	}

	setup_filters() {
		this.filters = {
			company: this.add_filter({ fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1 }),
			period: this.add_filter({ fieldname: "period", label: __("税款所属期"), fieldtype: "Data", placeholder: "YYYY-MM", reqd: 1 }),
		};
		this.filters.company.set_value(frappe.defaults.get_user_default("Company"));
		this.filters.period.set_value(frappe.datetime.now_date().slice(0, 7));
	}

	render_tax_types() {
		this.root.querySelector(".cf-tax-type-nav").innerHTML = this.tax_types.map(([value, label]) => `<button class="btn btn-default cf-tax-type ${value === this.tax_type ? "active" : ""}" data-tax-type="${value}">${label}</button>`).join("");
		this.root.querySelectorAll(".cf-tax-type").forEach((button) => button.onclick = () => { this.tax_type = button.dataset.taxType; this.render_tax_types(); this.refresh(); });
	}

	refresh() {
		if (!this.filters?.company.get_value() || !this.filters.period.get_value()) return;
		const request = this.request_id = (this.request_id || 0) + 1;
		this.latest = null;
		this.manage_button.hide();
		this.root.querySelector(".cf-tax-status").textContent = __("正在计算...");
		frappe.call({ method: "china_finance.services.tax_calculation.get_tax_calculation", args: { company: this.filters.company.get_value(), period: this.filters.period.get_value(), tax_type: this.tax_type }, freeze: true }).then(({ message }) => {
			if (request !== this.request_id) return;
			this.latest = message;
			this.render_result(message);
		}).catch(() => { if (request === this.request_id) this.root.querySelector(".cf-tax-status").textContent = __("计算失败"); });
	}

	render_result(result) {
		this.manage_button.toggle(!!result.can_manage);
		this.root.querySelector(".cf-tax-status").textContent = `${__("所属期")}：${result.period}　${__("计算时间")}：${frappe.datetime.str_to_user(result.calculated_at)}`;
		if (result.worksheet) this.root.querySelector(".cf-tax-status").textContent += `　版本：${result.worksheet.name}　复核人：${result.worksheet.confirmed_by || "--"}　依据：${result.worksheet.basis}`;
		this.root.querySelector(".cf-tax-heading h4").textContent = result.tax_type_label;
		const incomplete = result.status === "Incomplete";
		const pill = this.root.querySelector(".cf-tax-status-pill");
		pill.textContent = this.status_label(result);
		pill.className = `cf-tax-status-pill ${incomplete ? "warning" : "success"}`;
		const warning = this.root.querySelector(".cf-tax-warning");
		warning.textContent = (result.warnings || []).join("　");
		warning.classList.toggle("hidden", !result.warnings?.length);
		this.root.querySelector("tbody").innerHTML = result.rows.map((row) => `<tr class="${row.emphasis ? "cf-tax-emphasis" : ""}"><td>${row.line_no}</td><td>${frappe.utils.escape_html(row.label)}<div class="text-muted small">${frappe.utils.escape_html(this.source_label(row))}</div></td><td class="text-right">${row.amount === null ? "--" : this.format_amount(row.amount, result.currency, row)}</td></tr>`).join("");
		this.root.querySelectorAll(".cf-tax-source").forEach((button) => button.onclick = () => this.open_source(button.dataset.source));
	}

	format_amount(amount, currency, source) {
		const value = source.unit === "percent" ? `${frappe.format(amount, { fieldtype: "Float" })}%` : frappe.format(amount, { fieldtype: source.unit === "number" ? "Float" : "Currency", options: currency });
		return source.source ? `<button class="btn btn-link btn-sm cf-tax-source" data-source="${source.source}">${value}</button>` : value;
	}

	status_label(result) { return result.status === "Confirmed" ? __("已复核底稿") : result.status === "Calculated" ? __("待复核底稿") : __("需补充数据"); }

	source_label(row) {
		if (row.source_state === "manual") return __("财务人工维护（替代本行来源）");
		if (row.source_state === "calculated") return __("常规增值税计算");
		if (row.source_count !== undefined) return `${__("来源记录")}：${row.source_count}；${row.source_count ? __("自动汇总") : __("尚无来源，待核实")}`;
		return __("未维护，待补充依据");
	}

	open_source(source) {
		if (!this.latest) return;
		const row = this.latest.rows.find((item) => item.source === source);
		if (!row) return;
		if (source === "China VAT Ledger") {
			frappe.set_route("query-report", source, row.source_filters);
			return;
		}
		if (source === "China Input Tax Deduction Batch") frappe.set_route("List", source, row.source_filters);
	}

	edit_worksheet() {
		const result = this.latest;
		if (!result?.can_manage) return;
		const sheet = result.worksheet || {};
		const fields = [{ fieldtype: "HTML", options: `<p>${frappe.utils.escape_html(result.company)} / ${frappe.utils.escape_html(result.period)} / ${frappe.utils.escape_html(result.tax_type_label)}</p><p>留空使用自动来源；填写 0 表示人工核实为零。人工值替代本行，不与自动值相加。所有人工值须在依据中注明政策及凭据。非增值税项目当前为人工底稿，不自动套用税率。</p>` }];
		if (result.tax_type === "VAT") fields.push({ fieldname: "ordinary_vat", fieldtype: "Check", label: __("确认适用常规一般纳税人分支（无减免、无预缴、无特殊计税）"), default: sheet.ordinary_vat ? 1 : 0 });
		result.rows.forEach((row) => fields.push({ fieldname: row.item_code, fieldtype: "Data", label: row.label,
			default: sheet.values?.[row.item_code] ?? "", description: `${this.source_label(row)}；当前值：${row.amount ?? "--"}` }));
		fields.push({ fieldname: "basis", fieldtype: "Small Text", label: __("政策、凭据依据及维护/修订原因"), reqd: 1, default: sheet.basis || "" });
		const dialog = new frappe.ui.Dialog({ title: __("维护本期税费底稿"), size: "large", fields,
			primary_action_label: __("保存草稿"), primary_action: () => save(false),
			secondary_action_label: __("复核并确认"), secondary_action: () => save(true) });
		const save = (confirm) => {
			const data = dialog.get_values();
			if (!data) return;
			const values = {};
			for (const row of result.rows) {
				const value = data[row.item_code];
				if (value !== undefined && value !== null && String(value).trim() !== "") values[row.item_code] = String(value).trim();
			}
			frappe.call({ method: "china_finance.services.tax_worksheet.save_worksheet", type: "POST", freeze: true,
				args: { company: result.company, period: result.period, tax_type: result.tax_type, values,
					basis: data.basis, previous_version: sheet.name || null, source_fingerprint: result.source_fingerprint, ordinary_vat: data.ordinary_vat || 0, confirm: confirm ? 1 : 0 }
			}).then(() => { dialog.hide(); this.refresh(); frappe.show_alert(__("底稿已保存")); });
		};
		dialog.show();
	}

	export_csv() {
		if (!this.latest) return;
		const rows = [[__("公司"), this.latest.company], [__("税种"), this.latest.tax_type_label], [__("所属期"), this.latest.period], [__("状态"), this.status_label(this.latest)],
			[__("版本"), this.latest.worksheet?.name || ""], [__("复核人"), this.latest.worksheet?.confirmed_by || ""],
			[__("依据"), this.latest.worksheet?.basis || ""], [__("提示"), (this.latest.warnings || []).join("；")], [__("行次"), __("项目"), __("数值"), __("单位"), __("来源")],
			...this.latest.rows.map((row) => [row.line_no, row.label, row.amount ?? "", row.unit === "percent" ? "%" : row.unit === "number" ? "人" : this.latest.currency, this.source_label(row)])];
		const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
		const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" })); link.download = `${this.latest.tax_type_label}-${this.latest.period}.csv`; link.click(); URL.revokeObjectURL(link.href);
	}

	print() { if (this.latest) window.print(); }
}
