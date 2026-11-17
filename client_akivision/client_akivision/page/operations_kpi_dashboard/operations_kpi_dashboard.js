frappe.pages["operations-kpi-dashboard"].on_page_load = function (wrapper) {
	new OperationsKPIDashboard(wrapper);
};

class OperationsKPIDashboard {
	constructor(wrapper) {
		$(wrapper).addClass("operations-kpi-page");
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Operations KPI Dashboard"), single_column: true });
		this.company = this.page.add_field({ fieldtype: "Link", fieldname: "company", label: __("Company"), options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1, change: () => this.refresh_from_first_timeout_page() });
		this.from_date = this.page.add_field({ fieldtype: "Date", fieldname: "from_date", label: __("From Date"), default: frappe.datetime.year_start(), reqd: 1, change: () => this.refresh_from_first_timeout_page() });
		this.to_date = this.page.add_field({ fieldtype: "Date", fieldname: "to_date", label: __("To Date"), default: frappe.datetime.get_today(), reqd: 1, change: () => this.refresh_from_first_timeout_page() });
		this.salesperson_limit = this.page.add_field({ fieldtype: "Select", fieldname: "salesperson_limit", label: __("Salesperson Rows"), options: "Top 10\nAll", default: "Top 10", change: () => this.refresh() });
		this.active_tab = "overview";
		this.dashboard = { get_value: () => this.active_tab };
		this.$tabs = $("<nav class='kpi-business-tabs' role='tablist' aria-label='业务分类'></nav>").appendTo(this.page.main);
		for (const [key, label] of [["overview", "经营总览"], ["sales", "销售与交付"], ["receivable", "回款与应收"], ["cost", "成本"], ["operations", "生产与采购"], ["high_tech", "高新合规"]]) {
			$("<button type='button' role='tab'></button>").text(label).attr({ id: `kpi-tab-${key}`, "aria-controls": "kpi-business-panel" }).data("tab", key).appendTo(this.$tabs).on("click", () => {
				this.active_tab = key;
				++this.cost_request_sequence;
				if (key === "cost") { this.cost_page = 1; return this.refresh_cost(); }
				if (this.data && this.data_filter_key === JSON.stringify(this.filters())) this.render(this.data);
				else this.refresh();
			});
		}
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.set_secondary_action(__("Export Excel"), () => this.export_excel(), "download");
		this.$body = $("<div id='kpi-business-panel' role='tabpanel' class='operations-kpi-dashboard'></div>").appendTo(this.page.main);
		this.request_sequence = 0;
		this.cost_request_sequence = 0;
		this.cost_page = 1;
		this.project_timeout_page = 1;
		this.project_timeout_page_length = 20;
		this.add_style();
		this.refresh();
	}

	refresh_from_first_timeout_page() {
		this.project_timeout_page = 1;
		this.refresh();
	}

	filters() {
		return {
			company: this.company.get_value(),
			from_date: this.from_date.get_value(),
			to_date: this.to_date.get_value(),
			salesperson_limit: (this.salesperson_limit.get_value() || "Top 10").toLowerCase() === "all" ? "all" : "top10",
			project_timeout_page: this.project_timeout_page,
			project_timeout_page_length: this.project_timeout_page_length,
		};
	}

	is_dashboard_selected(section_key) {
		const groups = { overview: [], sales: ["sales", "fulfillment", "salesperson", "year_over_year"], receivable: ["receivable", "receivable_control", "reconciliation"], operations: ["operations"], high_tech: ["high_tech"] };
		return (groups[this.active_tab] || []).includes(section_key);
	}

	export_excel() {
		if (!this.company.get_value() || !this.from_date.get_value() || !this.to_date.get_value()) {
			frappe.msgprint(__("Please select Company, From Date and To Date."));
			return;
		}
		open_url_post(frappe.request.url, {
			cmd: this.active_tab === "cost"
				? "client_akivision.client_akivision.api.operations_kpi_cost_export.export_cost_dashboard"
				: "client_akivision.client_akivision.api.operations_kpi_export.export_kpi_dashboard",
			filters: this.filters(),
		});
	}

	refresh() {
		if (this.active_tab === "cost") { this.cost_page = 1; return this.refresh_cost(); }
		if (!this.company.get_value() || !this.from_date.get_value() || !this.to_date.get_value()) return;
		if (this.from_date.get_value() > this.to_date.get_value()) {
			this.render_error(__("From Date cannot be later than To Date."));
			return;
		}
		const request_sequence = ++this.request_sequence;
		const filter_key = JSON.stringify(this.filters());
		this.render_loading();
		frappe.call({
			method: "client_akivision.client_akivision.api.operations_kpi.get_kpi_dashboard_data",
			args: { filters: this.filters() },
			freeze: false,
			callback: (r) => {
				if (request_sequence === this.request_sequence && this.active_tab !== "cost") {
					this.data_filter_key = filter_key;
					this.render(r.message || {});
				}
			},
			error: (error) => {
				if (request_sequence === this.request_sequence && this.active_tab !== "cost") this.render_error(error?.message || __("Unable to load KPI data."));
			},
		});
	}

	refresh_cost() {
		++this.request_sequence;
		const sequence = ++this.cost_request_sequence;
		this.update_cost_tabs();
		if (!this.company.get_value() || !this.from_date.get_value() || !this.to_date.get_value()) {
			this.render_error("请选择公司、开始日期和截止日期。"); return;
		}
		if (this.from_date.get_value() > this.to_date.get_value()) {
			this.render_error("开始日期不能晚于截止日期。"); return;
		}
		this.render_loading();
		const filters = {...this.filters(), page: this.cost_page || 1, page_length: 20};
		const current = () => this.active_tab === "cost" && sequence === this.cost_request_sequence;
		frappe.call({
			method: "client_akivision.client_akivision.api.operations_kpi_cost.get_cost_dashboard_data",
			args: {filters}, freeze: false,
			callback: r => { if (current()) this.render_cost(r.message || {}); },
			error: error => { if (current()) this.render_error(error?.message || "成本看板加载失败，请检查财务成本权限后重试。"); },
		});
	}

	update_cost_tabs() {
		this.$tabs.find("button").each((_, button) => {
			const active = $(button).data("tab") === this.active_tab;
			$(button).toggleClass("active", active).attr({"aria-selected": String(active), tabindex: active ? 0 : -1});
		});
		this.$body.attr("aria-labelledby", `kpi-tab-${this.active_tab}`);
	}

