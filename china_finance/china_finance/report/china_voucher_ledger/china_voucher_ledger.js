frappe.query_reports["China Voucher Ledger"] = {
	_client_selected_vouchers: new Set(),
	filters: [
		{
			fieldname: "company",
			label: __("公司"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "period_preset",
			label: __("凭证日期"),
			fieldtype: "Select",
			options: ["", __("本月凭证"), __("上月凭证"), __("近三个月"), __("本年凭证")],
			default: __("本月凭证"),
			on_change: (report) => {
				const preset = report.get_filter_value("period_preset");
				if (preset) set_quick_period(report, preset);
			},
		},
		{ fieldname: "from_date", label: __("起始日期"), fieldtype: "Date", reqd: 1 },
		{ fieldname: "to_date", label: __("截止日期"), fieldtype: "Date", reqd: 1 },
		{ fieldname: "voucher_word", label: __("凭证字号"), fieldtype: "Data" },
		{ fieldname: "accounting_period", label: __("会计期间"), fieldtype: "Data" },
		{
			fieldname: "source_doctype",
			label: __("来源类型"),
			fieldtype: "Select",
			options: ["", "Journal Entry", "Payment Entry"],
		},
		{ fieldname: "source_name", label: __("来源单据"), fieldtype: "Data" },
		{ fieldname: "account", label: __("科目"), fieldtype: "Link", options: "Account" },
		{
			fieldname: "party_type",
			label: __("往来类型"),
			fieldtype: "Select",
			options: ["", "Customer", "Supplier", "Employee", "Shareholder"],
		},
		{ fieldname: "party", label: __("往来单位"), fieldtype: "Data" },
		{ fieldname: "search_text", label: __("关键词"), fieldtype: "Data" },
	],
	tree: true,
	name_field: "row_id",
	parent_field: "parent_row_id",
	initial_depth: 1,
	get_datatable_options(options) {
		const select_all_html = `<input type="checkbox" class="china-voucher-select-all" aria-label="${__("全选凭证")}">`;
		if (options.columns?.[0]?.id === "_select_voucher") {
			options.columns[0].name = select_all_html;
			options.columns[0].content = select_all_html;
		}
		return options;
	},
	after_datatable_render(datatable) {
		const wrapper = $(datatable.wrapper);
		const header = wrapper.querySelector(".dt-header .dt-cell__content--header-0");
		if (header && !header.querySelector(".china-voucher-select-all")) {
			header.innerHTML = `<input type="checkbox" class="china-voucher-select-all" aria-label="${__("全选凭证")}">`;
		}
		update_voucher_selection_ui($(datatable.wrapper));
	},
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "_select_voucher") {
			if (!data?.voucher_snapshot || data.indent > 0) return "";
			const checked = frappe.query_reports["China Voucher Ledger"]._client_selected_vouchers.has(data.voucher_snapshot) ? "checked" : "";
			return `<input type="checkbox" class="china-voucher-select" value="${frappe.utils.escape_html(data.voucher_snapshot)}" ${checked} aria-label="${__("选择凭证")}">`;
		}
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname === "voucher_status" && data?.voucher_status !== undefined && data?.voucher_status !== null) {
			const status = {
				0: [__("草稿"), "orange"],
				1: [__("已提交"), "green"],
				2: [__("已取消"), "red"],
			}[data.voucher_status];
			if (!status) return "";
			return `<span class="china-voucher-status-text ${status[1]}">${status[0]}</span>`;
		}
		if (data?.indent > 0 && ["posting_date", "statutory_number", "accounting_period", "remarks", "source_doctype"].includes(column.fieldname)) {
			return "";
		}
		if (column.fieldname === "statutory_number" && data?.source_doctype && data?.source_name) {
			const route = frappe.utils.get_form_link(data.source_doctype, data.source_name);
			return `<a href="${route}" class="china-voucher-link" data-source-doctype="${encodeURIComponent(data.source_doctype)}" data-source-name="${encodeURIComponent(data.source_name)}">${formatted}</a>`;
		}
		if (!data || !["posting_date", "statutory_number", "accounting_period", "remarks", "source_doctype", "source_name", "source_event"].includes(column.fieldname)) {
			return formatted;
		}
		const index = Number.isInteger(row?._index) ? row._index : frappe.query_report.data?.indexOf(data);
		const previous = index > 0 ? frappe.query_report.data?.[index - 1] : null;
		if (previous && previous.voucher_snapshot === data.voucher_snapshot) return "";
		return formatted;
	},
	onload(report) {
		report.page.wrapper.addClass("china-voucher-ledger-report");
		ensure_voucher_ledger_styles();
		report.page.wrapper.on("click", ".china-voucher-link", (event) => {
			event.preventDefault();
			const source_doctype = decodeURIComponent(event.currentTarget.dataset.sourceDoctype);
			const source_name = decodeURIComponent(event.currentTarget.dataset.sourceName);
			frappe.set_route("Form", source_doctype, source_name);
		});
		report.page.wrapper.on("change", ".china-voucher-select", (event) => {
			const selected = frappe.query_reports["China Voucher Ledger"]._client_selected_vouchers;
			if (event.currentTarget.checked) selected.add(event.currentTarget.value);
			else selected.delete(event.currentTarget.value);
			update_voucher_selection_ui(report.page.wrapper);
		});
		report.page.wrapper.on("change", ".china-voucher-select-all", (event) => {
			const selected = frappe.query_reports["China Voucher Ledger"]._client_selected_vouchers;
			const visible_vouchers = get_visible_voucher_names();
			if (event.currentTarget.checked) visible_vouchers.forEach((name) => selected.add(name));
			else visible_vouchers.forEach((name) => selected.delete(name));
			update_voucher_selection_ui(report.page.wrapper);
		});
		report.page.add_menu_item(__("导出选中项"), () => export_selected_vouchers(report));
		hide_all_rows_export(report);
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
		if (!report.get_filter_value("from_date") || !report.get_filter_value("to_date")) {
			const today = frappe.datetime.get_today();
			report.set_filter_value({
				period_preset: __("本月凭证"),
				from_date: frappe.datetime.month_start(today),
				to_date: frappe.datetime.month_end(today),
			});
		}
	},
};

