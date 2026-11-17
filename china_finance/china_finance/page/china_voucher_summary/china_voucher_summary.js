frappe.pages["china-voucher-summary"].on_page_load = (wrapper) => {
	wrapper.china_voucher_summary = new ChinaVoucherSummary(wrapper);
};

class ChinaVoucherSummary {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("凭证汇总表"), single_column: true });
		frappe.breadcrumbs.add("China Finance");
		this.page.add_action_item(__("下载"), () => this.export_csv());
		this.page.add_action_item(__("导出所选凭证"), () => this.export_selected());
		this.page.add_action_item(__("打印"), () => this.print());
		this.page.add_button(__("刷新"), () => this.refresh(), { icon: "refresh-cw" });
		this.render(); this.setup_filters(); this.refresh();
	}

	render() {
		this.wrapper.querySelector(".layout-main-section").innerHTML = `<div class="cf-voucher-summary"><div class="cf-summary-filter-grid"></div><button class="cf-more-filters btn btn-link btn-sm" type="button" aria-expanded="false">${__("更多筛选")} <span class="cf-more-filters-icon">+</span></button><div class="cf-summary-advanced-grid" hidden></div><div class="cf-summary-metrics"><div class="cf-summary-primary-metrics"><span><b class="cf-voucher-count">0</b> ${__("张凭证")}</span><span><b class="cf-attachment-count">0</b> ${__("张附件")}</span><span>${__("借方合计")} <b class="cf-debit-total">0.00</b></span><span>${__("贷方合计")} <b class="cf-credit-total">0.00</b></span></div><div class="cf-summary-meta"><span class="cf-applied-period"></span><span class="cf-status-message"></span><span class="cf-runtime"></span></div></div><div class="cf-selection-bar" hidden><span class="cf-selected-count"></span><button class="btn btn-default btn-sm cf-export-selected">${__("导出所选凭证")}</button><button class="btn btn-link btn-sm cf-clear-selection">${__("取消选择")}</button></div><div class="cf-summary-results"><table class="cf-summary-list"><thead><tr><th class="cf-select-column"><input type="checkbox" class="cf-select-all" aria-label="${__("选择全部凭证")}"></th><th>${__("凭证编号")}</th><th>${__("来源单据")}</th><th>${__("日期")}</th><th>${__("摘要")}</th><th>${__("借方金额")}</th><th>${__("贷方金额")}</th></tr></thead><tbody></tbody></table><div class="cf-summary-empty hidden">${frappe.utils.icon("table", "lg")}<span>${__("当前期间暂无凭证汇总数据")}</span><button class="btn btn-default btn-sm cf-clear-search hidden">${__("清除关键词")}</button></div></div></div>`;
		this.root = this.wrapper.querySelector(".cf-voucher-summary");
		this.filter_grid = this.root.querySelector(".cf-summary-filter-grid");
		this.advanced_filter_grid = this.root.querySelector(".cf-summary-advanced-grid");
		this.root.querySelector(".cf-more-filters").onclick = (event) => {
			const button = event.currentTarget;
			const expanded = button.getAttribute("aria-expanded") === "true";
			button.setAttribute("aria-expanded", String(!expanded));
			this.advanced_filter_grid.hidden = expanded;
			button.querySelector(".cf-more-filters-icon").textContent = expanded ? "+" : "−";
		};
		this.selected = new Set();
		this.root.querySelector(".cf-select-all").onchange = (event) => {
			this.selected = event.target.checked ? new Set((this.latest?.voucher_rows || []).map((row) => row.name)) : new Set();
			this.render_selection();
		};
		this.root.querySelector(".cf-summary-list tbody").onchange = (event) => {
			if (!event.target.matches(".cf-select-row")) return;
			if (event.target.checked) this.selected.add(event.target.value);
			else this.selected.delete(event.target.value);
			this.render_selection();
		};
		this.root.querySelector(".cf-export-selected").onclick = () => this.export_selected();
		this.root.querySelector(".cf-clear-selection").onclick = () => { this.selected.clear(); this.render_selection(); };
	}

	add_filter(df) {
		const advanced = ["search_text", "show_account_category_subtotal"].includes(df.fieldname);
		const parent = document.createElement("div"); parent.className = "cf-summary-filter"; (advanced ? this.advanced_filter_grid : this.filter_grid).appendChild(parent);
		const control = frappe.ui.form.make_control({ parent, df: { ...df, change: () => this.on_filter_change(df.fieldname) }, render_input: true });
		control.grid_parent = parent;
		return control;
	}

	setup_filters() {
		const month = frappe.datetime.now_date().slice(0, 7);
		this.filters = {
			company: this.add_filter({ fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1 }),
			period_mode: this.add_filter({ fieldname: "period_mode", label: __("期间模式"), fieldtype: "Select", options: `${__("按月")}\n${__("自定义日期")}` }),
			from_month: this.add_filter({ fieldname: "from_month", label: __("起始月份"), fieldtype: "Data", placeholder: "YYYY-MM" }),
			to_month: this.add_filter({ fieldname: "to_month", label: __("截止月份"), fieldtype: "Data", placeholder: "YYYY-MM" }),
			from_date: this.add_filter({ fieldname: "from_date", label: __("起始日期"), fieldtype: "Date" }),
			to_date: this.add_filter({ fieldname: "to_date", label: __("截止日期"), fieldtype: "Date" }),
			search_text: this.add_filter({ fieldname: "search_text", label: __("关键词"), fieldtype: "Data", placeholder: __("凭证号/摘要/科目/金额") }),
			show_account_category_subtotal: this.add_filter({ fieldname: "show_account_category_subtotal", label: __("显示科目分类小计"), fieldtype: "Check" }),
		};
		this.filters.company.set_value(frappe.defaults.get_user_default("Company")); this.filters.period_mode.set_value(__("按月")); this.filters.from_month.set_value(month); this.filters.to_month.set_value(month); this.toggle_period_filters();
		this.filters.search_text.$input.on("keydown", (event) => { if (event.key === "Enter") this.refresh(); });
		this.root.querySelector(".cf-clear-search").onclick = () => { this.filters.search_text.set_value(""); this.refresh(); };
	}

	on_filter_change(name) { if (name === "period_mode") this.toggle_period_filters(); if (name === "show_account_category_subtotal") this.refresh(); }
	toggle_period_filters() { const custom = this.filters.period_mode.get_value() === __("自定义日期"); this.filters.from_month.grid_parent.hidden = custom; this.filters.to_month.grid_parent.hidden = custom; this.filters.from_date.grid_parent.hidden = !custom; this.filters.to_date.grid_parent.hidden = !custom; }
	get_filters() { const custom = this.filters.period_mode.get_value() === __("自定义日期"); return { company: this.filters.company.get_value(), period_mode: custom ? "custom" : "month", from_month: custom ? null : this.filters.from_month.get_value(), to_month: custom ? null : this.filters.to_month.get_value(), from_date: custom ? this.filters.from_date.get_value() : null, to_date: custom ? this.filters.to_date.get_value() : null, search_text: this.filters.search_text.get_value(), show_account_category_subtotal: this.filters.show_account_category_subtotal.get_value() }; }

	refresh() {
		if (!this.filters.company.get_value()) return;
		this.selected.clear(); this.render_selection(); this.latest = null;
		this.applied_filters = this.get_filters();
		const started = performance.now(); this.set_status(__("正在生成汇总..."), "orange");
		frappe.call({ method: "china_finance.services.voucher_summary.get_voucher_summary", args: { filters: this.applied_filters }, freeze: true }).then(({ message }) => { this.latest = message; this.render_metrics(message); this.render_table(message.voucher_rows || []); this.set_status(__("汇总数据已更新"), "green"); this.root.querySelector(".cf-runtime").textContent = __("运行时间：{0} 秒", [((performance.now() - started) / 1000).toFixed(3)]); });
	}
	set_status(message, color) { this.root.querySelector(".cf-status-message").innerHTML = `<i class="cf-status-dot ${color}"></i>${message}`; }
	render_metrics(message) { this.root.querySelector(".cf-voucher-count").textContent = message.totals.voucher_count || 0; this.root.querySelector(".cf-attachment-count").textContent = message.totals.attachment_count || 0; this.root.querySelector(".cf-debit-total").textContent = format_currency(message.totals.total_debit); this.root.querySelector(".cf-credit-total").textContent = format_currency(message.totals.total_credit); this.root.querySelector(".cf-applied-period").textContent = `${message.from_date} - ${message.to_date}`; }
	render_table(rows) { const empty = this.root.querySelector(".cf-summary-empty"); empty.classList.remove("hidden"); empty.style.display = rows.length ? "none" : "flex"; empty.querySelector(".cf-clear-search").classList.toggle("hidden", !this.filters.search_text.get_value()); this.root.querySelector(".cf-summary-list tbody").innerHTML = rows.map((row) => `<tr><td class="cf-select-column"><input type="checkbox" class="cf-select-row" value="${frappe.utils.escape_html(row.name)}" aria-label="${__("选择凭证")} ${frappe.utils.escape_html(row.statutory_number || row.name)}"></td><td>${this.document_link("China Accounting Voucher", row.name, row.statutory_number || row.name)}</td><td>${this.document_link(row.source_doctype, row.source_name)}</td><td>${frappe.datetime.str_to_user(row.posting_date)}</td><td>${frappe.utils.escape_html(row.remarks || "")}</td><td class="text-right">${format_currency(row.debit)}</td><td class="text-right">${format_currency(row.credit)}</td></tr>`).join(""); this.render_selection(); }
	document_link(doctype, name, label = name) {
		const text = frappe.utils.escape_html(label || "");
		if (!doctype || !name) return text;
		return frappe.utils.get_form_link(doctype, name, true, text);
	}
	render_selection() {
		const boxes = [...this.root.querySelectorAll(".cf-select-row")];
		boxes.forEach((box) => { box.checked = this.selected.has(box.value); box.closest("tr").classList.toggle("cf-selected-row", box.checked); });
		const all = this.root.querySelector(".cf-select-all");
		all.checked = boxes.length > 0 && this.selected.size === boxes.length;
		all.indeterminate = this.selected.size > 0 && this.selected.size < boxes.length;
		const bar = this.root.querySelector(".cf-selection-bar");
		bar.hidden = this.selected.size === 0;
		bar.querySelector(".cf-selected-count").textContent = __("已选择 {0} 张凭证", [this.selected.size]);
	}
	export_selected() {
		if (!this.selected.size || !this.latest) { frappe.msgprint(__("请先选择要导出的凭证")); return; }
		frappe.confirm(__("确认导出所选的 {0} 张凭证（CSV）？", [this.selected.size]), () => this.download_selected());
	}
	async download_selected() {
		const names = [...this.selected];
		const button = this.root.querySelector(".cf-export-selected"); button.disabled = true;
		try {
			const body = new URLSearchParams({ voucher_names: JSON.stringify(names), filters: JSON.stringify(this.applied_filters), format: "csv" });
			const response = await fetch("/api/method/china_finance.services.voucher_summary.export_selected_vouchers", {
				method: "POST", headers: { "X-Frappe-CSRF-Token": frappe.csrf_token, "Content-Type": "application/x-www-form-urlencoded" }, body,
			});
			if (!response.ok) {
				const result = await response.json().catch(() => ({}));
				let reason = result.message || result.exception;
				if (result._server_messages) {
					try { reason = JSON.parse(result._server_messages).map((item) => JSON.parse(item).message).join("；"); } catch (_) { /* Keep the response message. */ }
				}
				const plain = new DOMParser().parseFromString(String(reason || ""), "text/html").body.textContent.trim();
				throw new Error(plain || __("导出失败（HTTP {0}）", [response.status]));
			}
			const blob = await response.blob();
			const link = document.createElement("a"); link.href = URL.createObjectURL(blob);
			link.download = `selected-vouchers-${this.latest.from_date}-${this.latest.to_date}.csv`;
			link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
			this.selected.clear(); this.render_selection();
			frappe.show_alert({ message: __("已导出 {0} 张凭证", [names.length]), indicator: "green" });
		} catch (error) { frappe.msgprint({ message: frappe.utils.escape_html(error.message), indicator: "red" }); }
		finally { button.disabled = false; }
	}
	export_csv() { if (!this.latest) return; const values = [[__("科目编码"), __("科目名称"), __("借方金额"), __("贷方金额")], ...this.latest.rows.map((row) => [row.account_number || row.account, row.account_name, row.debit, row.credit])]; const csv = values.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\n"); const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" })); link.download = `${__("凭证汇总表")}-${this.latest.from_date}-${this.latest.to_date}.csv`; link.click(); URL.revokeObjectURL(link.href); }
	print() { if (!this.latest) return; const table = this.root.querySelector("table").cloneNode(true); table.querySelectorAll(".cf-select-column").forEach((cell) => cell.remove()); const win = window.open("", "_blank"); win.document.write(`<title>${__("凭证汇总表")}</title>${this.root.querySelector(".cf-summary-metrics").outerHTML}${table.outerHTML}`); win.print(); }
}