	render_cost(data) {
		this.$body.empty();
		this.update_cost_tabs();
		const currency = data.currency || "CNY";
		const display = (value, percent = false) => value == null ? "—"
			: format_number(value * (percent ? 100 : 1), null, 2) + (percent ? "%" : "");
		$("<div class='kpi-update-time'></div>").text(`数据更新时间：${data.generated_at || "—"} · 公司本位币：${currency}`).appendTo(this.$body);
		const metrics = data.metrics || {};
		const cards = keys => keys.map(([key, label]) => {
			const value = metrics[key] || {value: null, reason: "数据未提供"};
			const $card = this.card(label, {...value, status: ""});
			$card.find(".kpi-card-value").text((value.datatype === "Currency" && value.value != null ? currency + " " : "")
				+ display(value.value, value.datatype === "Percent"));
			$card.find(".kpi-card-meta").text(value.reason || "");
			$card.find(".kpi-card-status").text(value.value == null ? "待完善数据" : "参考口径");
			return $card;
		});
		this.section("核心成本指标", cards([["gross_margin", "参考综合毛利率"], ["budget_execution", "主营成本预算执行率"],
			["rework_scrap_ratio", "返工报废成本占比"], ["unit_cost_variance", "单位成本差异率"]]));
		this.section("财务与制造成本（口径分别列示）", cards([["revenue", "参考收入"], ["sales_cost", "参考销售成本"],
			["gross_profit", "参考毛利"], ["production_cost", "根工单成品入库成本"]]));
		const table = (title, columns, rows) => {
			const $section = $("<section class='kpi-section'></section>").appendTo(this.$body);
			$("<h4></h4>").text(title).appendTo($section);
			if (!rows.length) { $("<p class='text-muted'></p>").text("所选范围暂无可用数据。").appendTo($section); return $section; }
			const $scroll = $("<div style='overflow-x:auto'></div>").appendTo($section);
			const $table = $("<table class='table table-bordered' style='background:white;width:100%;border-collapse:collapse'></table>").appendTo($scroll);
			const $head = $("<tr></tr>").appendTo($("<thead></thead>").appendTo($table));
			columns.forEach(([, label]) => $("<th></th>").text(label).appendTo($head));
			const $body = $("<tbody></tbody>").appendTo($table);
			rows.forEach(row => {
				const $row = $("<tr></tr>").appendTo($body);
				columns.forEach(([key, , numeric]) => $("<td></td>").text(numeric ? display(row[key]) : row[key] ?? "—").appendTo($row));
			});
			$table.find("th, td").css({padding: "10px 12px", border: "1px solid #e2e8f0", "white-space": "nowrap"});
			return $section;
		};
		table(`月度财务趋势（${currency}）`, [["period", "月份"], ["revenue", "参考收入", true],
			["sales_cost", "参考销售成本", true], ["gross_profit", "参考毛利", true]], data.trend || []);
		const $products = table(`产品制造入库成本（${currency}，非产品销售毛利）`, [["item_code", "产品"], ["stock_uom", "库存单位"],
			["qty", "入库数量", true], ["production_cost", "入库成本", true], ["unit_cost", "单位成本", true],
			["entry_count", "制造凭证数", true]], data.product_rows || []);
		const pagination = data.pagination || {page: 1, page_length: 20, total: 0};
		const $pager = $("<div class='kpi-cost-pagination'></div>").appendTo($products);
		$("<span></span>").text(`共 ${pagination.total} 项 · 第 ${pagination.page} 页 `).appendTo($pager);
		for (const [label, step, disabled] of [["上一页", -1, pagination.page <= 1],
			["下一页", 1, pagination.page * pagination.page_length >= pagination.total]]) {
			$("<button class='btn btn-default btn-sm'></button>").text(label).prop("disabled", disabled).appendTo($pager)
				.on("click", () => { this.cost_page = pagination.page + step; this.refresh_cost(); });
		}
		const $variance = $("<section class='kpi-section'><h4>标准成本差异与成本结构</h4></section>").appendTo(this.$body);
		$("<p class='text-muted'></p>").text("暂不计算：历史标准成本快照、预算、实际料工费拆分及完工/试制规则尚待确认。不使用当前 BOM 重算历史标准，不将缺失值显示为零。").appendTo($variance);
		const $notes = $("<section class='kpi-section'><h4>口径与数据完整性说明</h4></section>").appendTo(this.$body);
		(data.warnings || []).forEach(warning => $("<p></p>").text(warning).appendTo($notes));
		table("参考科目范围（用于核对统计口径）", [["name", "科目"], ["account_type", "科目类型"]], data.accounts || []);
	}

	render(data) {
		this.render_sections(data);
		this.$tabs.find("button").each((_, button) => {
			const active = $(button).data("tab") === this.active_tab;
			$(button).toggleClass("active", active).attr({ "aria-selected": String(active), tabindex: active ? 0 : -1 });
		});
		this.$tabs.off("keydown").on("keydown", "button", (event) => {
			if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
			event.preventDefault();
			const buttons = this.$tabs.find("button").toArray();
			let index = buttons.indexOf(event.currentTarget);
			index = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
			buttons[index].click(); buttons[index].focus();
		});
		this.$body.attr("aria-labelledby", `kpi-tab-${this.active_tab}`);
		if (this.active_tab === "overview") {
			this.section("核心经营指标", [
				this.card("销售金额", data.sales?.total_sales_amount, "Sales Order List", {}, { featured: true }),
				this.card("订单总数", data.sales?.total_orders, "Sales Order List", {}, { comparison: data.sales?.order_comparison }),
				this.card("回款金额", data.receivable?.received_amount, "Receipt Record"),
				this.card("应收金额", data.receivable?.receivable_amount, "Receivable Aging Analysis"),
			]);
			const charts = this.get_overview_charts(data);
			const $charts = $("<div class='kpi-overview-grid'></div>").appendTo(this.$body);
			for (const chart of [charts.sales, charts.fulfillment]) {
				if (chart) this.donut_chart($("<div class='kpi-donut-chart kpi-module-chart'></div>").appendTo($charts)[0], chart);
			}
			this.section("重点关注", [
				this.card("未交货订单", data.delivery?.undelivered_orders, "Sales Order List", { status: "未交货" }),
				this.card("逾期超过90天", data.receivable?.overdue_over_90, "Receivable Aging Analysis"),
				this.card("安全库存预警数", data.operations?.safety_stock_warning_count),
				this.card("订单状态不一致数", data.reconciliation?.status_mismatch_count, "Sales Order List"),
			]);
			return;
		}
		const $sections = this.$body.children(".kpi-section");
		const $firstCards = $sections.find(".kpi-card-grid").first();
		if ($firstCards.length) {
			const $primary = $("<section class='kpi-section kpi-primary-section'><h4>核心指标</h4><div class='kpi-card-grid'></div></section>");
			$firstCards.children().slice(0, 4).appendTo($primary.find(".kpi-card-grid"));
			$primary.insertAfter(this.$body.find(".kpi-update-time"));
		}
		const $charts = this.$body.children(".kpi-overview-grid");
		if ($charts.length) $charts.insertAfter(this.$body.children(".kpi-primary-section"));
		$sections.each((_, section) => {
			const $section = $(section);
			if ($section.find(".kpi-card-grid").length && !$section.find(".kpi-card").length) $section.remove();
		});
		// Keep every detailed table full width below its chart, never nested inside a chart card.
		this.$body.find(".kpi-chart > .kpi-table-card").each((_, table) => {
			const $pair = $(table).closest(".kpi-template-pair");
			$(table).appendTo($pair);
		});
		if (!$firstCards.length) {
			const source = this.active_tab === "operations" ? data.operations || {} : data.high_tech || {};
			const metrics = this.active_tab === "operations"
				? [["生产完成率", "production_completion_rate"], ["采购准时率", "purchase_on_time_rate"], ["实时库存金额", "realtime_inventory_amount"], ["安全库存预警数", "safety_stock_warning_count"]]
				: [["高新收入金额", "high_tech_revenue"], ["高新收入占比", "high_tech_ratio"], ["研发项目数", "rd_project_count"], ["研发费用金额", "rd_expense_amount"]];
			this.section("核心指标", metrics.map(([label, key]) => this.card(label, source[key])));
			this.$body.children().last().insertAfter(this.$body.find(".kpi-update-time"));
			this.$body.children(".kpi-template-pair").insertAfter(this.$body.children(".kpi-section").first());
		}
		if (this.active_tab === "sales") {
			// Businessperson details follow all summary indicators and comparisons.
			this.$body.children(".kpi-section").filter((_, section) => $(section).children(".kpi-table-card").length > 0).appendTo(this.$body);
		}
	}