function export_selected_vouchers(report) {
	const voucher_names = Array.from(frappe.query_reports["China Voucher Ledger"]._client_selected_vouchers);
	if (!voucher_names.length) return frappe.msgprint(__("请先勾选要导出的凭证。"));
	open_url_post("/api/method/china_finance.services.voucher_ledger_export.download_selected_vouchers", {
		voucher_names: JSON.stringify(voucher_names),
		filters: JSON.stringify(report.get_filter_values(true)),
	});
}

function get_visible_voucher_names() {
	return [...new Set((frappe.query_report.data || [])
		.filter((row) => row.voucher_snapshot && !row.indent)
		.map((row) => row.voucher_snapshot))];
}

function update_voucher_selection_ui(wrapper) {
	const selected = frappe.query_reports["China Voucher Ledger"]._client_selected_vouchers;
	const names = get_visible_voucher_names();
	wrapper.find(".china-voucher-select").each((_, checkbox) => {
		checkbox.checked = selected.has(checkbox.value);
	});
	const select_all = wrapper.find(".china-voucher-select-all").get(0);
	if (select_all) {
		const selected_count = names.filter((name) => selected.has(name)).length;
		select_all.checked = names.length > 0 && selected_count === names.length;
		select_all.indeterminate = selected_count > 0 && selected_count < names.length;
	}
}

function hide_all_rows_export(report) {
	const hide = () => {
		report.page.wrapper.find(".dropdown-menu a, .dropdown-menu button").each((_, node) => {
			if (["导出", "Export"].includes((node.textContent || "").trim())) $(node).closest("li, .dropdown-item").hide();
		});
	};
	hide();
	const observer = new MutationObserver(hide);
	observer.observe(report.page.wrapper[0], { childList: true, subtree: true });
	setTimeout(() => observer.disconnect(), 10000);
}

function ensure_voucher_ledger_styles() {
	if (document.getElementById("china-voucher-ledger-inline-style")) return;
	$("<style>")
		.attr("id", "china-voucher-ledger-inline-style")
		.text(`
			.china-voucher-ledger-report .datatable {
				width: 100%;
			}
			.china-voucher-ledger-report .dt-row {
				width: 100%;
			}
			.china-voucher-ledger-report .dt-cell--col-4,
			.china-voucher-ledger-report .dt-cell--col-6,
			.china-voucher-ledger-report .dt-cell--col-8 {
				flex-grow: 1;
			}
			.china-voucher-ledger-report .dt-scrollable,
			.china-voucher-ledger-report .dt-header {
				width: 100%;
				max-width: 100%;
			}
			.china-voucher-ledger-report .dt-cell__content {
				line-height: 24px;
				padding-left: 6px;
				padding-right: 6px;
				white-space: nowrap;
				overflow: hidden;
				text-overflow: ellipsis;
			}
			.china-voucher-ledger-report .dt-row { min-height: 28px; }
			.china-voucher-ledger-report .dt-cell--header-0 .dt-cell__content,
			.china-voucher-ledger-report .dt-cell--col-0 .dt-cell__content {
				display: flex;
				align-items: center;
				justify-content: center;
			}
			.china-voucher-ledger-report .china-voucher-select {
				width: 15px;
				height: 15px;
				margin: 0;
				cursor: pointer;
			}
			.china-voucher-ledger-report .china-voucher-select-all {
				width: 15px;
				height: 15px;
				margin: 0;
				vertical-align: middle;
				cursor: pointer;
			}
		`)
		.appendTo(document.head);
}

function set_quick_period(report, period) {
	const today = frappe.datetime.get_today();
	// Select values may be translated, so compare the selected option's index
	// instead of comparing translated labels directly.
	const period_control = report.get_filter("period_preset");
	const selected_index = Number(period_control.$input?.prop("selectedIndex"));
	const raw_options = period_control.df.options || [];
	const options = Array.isArray(raw_options) ? raw_options : raw_options.split("\n");
	const period_index = Number.isInteger(selected_index) && selected_index >= 0
		? selected_index
		: options.indexOf(period);
	const period_text = String(period || "");
	let from_date;
	let to_date;
	if (period_text.includes("近三") || period_index === 3) {
		from_date = moment(today).subtract(2, "months").startOf("month").format("YYYY-MM-DD");
		to_date = today;
	} else if (period_text.includes("本年") || period_index === 4) {
		from_date = `${today.slice(0, 4)}-01-01`;
		to_date = today;
	} else if (period_text.includes("本月") || period_index === 1) {
		from_date = moment(today).startOf("month").format("YYYY-MM-DD");
		to_date = moment(today).endOf("month").format("YYYY-MM-DD");
	} else if (period_text.includes("上月") || period_index === 2) {
		const previous = moment(today).subtract(1, "month");
		from_date = previous.clone().startOf("month").format("YYYY-MM-DD");
		to_date = previous.clone().endOf("month").format("YYYY-MM-DD");
	} else {
		from_date = moment(today).startOf("month").format("YYYY-MM-DD");
		to_date = moment(today).endOf("month").format("YYYY-MM-DD");
	}
	report.set_filter_value("from_date", from_date);
	report.set_filter_value("to_date", to_date);
	report.refresh();
}