	render_sections(data) {
		this.data = data;
		this.$body.empty();
		const overviewCharts = this.get_overview_charts(data);
		this.$body.removeClass("kpi-all-sections");
		$("<div class='kpi-update-time'></div>").text("数据更新时间：" + new Date().toLocaleTimeString("zh-CN", { hour12: false })).appendTo(this.$body);
		// Follow the section order of the first worksheet in ERP表格模板.xlsx.
		if (this.is_dashboard_selected("sales")) this.section(__("Sales Overview"), [
			this.card(__("Total Sales Amount"), data.sales?.total_sales_amount, "Sales Order List", {}, { featured: true }),
			this.card(__("Total Orders"), data.sales?.total_orders, "Sales Order List", {}, { comparison: data.sales?.order_comparison }),
			this.card("已完成订单", data.sales?.fully_completed_orders, "Sales Order List", { per_delivered: [">=", 100], per_billed: [">=", 100] }),
			this.card("未交货订单", data.delivery?.undelivered_orders, "Sales Order List", { status: "未交货" }),
		]);
		const visibleCharts = [
			this.is_dashboard_selected("sales") && overviewCharts.sales,
			this.is_dashboard_selected("fulfillment") && overviewCharts.fulfillment,
			this.is_dashboard_selected("receivable") && overviewCharts.receivable,
		].filter(Boolean);
		if (visibleCharts.length) {
			const $charts = $("<div class='kpi-overview-grid'></div>").appendTo(this.$body);
			visibleCharts.forEach((chart) => this.donut_chart($("<div class='kpi-donut-chart kpi-module-chart'></div>").appendTo($charts)[0], chart));
		}
		if (this.is_dashboard_selected("fulfillment")) this.section(__("Order Fulfillment"), [
			this.card(__("Final Completed Orders"), data.delivery?.completed_orders, "Sales Order List", { status: "已完成" }),
			this.card(__("Pending Orders"), data.delivery?.pending_orders, "Sales Order List"),
			this.card(__("Fully Delivered Orders"), data.delivery?.fully_delivered_orders, "Sales Order List", { status: "已交货" }),
			this.card(__("Delivered Orders"), data.delivery?.delivered_orders, "Sales Order List", { status: "已交货" }),
			this.card(__("Delivering Orders"), data.delivery?.delivering_orders, "Sales Order List", { status: "交货中" }),
			this.card(__("Undelivered Orders"), data.delivery?.undelivered_orders, "Sales Order List", { status: "未交货" }),
		]);
		if (this.is_dashboard_selected("receivable")) this.section(__("Collection and Receivables"), [
			this.card(__("Collection Amount"), data.receivable?.received_amount, "Receipt Record"),
			this.card(__("Receivable Amount"), data.receivable?.receivable_amount, "Receivable Aging Analysis", {}, { featured: true }),
			this.card(__("Settled Documents"), data.receivable?.settled_documents, "Receivable Aging Analysis"),
			this.card(__("Unsettled Documents"), data.receivable?.unsettled_documents, "Receivable Aging Analysis"),
			this.card(__("Average Receivable Days"), data.receivable?.average_receivable_days, "Receivable Aging Analysis"),
			this.card(__("Receivable Turnover Days"), data.receivable?.receivable_turnover_days, "Receivable Aging Analysis"),
			this.card(__("Over 90 Days Overdue"), data.receivable?.overdue_over_90, "Receivable Aging Analysis"),
		]);
		if (this.is_dashboard_selected("salesperson")) this.table_section(__("Salesperson Performance"), data.salesperson || [], ["sales_person", "delivery_count", "delivery_amount", "personal_received", "personal_receivable", "delivery_rate", "collection_rate"], {
			permission: "sales_order_list", report: "Sales Order List", filter: "sales_person",
		});
		if (this.is_dashboard_selected("year_over_year")) this.section(__("Year-over-year Indicators"), [
			this.card(__("Prior-period Sales Amount"), data.year_over_year?.prior_sales_amount),
			this.card(__("Sales Growth Rate"), data.year_over_year?.sales_growth_rate),
			this.card(__("Receivable Growth Rate"), data.year_over_year?.receivable_growth_rate),
		]);
		if (this.is_dashboard_selected("reconciliation")) this.section(__("Reconciliation Warning"), [
			this.card(__("Unfinished Orders"), data.reconciliation?.unfinished_orders, "Sales Order List"),
			this.card(__("Status Mismatch Count"), data.reconciliation?.status_mismatch_count, "Sales Order List"),
		]);
		if (this.is_dashboard_selected("receivable_control")) this.render_receivable_control(data);
		if (this.is_dashboard_selected("operations")) this.render_operations(data);
		if (this.is_dashboard_selected("high_tech")) this.render_high_tech(data);
	}

	render_loading() {
		this.$body.empty();
		const $loading = $("<div class='kpi-loading-dashboard'></div>").appendTo(this.$body);
		for (let index = 0; index < 5; index++) {
			$("<section class='kpi-loading-section'><span class='kpi-skeleton kpi-skeleton-title'></span><div class='kpi-loading-grid'><span class='kpi-skeleton'></span><span class='kpi-skeleton'></span><span class='kpi-skeleton'></span><span class='kpi-skeleton'></span></div></section>").appendTo($loading);
		}
	}

	render_error(message = __("Unable to load KPI data.")) {
		this.$body.empty();
		const $error = $(this.empty_state_markup(message, true)).appendTo(this.$body);
		$('<button class="btn btn-primary btn-sm kpi-retry"><i class="fa fa-refresh"></i> ' + frappe.utils.escape_html(__("Retry")) + '</button>')
			.appendTo($error)
			.on("click", () => this.refresh());
	}

	section(title, cards, overview_chart = null) {
		const $section = $("<section class='kpi-section'><h4></h4><div class='kpi-card-grid'></div></section>").appendTo(this.$body);
		$section.find("h4").text(title);
		if (cards.some((card) => card.hasClass("kpi-featured-card"))) $section.find(".kpi-card-grid").addClass("kpi-card-grid-featured");
		if (overview_chart) {
			this.donut_chart($("<div class='kpi-donut-chart kpi-module-chart'></div>").insertAfter($section.find("h4"))[0], overview_chart);
		}
		cards.forEach((card) => $section.find(".kpi-card-grid").append(card));
	}

	card(label, value, report, route_options = {}, { featured = false, comparison = null } = {}) {
		value = value || { value: 0, datatype: "Float", status: "未设置" };
		const $card = $("<div class='kpi-card'><div class='kpi-card-header'><div class='kpi-card-label'></div><div class='kpi-card-status'></div></div><div class='kpi-card-value'></div><div class='kpi-card-meta'></div></div>");
		if (featured) $card.addClass("kpi-featured-card");
		$card.find(".kpi-card-label").text(label);
		$card.find(".kpi-card-value").text(this.format(value));
		const meta = [];
		$card.find(".kpi-card-status").html(this.metric_status(value, ""));
		if (value.target != null) {
			meta.push(`<div class='kpi-target-block'><span class='kpi-target'>${__("Target")}: ${this.format({ value: value.target, datatype: value.datatype })}</span>${this.target_progress(value)}</div>`);
		}
		if (comparison) meta.push(this.comparison_meta(comparison));
		$card.find(".kpi-card-meta").html(meta.join(""));
		if (report && this.can_open_report(report)) {
			$card.attr({ role: "link", tabindex: 0, title: __("Click to view details") });
			$card.addClass("kpi-clickable").on("click keydown", (event) => {
				if (event.type === "keydown" && !["Enter", " ", "Spacebar"].includes(event.key)) return;
				if (event.type === "keydown") event.preventDefault();
				this.open_report(report, route_options);
			});
		}
		return $card;
	}

	comparison_meta(comparison) {
		const item = (label, rate, period) => {
			if (rate == null) return `<span class='kpi-comparison muted'>${frappe.utils.escape_html(label)}：暂无可比数据</span>`;
			const value = Number(rate) * 100;
			const color = value > 0 ? "positive" : value < 0 ? "negative" : "muted";
			const sign = value > 0 ? "+" : "";
			const title = period ? `${period.from_date} - ${period.to_date}` : "";
			return `<span class='kpi-comparison ${color}' title='${frappe.utils.escape_html(title)}'>${frappe.utils.escape_html(label)} ${sign}${format_number(value, null, 1)}%</span>`;
		};
		return `<div class='kpi-comparison-meta'>${item("环比", comparison.mom_rate, comparison.previous_period)}${item("同比", comparison.yoy_rate, comparison.year_ago_period)}</div>`;
	}

	can_open_report(report) {
		const permission_keys = {
			"Sales Order List": "sales_order_list",
			"Delivery List": "delivery_list",
			"Receipt Record": "receipt_record",
			"Receivable Aging Analysis": "receivable_aging_analysis",
			"Purchase Delay Analysis": "purchase_delay_analysis",
			"High-tech Revenue Analysis": "high_tech_revenue_analysis",
		};
		const key = permission_keys[report];
		return Boolean(key && this.data?.drilldown_permissions?.[key]);
	}

	table_section(title, rows, fields, drilldown = null) {
		const $section = $("<section class='kpi-section'></section>").appendTo(this.$body);
		$("<h4></h4>").text(title).appendTo($section);
		this.table($section, title, rows, fields, drilldown);
	}

	get_overview_charts(data) {
		const sales = data.sales || {};
		const delivery = data.delivery || {};
		const receivable = data.receivable || {};
		const totalSales = sales.total_sales_amount?.value || 0;
		const highTechRevenue = sales.high_tech_revenue?.value || 0;
		const charts = {
			sales: {
				title: __("Sales Revenue Composition"),
				labels: [__("High-tech Revenue"), __("Other Revenue")],
				values: [highTechRevenue, Math.max(0, totalSales - highTechRevenue)],
				colors: ["#2490ef", "#c9d8f2"],
			},
			fulfillment: {
				title: __("Order Fulfillment Distribution"),
				labels: [__("Delivered Orders"), __("Delivering Orders"), __("Undelivered Orders")],
				values: [delivery.delivered_orders?.value || 0, delivery.delivering_orders?.value || 0, delivery.undelivered_orders?.value || 0],
				colors: ["#52ba8a", "#f0ad4e", "#e36d6d"],
			},
			receivable: {
				title: __("Collection and Receivable Composition"),
				labels: [__("Collection Amount"), __("Receivable Amount")],
				values: [receivable.received_amount?.value || 0, receivable.receivable_amount?.value || 0],
				colors: ["#52ba8a", "#f0ad4e"],
			},
		};
		for (const key of Object.keys(charts)) {
			if (!charts[key].values.some((value) => value > 0)) charts[key] = null;
		}
		return charts;
	}

	donut_chart(parent, chart) {
		$(parent).append(`<h5>${frappe.utils.escape_html(chart.title)}</h5>`);
		const $chart = $("<div class='kpi-donut-canvas'></div>").appendTo(parent);
		const legend = chart.labels.map((label, index) => `
			<span class='kpi-donut-legend-item'>
				<i style='background:${chart.colors[index]}'></i>
				<span>${frappe.utils.escape_html(label)}</span>
				<b>${format_number(chart.values[index], null, 0)}</b>
			</span>`).join("");
		$("<div class='kpi-donut-legend'></div>").html(legend).appendTo(parent);
		new frappe.Chart($chart[0], {
			type: "donut",
			height: 180,
			data: { labels: chart.labels, datasets: [{ values: chart.values }] },
			colors: chart.colors,
			showLegend: false,
		});
	}

	render_receivable_control(data) {
		const receivable = data.receivable || {};
		const total = receivable.total_receivable_balance?.value || 0;
		const ratio = (metric) => (total ? (metric?.value || 0) / total : 0);
		this.metric_table(__("Receivable Core Control Indicators"), __("Receivable Core Indicators"), [
			{ label: __("Receivable Balance"), metric: receivable.total_receivable_balance, ratio: 1 },
			{ label: __("Due Within 30 Days"), metric: receivable.aging_0_30, ratio: ratio(receivable.aging_0_30) },
			{ label: __("31-90 Days Overdue"), metric: receivable.aging_31_90, ratio: ratio(receivable.aging_31_90) },
			{ label: __("Over 90 Days Overdue"), metric: receivable.aging_over_90, ratio: ratio(receivable.aging_over_90) },
			{ label: __("Monthly Collection Target Completion"), metric: receivable.monthly_collection_completion, ratio: receivable.monthly_collection_completion?.achievement },
		], [__("Amount"), __("Ratio"), __("Warning Status")]);
		this.pair_section(
			($left) => {
				this.chart($left[0], __("Receivable Aging Distribution"), data.aging?.distribution || [], "label", [{ name: __("Amount"), values: (data.aging?.distribution || []).map((row) => row.amount) }], "bar");
				this.table($left, __("Receivable Aging Distribution Details"), data.aging?.distribution || [], ["label", "amount", "ratio"]);
			},
			($right) => this.table($right, __("Top 10 Overdue Customers"), data.aging?.top_customers || [], ["customer_name", "overdue_amount", "overdue_days", "risk_level"], {
				permission: "receivable_aging_analysis", report: "Receivable Aging Analysis", filter: "customer",
			}),
		);
	}

	render_operations(data) {
		const operations = data.operations || {};
		const productionTrend = data.production_trend || [];
		this.metric_table(__("Production and Purchasing Operations"), __("Operations Core Indicators"), [
			{ key: "production_completion_rate", label: __("Production Completion Rate"), metric: operations.production_completion_rate },
			{ key: "purchase_on_time_rate", label: __("Purchase On-time Rate"), metric: operations.purchase_on_time_rate },
			{ key: "realtime_inventory_amount", label: __("Realtime Inventory Amount"), metric: operations.realtime_inventory_amount },
			{ key: "safety_stock_warning_count", label: __("Safety Stock Warning Count"), metric: operations.safety_stock_warning_count },
			{ key: "purchase_in_transit_amount", label: __("Purchase In-transit Amount"), metric: operations.purchase_in_transit_amount },
			{ key: "material_over_consumption_rate", label: __("Material Over-consumption Rate"), metric: operations.material_over_consumption_rate },
		], [__("Value"), __("Target Value"), __("Achievement Rate"), __("Warning Status")], data.operations_drilldowns || {});
		this.pair_section(
			productionTrend.length
				? ($left) => {
					this.chart($left[0], __("Monthly Production Completion Trend"), productionTrend, "period", [{ name: __("Completion Rate"), chartType: "line", values: productionTrend.map((row) => row.completion_rate * 100) }], "line");
					this.table($left, __("Monthly Production Trend Details"), productionTrend, ["period", "planned_qty", "actual_qty", "completion_rate"]);
				}
				: null,
			($right) => this.table($right, __("Top 10 Delayed Suppliers"), data.delayed_suppliers || [], ["supplier_name", "delayed_order_count", "average_delay_days", "risk_level"], {
				permission: "purchase_delay_analysis", report: "Purchase Delay Analysis", filter: "supplier",
			}),
		);
	}

		render_high_tech(data) {
		const highTech = data.high_tech || {};
		this.metric_table(__("High-tech Compliance"), __("High-tech Core Indicators"), [
			{ label: __("High-tech Revenue Amount"), metric: highTech.high_tech_revenue },
			{ label: __("Total Revenue"), metric: highTech.total_revenue },
			{ label: __("High-tech Revenue Ratio"), metric: highTech.high_tech_ratio, featured: true },
			{ label: __("RD Project Count"), metric: highTech.rd_project_count },
			{ label: __("RD Expense Amount"), metric: highTech.rd_expense_amount },
			{ label: __("RD Expense Ratio"), metric: highTech.rd_expense_ratio },
		], [__("Year-to-date"), __("Annual Target"), __("Achievement Rate"), __("Compliance Status")]);
		this.pair_section(
			($left) => {
				this.chart($left[0], __("3-Year High-tech Trend"), data.high_tech_trend || [], "year", [{ name: __("High-tech Revenue Amount"), values: (data.high_tech_trend || []).map((row) => row.high_tech_revenue) }, { name: __("Total Revenue"), values: (data.high_tech_trend || []).map((row) => row.total_revenue) }], "bar");
				this.table($left, __("3-Year High-tech Trend Details"), data.high_tech_trend || [], ["year", "high_tech_revenue", "total_revenue", "high_tech_ratio"]);
			},
			($right) => this.table($right, __("Top 10 RD Projects"), data.high_tech_projects || [], ["project_name", "high_tech_revenue", "ratio"]),
		);
	}

	pair_section(render_left, render_right) {
		const $section = $("<section class='kpi-section kpi-template-pair'></section>").appendTo(this.$body);
		const $grid = $("<div class='kpi-pair-grid'></div>").appendTo($section);
		if (render_left) {
			const $left = $("<div class='kpi-chart'></div>").appendTo($grid);
			render_left($left);
		} else {
			$grid.addClass("kpi-pair-single");
		}
		const $right = $("<div class='kpi-table'></div>").appendTo($grid);
		render_right($right);
	}

	metric_table(section_title, table_title, rows, headers, drilldowns = {}) {
		const $section = $("<section class='kpi-section kpi-wide-section'></section>").appendTo(this.$body);
		$("<h4></h4>").text(section_title).appendTo($section);
		const $card = $("<div class='kpi-table-card kpi-metric-table'><h5></h5><div class='table-responsive'><table><thead></thead><tbody></tbody></table></div></div>").appendTo($section);
		$card.find("h5").text(table_title);
		$card.find("thead").html(`<tr><th>${__("Metric")}</th>${headers.map((header) => `<th>${frappe.utils.escape_html(header)}</th>`).join("")}</tr>`);
		$card.find("tbody").html(rows.map((row) => {
			const metric = row.metric || {};
			const drilldown = row.key ? drilldowns[row.key] : null;
			const values = headers.length === 3
				? [this.format(metric), this.format({ value: row.ratio, datatype: "Percent" }), this.metric_status(metric)]
				: [row.featured ? this.metric_value_with_progress(metric) : this.format(metric), metric.target == null ? "—" : this.format({ value: metric.target, datatype: metric.datatype }), metric.achievement == null ? "—" : this.format({ value: metric.achievement, datatype: "Percent" }), this.metric_status(metric)];
			const classes = [row.featured ? "kpi-featured-row" : "", drilldown ? "kpi-drilldown-row" : ""].filter(Boolean).join(" ");
			const attributes = drilldown
				? ` class='${classes}' role='link' tabindex='0' data-metric-key='${frappe.utils.escape_html(row.key)}' title='${frappe.utils.escape_html(__("Click to view details"))}'`
				: classes ? ` class='${classes}'` : "";
			return `<tr${attributes}><td>${frappe.utils.escape_html(row.label)}</td>${values.map((value) => `<td>${value}</td>`).join("")}</tr>`;
		}).join(""));
		$card.on("click keydown", ".kpi-drilldown-row", (event) => {
			if (event.type === "keydown" && !["Enter", " ", "Spacebar"].includes(event.key)) return;
			if (event.type === "keydown") event.preventDefault();
			const drilldown = drilldowns[$(event.currentTarget).data("metric-key")];
			if (drilldown) this.open_route(drilldown.route, drilldown.route_options);
		});
	}

	metric_status(metric, empty = "<span class='text-muted'>—</span>") {
		if (!metric || metric.status === "未设置" || !metric.status) return empty;
		const title = metric.target_direction
			? __("Status is based on the configured evaluation direction and thresholds.")
			: __("Status is based on the KPI calculation rules.");
		return `<span class='indicator-pill ${this.status_color(metric.status)}' title='${frappe.utils.escape_html(title)}'>${frappe.utils.escape_html(metric.status)}</span>`;
	}

	target_progress(metric) {
		const progress = Number(metric?.target_progress);
		if (metric?.target == null || !Number.isFinite(progress)) return "";
		const percent = Math.max(0, Math.min(100, progress));
		return `<div class='kpi-target-progress' title='${frappe.utils.escape_html(__("Target Progress"))}: ${format_number(percent, null, 1)}%'><span class='${this.progress_color(metric.status)}' style='width:${percent}%'></span></div>`;
	}

	metric_value_with_progress(metric) {
		return `<div class='kpi-featured-value'>${this.format(metric)}${this.target_progress(metric)}</div>`;
	}

	chart(parent, title, rows, label_field, datasets, type) {
		$(parent).append(`<h5>${frappe.utils.escape_html(title)}</h5>`);
		if (!rows.length || !datasets.some((dataset) => dataset.values.some((value) => Number(value || 0) !== 0))) {
			this.empty_state($(parent), __("No data matching the current filters."));
			return;
		}
		const canvas = $("<div class='kpi-trend-canvas'></div>").appendTo(parent)[0];
		new frappe.Chart(canvas, { type, height: 200, data: { labels: rows.map((row) => row[label_field]), datasets }, colors: ["#2490ef", "#52ba8a"] });
	}

	table($container, title, rows, fields, drilldown = null) {
		const labels = { label: __("Aging Period"), period: __("Period"), year: __("Year"), customer_name: __("Customer"), supplier_name: __("Supplier"), project: __("项目编号"), project_name: __("项目名称"), step_name: __("节点名称"), expected_end_date: __("计划完成日期"), actual_completed_on: __("实际完成时间"), remarks: __("备注"), sales_person: __("Sales Person"), amount: __("Amount"), planned_qty: __("计划生产数量"), actual_qty: __("实际生产数量"), overdue_amount: __("Overdue Amount"), overdue_days: __("Overdue Days"), risk_level: __("Risk Level"), delayed_order_count: __("Delayed Orders"), average_delay_days: __("Average Delay Days"), high_tech_revenue: __("High-tech Revenue Amount"), total_revenue: __("Total Revenue"), high_tech_ratio: __("High-tech Revenue Ratio"), ratio: __("Ratio"), completion_rate: __("Completion Rate"), delivery_count: __("Delivery Count"), delivery_amount: __("Delivery Amount"), personal_received: __("Personal Collection"), personal_receivable: __("Personal Receivable"), delivery_rate: __("Delivery Rate"), collection_rate: __("Collection Rate") };
		const $table = $("<div class='kpi-table-card'><h5></h5><div class='table-responsive'><table><thead></thead><tbody></tbody></table></div></div>").appendTo($container);
		const can_drilldown = drilldown && this.data?.drilldown_permissions?.[drilldown.permission];
		$table.find("h5").text(title);
		$table.find("thead").html(`<tr>${fields.map((field) => `<th class='${this.table_column_class(field)}'>${frappe.utils.escape_html(labels[field] || field)}</th>`).join("")}</tr>`);
		if (!rows.length) {
			$table.find("tbody").html(`<tr><td colspan='${fields.length}'>${this.empty_state_markup(__("No data matching the current filters."))}</td></tr>`);
			return;
		}

		$table.find("tbody").html(rows.map((row) => {
			const drill_value = can_drilldown ? row[drilldown.filter] : null;
			const is_clickable = Boolean(drill_value);
			const row_attributes = is_clickable
				? ` class='kpi-drilldown-row' role='link' tabindex='0' data-drill-value='${frappe.utils.escape_html(String(drill_value))}' title='${frappe.utils.escape_html(__("Click to view details"))}'`
				: "";
			return `<tr${row_attributes}>${fields.map((field) => `<td class='${this.table_column_class(field)}'>${this.table_cell_value(row[field], field)}</td>`).join("")}</tr>`;
		}).join(""));

		if (can_drilldown) {
			$table.on("click keydown", ".kpi-drilldown-row", (event) => {
				if (event.type === "keydown" && !["Enter", " ", "Spacebar"].includes(event.key)) return;
				if (event.type === "keydown") event.preventDefault();
				this.open_report(drilldown.report, { [drilldown.filter]: $(event.currentTarget).data("drill-value") });
			});
		}
	}

	empty_state($container, message) {
		$(this.empty_state_markup(message)).appendTo($container);
	}

	empty_state_markup(message, with_action = false) {
		return `<div class='kpi-empty-state${with_action ? " kpi-error-state" : ""}'><span class='kpi-empty-mark'>—</span><span>${frappe.utils.escape_html(message)}</span></div>`;
	}

	open_report(report, options) {
		this.open_route(["query-report", report], { ...this.filters(), ...options });
	}

	open_route(route, options = {}) {
		frappe.route_options = options;
		frappe.set_route(...route);
	}

	format(metric = {}) {
		if (metric.value == null) return "—";
		if (metric.datatype === "Currency") return format_currency(metric.value);
		if (metric.datatype === "Percent") return format_number(metric.value * 100, null, 1) + "%";
		return format_number(metric.value, null, metric.datatype === "Int" ? 0 : 2);
	}

	table_value(value, field) {
		if (["amount", "overdue_amount", "high_tech_revenue", "total_revenue", "delivery_amount", "personal_received", "personal_receivable"].includes(field)) return format_currency(value || 0);
		if (["completion_rate", "high_tech_ratio", "delivery_rate", "collection_rate", "ratio"].includes(field)) return format_number((value || 0) * 100, null, 1) + "%";
		if (["planned_qty", "actual_qty", "average_delay_days", "overdue_days", "delayed_order_count", "delivery_count"].includes(field)) return format_number(value || 0, null, 2);
		return value == null ? "" : String(value);
	}

	table_cell_value(value, field) {
		const text = frappe.utils.escape_html(this.table_value(value, field));
		if (field === "project" && value) return `<a href="/app/project/${encodeURIComponent(value)}" class="kpi-project-link">${text}</a>`;
		if (field === "remarks") return `<span class="kpi-timeout-remarks ellipsis" title="${text}">${text || "-"}</span>`;
		if (field === "risk_level") {
			const color_map = { "Low Risk": "green", "Medium Risk": "orange", "High Risk": "red" };
			const color = color_map[value] || "gray";
			const display_text = frappe.utils.escape_html(__(value || ""));
			return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${display_text}</span></span>`;
		}
		if (!["delivery_rate", "collection_rate"].includes(field)) return text;
		const percent = Math.max(0, Math.min(100, Number(value || 0) * 100));
		return `<div class='kpi-table-rate'><span>${text}</span><i><b style='width:${percent}%'></b></i></div>`;
	}

	table_column_class(field) {
		if (["customer_name", "supplier_name", "project_name", "sales_person", "label"].includes(field)) return "kpi-table-name";
		if (["amount", "overdue_amount", "high_tech_revenue", "total_revenue", "delivery_amount", "personal_received", "personal_receivable"].includes(field)) return "kpi-table-amount";
		if (["year", "planned_qty", "actual_qty", "completion_rate", "high_tech_ratio", "overdue_days", "delayed_order_count", "average_delay_days", "delivery_count", "delivery_rate", "collection_rate", "ratio"].includes(field)) return "kpi-table-number";
		return "";
	}

	status_color(status) { return { "正常": "green", "达标": "green", "合规": "green", "预警": "orange", "危险": "red", "未达标": "red", "不合规": "red", "未设置": "gray" }[status] || "gray"; }

	progress_color(status) { return { "预警": "orange", "危险": "red", "未达标": "red", "不合规": "red" }[status] || "blue"; }

	add_style() {
		if (document.getElementById("operations-kpi-style")) return;
		$(
			`<style id="operations-kpi-style">
				.operations-kpi-page .page-form .form-control,
				.operations-kpi-page .page-form .input-with-feedback,
				.operations-kpi-page .page-form .awesomplete > input {
					background-color: #fff !important;
					border: 1px solid var(--border-color) !important;
					box-shadow: none !important;
				}
				.operations-kpi-page .page-form .form-control:focus,
				.operations-kpi-page .page-form .awesomplete > input:focus {
					border-color: var(--blue-500) !important;
					box-shadow: 0 0 0 1px var(--blue-500) !important;
				}
				.operations-kpi-dashboard {
					box-sizing: border-box;
					max-width: 1520px;
					margin: 0 auto;
					padding: 24px clamp(20px, 3vw, 48px) 56px;
					--kpi-hero-from: #1d4ed8;
					--kpi-hero-via: #2490ef;
					--kpi-hero-to: #60a5fa;
				}
				.kpi-section { margin: 0 0 36px; }
				.kpi-section h4 {
					position: relative;
					margin: 0 0 16px;
					padding-left: 12px;
					color: var(--text-color);
					font-size: 15px;
					font-weight: 700;
					letter-spacing: .02em;
				}
				.kpi-section h4::before {
					content: "";
					position: absolute;
					left: 0;
					top: 50%;
					width: 3px;
					height: 16px;
					border-radius: 999px;
					background: linear-gradient(180deg, var(--kpi-hero-via), var(--kpi-hero-from));
					transform: translateY(-50%);
				}
				.kpi-card-grid {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
					gap: 16px;
				}
				.kpi-card-grid-featured { grid-template-columns: repeat(5, minmax(0, 1fr)); }
				.kpi-card-grid-featured .kpi-featured-card { grid-column: span 2; }
				.kpi-card, .kpi-chart, .kpi-table-card, .kpi-donut-chart {
					box-sizing: border-box;
					border: 1px solid var(--border-color);
					border-radius: 14px;
					background: var(--card-bg);
					box-shadow: 0 1px 3px rgba(16, 24, 40, .06), 0 1px 2px rgba(16, 24, 40, .04);
				}
				.kpi-card { min-height: 128px; padding: 18px 20px; }
				.kpi-chart, .kpi-table-card, .kpi-donut-chart { padding: 18px 20px; }
				.kpi-featured-card {
					border: 0;
					background: linear-gradient(135deg, var(--kpi-hero-from) 0%, var(--kpi-hero-via) 55%, var(--kpi-hero-to) 100%);
					box-shadow: 0 6px 18px rgba(36, 144, 239, .28);
				}
				.kpi-featured-card .kpi-card-label { color: rgba(255, 255, 255, .82); }
				.kpi-featured-card .kpi-card-value {
					color: #fff;
					font-size: clamp(30px, 2.6vw, 40px);
					letter-spacing: -.02em;
				}
				.kpi-featured-card .kpi-target { color: rgba(255, 255, 255, .78); }
				.kpi-featured-card .kpi-target-progress { background: rgba(255, 255, 255, .25); }
				.kpi-featured-card .kpi-target-progress > span { background: #fff; }
				.kpi-featured-card .kpi-card-status .indicator-pill {
					background: rgba(255, 255, 255, .16);
					color: #fff;
				}
				.kpi-clickable { cursor: pointer; transition: box-shadow .18s ease, transform .18s ease; }
				.kpi-clickable:hover { box-shadow: 0 10px 24px rgba(16, 24, 40, .1); transform: translateY(-2px); }
				.kpi-featured-card.kpi-clickable:hover { box-shadow: 0 12px 28px rgba(36, 144, 239, .36); }
				.kpi-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
				.kpi-card-label { min-height: 20px; color: var(--text-muted); font-size: 12px; font-weight: 500; letter-spacing: .02em; }
				.kpi-card-status { flex: 0 0 auto; min-height: 20px; }
				.kpi-card-value {
					margin: 10px 0;
					color: var(--text-color);
					font-size: 26px;
					font-weight: 700;
					font-variant-numeric: tabular-nums;
					letter-spacing: -.01em;
					line-height: 1.15;
				}
				.kpi-card-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
				.kpi-comparison-meta { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; }
				.kpi-comparison { white-space: nowrap; }
				.kpi-comparison.positive { color: var(--green-500, #16a34a); }
				.kpi-comparison.negative { color: var(--red-500, #dc2626); }
				.kpi-comparison.muted { color: var(--text-muted); }
				.kpi-target-block { display: grid; gap: 6px; width: 100%; }
				.kpi-target { color: var(--text-muted); font-size: 12px; }
				.kpi-target-progress { height: 5px; overflow: hidden; border-radius: 999px; background: var(--control-bg); }
				.kpi-target-progress > span { display: block; height: 100%; min-width: 0; border-radius: inherit; background: var(--blue-500); transition: width .2s ease; }
				.kpi-target-progress > .orange { background: var(--orange-500); }
				.kpi-target-progress > .red { background: var(--red-500); }
				.kpi-module-chart {
					display: grid;
					grid-template-columns: minmax(200px, 240px) minmax(0, 1fr);
					align-items: center;
					column-gap: 24px;
					margin: 0 0 16px;
				}
				.kpi-module-chart h5 { grid-column: 1 / -1; }
				.kpi-donut-canvas .chart-container { margin: 0 auto; }
				.kpi-donut-legend { display: flex; flex-direction: column; gap: 10px; font-size: 13px; }
				.kpi-donut-legend-item { display: flex; align-items: center; gap: 8px; color: var(--text-muted); }
				.kpi-donut-legend-item i { width: 9px; height: 9px; border-radius: 50%; flex: 0 0 9px; }
				.kpi-donut-legend-item b { margin-left: auto; color: var(--text-color); font-weight: 600; font-variant-numeric: tabular-nums; }
				.kpi-visual-grid, .kpi-pair-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
				.kpi-pair-grid > *, .kpi-visual-grid > * { min-width: 0; }
				.kpi-pair-grid.kpi-pair-single { grid-template-columns: minmax(0, 1fr); }
				.kpi-template-pair { margin-top: -14px; }
				.kpi-table-card h5, .kpi-chart h5, .kpi-donut-chart h5 {
					margin: 0 0 12px;
					color: var(--text-muted);
					font-size: 13px;
					font-weight: 600;
					letter-spacing: .02em;
				}
				.kpi-table-card .table-responsive { max-width: 100%; overflow-x: auto; }
				.kpi-table-card table { width: 100%; min-width: 0; font-size: 12.5px; }
				.kpi-table-card th {
					color: var(--text-muted);
					font-size: 11px;
					font-weight: 600;
					letter-spacing: .04em;
					text-transform: uppercase;
					white-space: nowrap;
				}
				.kpi-table-card th, .kpi-table-card td { padding: 10px 8px; border-bottom: 1px solid var(--border-color); text-align: left; vertical-align: middle; }
				.kpi-table-card tbody tr:last-child td { border-bottom: 0; }
				.kpi-metric-table td:first-child { width: 34%; font-weight: 500; }
				.kpi-metric-table td:not(:first-child), .kpi-metric-table th:not(:first-child) { text-align: right; }
				.kpi-table-name { width: 38%; min-width: 156px; }
				.kpi-table-number, .kpi-table-amount { min-width: 92px; text-align: right !important; white-space: nowrap; }
				.kpi-table-amount { font-weight: 600; }
				.kpi-table-card tbody tr { transition: background-color .16s ease; }
				.kpi-table-card tbody tr:not(.kpi-featured-row):hover td { background: var(--highlight-color); }
				.kpi-drilldown-row { cursor: pointer; outline: none; }
				.kpi-drilldown-row:focus-visible td { background: var(--highlight-color); box-shadow: inset 0 1px 0 var(--blue-500), inset 0 -1px 0 var(--blue-500); }
				.kpi-drilldown-row td:first-child { position: relative; }
				.kpi-drilldown-row td:first-child::after { content: "›"; display: inline-block; margin-left: 6px; color: var(--blue-500); font-size: 15px; line-height: 0; }
				.kpi-table-rate { display: grid; justify-items: end; gap: 4px; }
				.kpi-table-rate i { display: block; width: 72px; height: 4px; overflow: hidden; border-radius: 999px; background: var(--control-bg); }
				.kpi-table-rate b { display: block; height: 100%; border-radius: inherit; background: var(--blue-500); }
				.kpi-empty-state { display: flex; min-height: 112px; align-items: center; justify-content: center; gap: 8px; color: var(--text-muted); font-size: 13px; text-align: center; }
				.kpi-error-state { flex-direction: column; gap: 12px; padding: 32px 16px; }
				.kpi-empty-mark { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center; border: 1px solid var(--border-color); border-radius: 50%; color: var(--blue-500); }
				.kpi-loading-dashboard { display: grid; gap: 30px; }
				.kpi-loading-section { display: grid; gap: 14px; }
				.kpi-loading-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
				.kpi-skeleton { display: block; min-height: 126px; border-radius: 14px; background: linear-gradient(90deg, var(--control-bg) 25%, var(--highlight-color) 50%, var(--control-bg) 75%); background-size: 200% 100%; animation: kpi-skeleton-shimmer 1.4s ease infinite; }
				.kpi-skeleton-title { min-height: 18px; width: 180px; border-radius: 5px; }
				@keyframes kpi-skeleton-shimmer { to { background-position: -200% 0; } }
				.kpi-metric-table tr.kpi-featured-row td { background: var(--highlight-color); font-weight: 600; }
				.kpi-metric-table tr.kpi-featured-row td:first-child { box-shadow: inset 3px 0 0 var(--kpi-hero-via); }
				.kpi-featured-value { display: grid; justify-items: end; gap: 6px; font-size: 15px; font-weight: 700; }
				.kpi-featured-value .kpi-target-progress { width: min(100%, 148px); }
				@media (max-width: 1199px) {
					.kpi-card-grid-featured { grid-template-columns: repeat(3, minmax(0, 1fr)); }
				}
				@media (max-width: 900px) {
					.operations-kpi-dashboard { padding: 18px 16px 36px; }
					.kpi-visual-grid, .kpi-pair-grid { grid-template-columns: 1fr; }
					.kpi-visual-grid > *, .kpi-pair-grid > * { min-width: 0; max-width: 100%; }
					.kpi-card-grid-featured, .kpi-loading-grid { grid-template-columns: 1fr; }
					.kpi-card-grid-featured .kpi-featured-card { grid-column: span 1; }
					.kpi-module-chart { grid-template-columns: 1fr; row-gap: 12px; }
					.kpi-donut-legend { flex-direction: row; flex-wrap: wrap; gap: 8px 16px; }
					.kpi-donut-legend-item b { margin-left: 0; }
				}
				@media (max-width: 640px) {
					.kpi-card-value { font-size: 22px; }
				}
				/* Compact management dashboard: equal KPI cards and adjacent visual panels. */
				.operations-kpi-dashboard { max-width: none; padding: 12px 18px 28px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; background: #f7f9fc; }
				.operations-kpi-dashboard.kpi-all-sections { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
				.operations-kpi-dashboard > * { min-width: 0; }
				.kpi-update-time { grid-column: 1 / -1; text-align: right; color: var(--text-muted); font-size: 11px; }
				.operations-kpi-dashboard > .kpi-section:nth-child(2), .kpi-overview-grid, .kpi-template-pair, .kpi-wide-section, .kpi-loading-dashboard { grid-column: 1 / -1; }
				.kpi-section { margin: 0; min-width: 0; }
				.kpi-section h4 { margin-bottom: 9px; font-size: 13px; }
				.kpi-card-grid, .kpi-card-grid-featured { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
				.kpi-section:nth-child(2) .kpi-card-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
				.kpi-card-grid-featured .kpi-featured-card { grid-column: auto; }
				.kpi-card, .kpi-chart, .kpi-table-card, .kpi-donut-chart { border-radius: 8px; box-shadow: none; border: 1px solid var(--border-color); background: var(--card-bg); }
				.kpi-card { min-height: 108px; padding: 12px 14px; }
				.kpi-card-value, .kpi-featured-card .kpi-card-value { font-size: clamp(20px, 1.65vw, 28px); margin: 6px 0; overflow-wrap: anywhere; }
				.kpi-featured-card { border-top: 3px solid #2563eb; }
				.kpi-featured-card .kpi-card-value { color: #2563eb; }
				.kpi-featured-card .kpi-card-label, .kpi-featured-card .kpi-target { color: var(--text-muted); }
				.kpi-featured-card .kpi-card-status .indicator-pill { background: var(--control-bg); color: var(--text-color); }
				.kpi-featured-card .kpi-target-progress { background: var(--control-bg); }
				.kpi-featured-card .kpi-target-progress > span { background: #2563eb; }
				.kpi-featured-card.kpi-clickable:hover { box-shadow: 0 3px 10px rgba(36,144,239,.12); }
				.kpi-card-label { font-size: 12px; }
				.kpi-comparison-meta { gap: 4px 10px; font-size: 11px; }
				.kpi-overview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
				.kpi-overview-grid > :last-child:nth-child(odd):not(:first-child) { grid-column: 1 / -1; }
				@media (min-width: 1200px) {
					.kpi-overview-grid:has(> :nth-child(3)) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
					.kpi-overview-grid > :last-child:nth-child(3) { grid-column: auto; }
					.kpi-overview-grid:has(> :nth-child(3)) .kpi-module-chart { grid-template-columns: 140px minmax(0, 1fr); column-gap: 8px; }
				}
				.kpi-module-chart { grid-template-columns: 180px minmax(0, 280px); justify-content: start; column-gap: 16px; margin: 0; }
				.kpi-chart, .kpi-table-card, .kpi-donut-chart { padding: 12px 14px; }
				.kpi-donut-legend { font-size: 12px; gap: 12px; }
				.kpi-donut-legend-item b { margin-left: 12px; }
				.kpi-pair-grid, .kpi-visual-grid { gap: 12px; }
				.kpi-template-pair { margin-top: 0; }
				.kpi-table-card th, .kpi-table-card td { padding: 7px 6px; }
				.kpi-table-card .table-responsive { max-height: 350px; }
				.kpi-table-card thead { position: sticky; top: 0; background: var(--card-bg); z-index: 1; }
				.kpi-table-name { min-width: 100px; width: auto; }
				.kpi-table-number, .kpi-table-amount { min-width: 76px; }
				@media (max-width: 1100px) {
					.kpi-module-chart { grid-template-columns: 140px minmax(0, 1fr); gap: 8px; }
					.kpi-card-header { flex-wrap: wrap; gap: 2px; }
				}
				@media (max-width: 900px) {
					.operations-kpi-dashboard.kpi-all-sections, .kpi-overview-grid { grid-template-columns: minmax(0, 1fr); }
					.kpi-section:nth-child(2) .kpi-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
					.kpi-module-chart { grid-template-columns: 160px minmax(0, 280px); }
					.kpi-donut-legend { flex-direction: column; }
				}
				@media (max-width: 520px) {
					.operations-kpi-dashboard { padding: 10px; }
					.kpi-card-grid, .kpi-section:nth-child(2) .kpi-card-grid { grid-template-columns: minmax(0, 1fr); }
					.kpi-module-chart { grid-template-columns: minmax(0, 1fr); }
					.kpi-donut-legend { padding-bottom: 10px; }
				}
				/* One business context per tab, with a fixed reading order. */
				.kpi-business-tabs { display: flex; gap: 24px; padding: 0 18px; border-bottom: 1px solid var(--border-color); background: var(--card-bg); overflow-x: auto; }
				.kpi-business-tabs button { flex: 0 0 auto; padding: 14px 2px 11px; background: transparent; border: 0; border-bottom: 3px solid transparent; color: var(--text-muted); font-size: 14px; cursor: pointer; }
				.kpi-business-tabs button.active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 600; }
				.kpi-business-tabs button:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
				.operations-kpi-dashboard, .operations-kpi-dashboard.kpi-all-sections { display: flex; flex-direction: column; gap: 20px; padding: 16px 18px 32px; }
				.operations-kpi-dashboard > * { width: 100%; }
				.operations-kpi-dashboard .kpi-card-grid, .operations-kpi-dashboard .kpi-card-grid-featured { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
				.operations-kpi-dashboard .kpi-overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
				.operations-kpi-dashboard .kpi-overview-grid > * { grid-column: auto !important; min-height: 230px; }
				.operations-kpi-dashboard .kpi-overview-grid .kpi-module-chart { grid-template-columns: minmax(140px, 42%) minmax(0, 1fr); gap: 12px; }
				.operations-kpi-dashboard .kpi-card { min-height: 118px; background: var(--card-bg, #fff); }
				.operations-kpi-dashboard .kpi-section h4 { font-size: 14px; margin-bottom: 12px; }
				.operations-kpi-dashboard .kpi-template-pair { display: flex; flex-direction: column; gap: 16px; }
				.operations-kpi-dashboard .kpi-pair-grid { align-items: stretch; }
				.operations-kpi-dashboard .kpi-pair-grid > .kpi-table > .kpi-table-card { height: 100%; }
				.operations-kpi-dashboard .kpi-section > .kpi-table-card > h5 { display: none; }
				.operations-kpi-dashboard .kpi-table-card th { text-transform: none; }
				.operations-kpi-dashboard .kpi-table-card th, .operations-kpi-dashboard .kpi-table-card td { padding: 10px; }
				.operations-kpi-dashboard .kpi-table-card .table-responsive { max-height: 420px; }
				@media (max-width: 1000px) {
					.operations-kpi-dashboard .kpi-card-grid, .operations-kpi-dashboard .kpi-card-grid-featured { grid-template-columns: repeat(2, minmax(0, 1fr)); }
				}
				@media (max-width: 700px) {
					.kpi-business-tabs { gap: 18px; padding: 0 10px; }
					.operations-kpi-dashboard .kpi-overview-grid, .operations-kpi-dashboard .kpi-pair-grid { grid-template-columns: minmax(0, 1fr); }
					.operations-kpi-dashboard { padding: 12px 10px 24px; }
				}
				@media (max-width: 440px) {
					.operations-kpi-dashboard .kpi-card-grid { grid-template-columns: minmax(0, 1fr); }
					.operations-kpi-dashboard .kpi-overview-grid .kpi-module-chart { grid-template-columns: minmax(0, 1fr); }
				}
			</style>`
		).appendTo(document.head);
	}
}
