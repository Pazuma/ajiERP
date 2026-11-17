import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/client_akivision";
const jqueryPath = "/home/cst/frappe_docker/development/frappe-bench/apps/frappe/frappe/public/js/lib/jquery/jquery.min.js";
const dashboardJs = await fs.readFile(path.join(appRoot, "page/operations_kpi_dashboard/operations_kpi_dashboard.js"), "utf8");
const jqueryJs = await fs.readFile(jqueryPath, "utf8");

const metric = (value, datatype = "Int", target = null, status = "正常") => ({value, datatype, target, status, achievement: target ? value / target : null, target_progress: target ? (value / target) * 100 : null});
const payload = {
	filters: {company: "示例公司", from_date: "2026-01-01", to_date: "2026-08-22", salesperson_limit: 10},
	drilldown_permissions: {sales_order_list: true, delivery_list: true, receipt_record: false, receivable_aging_analysis: true, purchase_delay_analysis: true, high_tech_revenue_analysis: false},
	operations_drilldowns: {production_completion_rate: {route: ["List", "Work Order"], route_options: {company: "示例公司"}}},
	sales: {total_orders: metric(260), total_sales_amount: metric(100000, "Currency", 120000), high_tech_revenue: metric(20000, "Currency"), high_tech_ratio: metric(0.2, "Percent", 0.15)},
	delivery: {completed_orders: metric(126), pending_orders: metric(134), fully_delivered_orders: metric(180), delivered_orders: metric(237), delivering_orders: metric(111), undelivered_orders: metric(23)},
	receivable: {received_amount: metric(100000, "Currency"), receivable_amount: metric(100000, "Currency"), settled_documents: metric(334), unsettled_documents: metric(136), average_receivable_days: metric(22, "Float"), overdue_over_90: metric(12000, "Currency"), receivable_turnover_days: metric(22, "Float"), total_receivable_balance: metric(100000, "Currency"), aging_0_30: metric(50000, "Currency"), aging_31_90: metric(38000, "Currency"), aging_over_90: metric(12000, "Currency"), monthly_collection_completion: metric(0.8, "Percent", 1)},
	salesperson: [
		{sales_person: "张三", delivery_count: 20, delivery_amount: 20000, personal_received: 16000, personal_receivable: 4000, delivery_rate: 0.72, collection_rate: 0.8},
		{sales_person: "李四", delivery_count: 12, delivery_amount: 15000, personal_received: 10000, personal_receivable: 5000, delivery_rate: 0.6, collection_rate: 0.67},
	],
	year_over_year: {prior_sales_amount: metric(80000, "Currency"), sales_growth_rate: metric(0.25, "Percent"), receivable_growth_rate: metric(0.1, "Percent")},
	reconciliation: {unfinished_orders: metric(134), status_mismatch_count: metric(3)},
	aging: {distribution: [{label: "30天内到期", amount: 50000, ratio: 0.5}, {label: "31-60天逾期", amount: 38000, ratio: 0.38}], top_customers: [{customer_name: "客户甲", overdue_amount: 12000, overdue_days: 95, risk_level: "高风险"}]},
	operations: {production_completion_rate: metric(0.88, "Percent", 0.9), purchase_on_time_rate: metric(0.76, "Percent", 0.8), realtime_inventory_amount: metric(88000, "Currency"), safety_stock_warning_count: metric(4), purchase_in_transit_amount: metric(33000, "Currency"), material_over_consumption_rate: metric(0.03, "Percent")},
	production_trend: [{period: "2026-06", planned_qty: 100, actual_qty: 90, completion_rate: 0.9}, {period: "2026-07", planned_qty: 120, actual_qty: 110, completion_rate: 0.92}],
	delayed_suppliers: [{supplier_name: "供应商甲", delayed_order_count: 4, average_delay_days: 8, risk_level: "Medium Risk"}],
	high_tech: {high_tech_revenue: metric(20000, "Currency", 30000), total_revenue: metric(100000, "Currency"), high_tech_ratio: metric(0.2, "Percent", 0.25), rd_project_count: metric(11), rd_expense_amount: metric(5000, "Currency"), rd_expense_ratio: metric(0.05, "Percent")},
	high_tech_trend: [{year: 2024, high_tech_revenue: 12000, total_revenue: 70000, high_tech_ratio: 12000 / 70000}, {year: 2025, high_tech_revenue: 16000, total_revenue: 85000, high_tech_ratio: 16000 / 85000}, {year: 2026, high_tech_revenue: 20000, total_revenue: 100000, high_tech_ratio: 0.2}],
	high_tech_projects: [{project_name: "研发项目甲", high_tech_revenue: 2500, ratio: 0.125}],
};

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { margin: 0; font-family: Arial, sans-serif; background: #f8fafc; }
.page-head { padding: 12px 16px; background: #fff; border-bottom: 1px solid #ddd; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; }
.toolbar label { display: grid; gap: 3px; font-size: 12px; }
.toolbar input, .toolbar select { min-height: 28px; padding: 3px 6px; }
.chart-container { min-height: 120px; }
.chart-container svg { width: 220px; height: 120px; }
</style></head><body><div id="app"></div>
<script>${jqueryJs}</script>
<script>
window.__ = (value) => value;
window.__calls = [];
window.__routes = [];
window.__exportPayload = null;
window.__payload = ${JSON.stringify(payload)};
window.frappe = {
  pages: {"operations-kpi-dashboard": {}},
  defaults: {get_user_default: () => "示例公司"},
  datetime: {year_start: () => "2026-01-01", get_today: () => "2026-08-22"},
  request: {url: "/api/method"},
  utils: {escape_html: (value) => String(value ?? "").replace(/[&<>\"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","'":"&#39;"}[c])),},
  msgprint: (message) => { window.__msgprint = message; },
  set_route: (...route) => { window.__routes.push(route); },
  call: (options) => {
    window.__calls.push(options);
    setTimeout(() => options.callback?.({message: structuredClone(window.__payload)}), 0);
  },
  ui: {make_app_page: ({parent, title}) => {
    const $root = $(parent); const $main = $("<main class='page-main'></main>").appendTo($root);
    const $head = $("<div class='page-head'></div>").prependTo($root); const $toolbar = $("<div class='toolbar'></div>").appendTo($head);
    const page = {main: $main, fields: {}, add_field: (definition) => {
      const $label = $("<label></label>").appendTo($toolbar).append(document.createTextNode(definition.label));
      const $control = definition.fieldtype === "Select" ? $("<select></select>") : $("<input>");
      $control.attr("data-fieldname", definition.fieldname);
      if (definition.fieldtype === "Select") definition.options.split("\\n").forEach((option) => $("<option></option>").val(option).text(option).appendTo($control));
      $control.val(definition.default ?? "").appendTo($label);
      const field = {get_value: () => $control.val(), set_value: (value) => {$control.val(value);}, $input: $control, trigger_change: () => $control.trigger("change")};
      $control.on("change", () => definition.change?.()); page.fields[definition.fieldname] = field; return field;
    }, set_primary_action: (label, handler) => $("<button data-action='refresh'></button>").text(label).on("click", handler).appendTo($toolbar), set_secondary_action: (label, handler) => $("<button data-action='export'></button>").text(label).on("click", handler).appendTo($toolbar)};
    window.__page = page; return page;
  },},
  Chart: class { constructor(parent, options) { const $parent = $(parent); $("<div class='chart-container'><svg viewBox='0 0 220 120' aria-label='chart'><rect x='8' y='8' width='180' height='80' fill='#2490ef'></rect></svg></div>").appendTo($parent); window.__charts = (window.__charts || 0) + 1; } },
};
window.open_url_post = (_url, payload) => { window.__exportPayload = payload; };
function format_number(value, _d, precision = 2) { return Number(value ?? 0).toFixed(precision); }
function format_currency(value) { return "CNY " + Number(value ?? 0).toFixed(2); }
</script>
<script>${dashboardJs}</script>
<script>frappe.pages["operations-kpi-dashboard"].on_page_load(document.querySelector("#app"));</script>
</body></html>`;

const server = http.createServer((request, response) => {
	if (request.url === "/") {
		response.writeHead(200, {"content-type": "text/html; charset=utf-8"});
		response.end(html);
		return;
	}
	response.writeHead(404);
	response.end("not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
const results = [];
const record = (name, details) => results.push({name, status: "passed", details});

try {
	const page = await browser.newPage({viewport: {width: 1440, height: 1000}, deviceScaleFactor: 1});
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	await page.waitForSelector(".kpi-section");
	await page.waitForTimeout(30);

	const sectionTitles = await page.locator(".kpi-section h4").allTextContents();
	for (const title of ["Sales Overview", "Order Fulfillment", "Collection and Receivables", "Salesperson Performance", "Year-over-year Indicators", "Reconciliation Warning", "Receivable Core Control Indicators", "Production and Purchasing Operations", "High-tech Compliance"]) assert.ok(sectionTitles.includes(title), `missing section: ${title}`);
	record("九个看板分区渲染", "销售、交付、应收、业务员、同比、对账、运营和高新合规区域均存在");

	const fulfillmentText = await page.locator(".kpi-section").filter({hasText: "Order Fulfillment"}).innerText();
	assert.match(fulfillmentText, /Final Completed Orders[\s\S]*126/);
	assert.match(fulfillmentText, /Fully Delivered Orders[\s\S]*180/);
	assert.match(fulfillmentText, /Delivered Orders[\s\S]*237/);
	record("交付与收款语义区分", "最终完成 126、全部交货 180 与至少有交货 237 分开显示");

	const ratioText = await page.locator("body").innerText();
	assert.match(ratioText, /研发项目甲/);
	assert.match(ratioText, /12\.5%/);
	assert.match(ratioText, /Receivable Turnover Days/);
	assert.match(ratioText, /计划生产数量[\s\S]*100/);
	assert.match(ratioText, /实际生产数量[\s\S]*90/);
	assert.match(ratioText, /HIGH-TECH REVENUE RATIO/);
	assert.match(ratioText, /RATIO[\s\S]*50\.0%/);
	assert.match(ratioText, /20\.0%/);
	record("完整字段展示", "应收周转天数、账龄占比、生产计划/实际产量和高新趋势占比均可见");
	const layout = await page.evaluate(() => {
		const cards = [...document.querySelectorAll('.kpi-section:nth-child(2) .kpi-card')].map(el => el.getBoundingClientRect());
		const charts = [...document.querySelectorAll('.kpi-overview-grid > *')].map(el => el.getBoundingClientRect());
		return { cards: cards.map(r => ({top:r.top,width:r.width})), charts: charts.map(r => ({top:r.top,width:r.width})), overflow:document.documentElement.scrollWidth > innerWidth };
	});
	assert.equal(layout.cards.length, 4);
	assert.ok(layout.cards.every(r => Math.abs(r.top-layout.cards[0].top)<1));
	assert.ok(layout.cards.every(r => Math.abs(r.width-layout.cards[0].width)<2));
	assert.equal(layout.charts[0].top, layout.charts[1].top);
	assert.equal(layout.overflow, false);
	record("紧凑桌面网格", "四张等宽指标卡同排，图表并排，页面无横向溢出");

	assert.equal(await page.locator(".kpi-card.kpi-clickable").count() > 0, true);
	const receiptCard = page.locator(".kpi-card").filter({hasText: "Collection Amount"});
	assert.equal(await receiptCard.evaluate((element) => element.classList.contains("kpi-clickable")), false);
	await page.locator(".kpi-card").filter({hasText: "Total Sales Amount"}).click();
	assert.deepEqual(await page.evaluate(() => window.__routes.at(-1)), ["query-report", "Sales Order List"]);
	record("下钻权限保护", "允许的销售卡可下钻，未授权的收款卡没有可点击样式");

	const callsBefore = await page.evaluate(() => window.__calls.length);
	await page.locator("select[data-fieldname='salesperson_limit']").selectOption("All");
	await page.waitForTimeout(50);
	const lastCall = await page.evaluate(() => window.__calls.at(-1));
	assert.equal(lastCall.args.filters.salesperson_limit, "all");
	record("Top10/全部切换", `切换后 API 发送 salesperson_limit=all（调用数 ${callsBefore} -> ${await page.evaluate(() => window.__calls.length)}）`);

	await page.locator("select[data-fieldname='dashboard']").selectOption("销售整体指标");
	await page.waitForTimeout(50);
	const salesDashboardCall = await page.evaluate(() => window.__calls.at(-1));
	assert.equal("sales_person" in salesDashboardCall.args.filters, false);
	assert.deepEqual(await page.locator(".kpi-section h4").allTextContents(), ["Sales Overview"]);
	record("看板分区切换", "选择销售整体指标后仅显示销售分区，API 不携带 sales_person");

	await page.locator("select[data-fieldname='dashboard']").selectOption("订单完成状态");
	await page.waitForTimeout(50);
	assert.deepEqual(await page.locator(".kpi-section h4").allTextContents(), ["Order Fulfillment"]);

	await page.locator("select[data-fieldname='dashboard']").selectOption("全部看板");
	await page.waitForTimeout(50);
	assert.equal(await page.locator(".kpi-section h4").count(), 9);

	await page.locator("button[data-action='export']").click();
	assert.equal(await page.evaluate(() => window.__exportPayload.cmd), "client_akivision.client_akivision.api.operations_kpi_export.export_kpi_dashboard");
	record("Excel 导出入口", "导出命令携带当前筛选条件");

	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_kpi_dashboard_desktop.png", fullPage: true});

	await page.setViewportSize({width: 390, height: 844});
	await page.waitForTimeout(50);
	const mobileLayout = await page.evaluate(() => ({scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth, charts: document.querySelectorAll(".chart-container svg").length, sections: document.querySelectorAll(".kpi-section").length}));
	assert.ok(mobileLayout.scrollWidth <= mobileLayout.clientWidth + 1, `horizontal overflow: ${JSON.stringify(mobileLayout)}`);
	assert.ok(mobileLayout.charts >= 3, `charts missing: ${JSON.stringify(mobileLayout)}`);
	assert.equal(mobileLayout.sections >= 9, true);
	record("移动端布局", `390px 视口无横向溢出，图表 ${mobileLayout.charts} 个，分区 ${mobileLayout.sections} 个`);
	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_kpi_dashboard_mobile.png", fullPage: true});

	await page.evaluate(() => { window.__page.fields.from_date.set_value("2026-12-01"); window.__page.fields.from_date.trigger_change(); });
	await page.waitForSelector(".kpi-error-state");
	assert.match(await page.locator(".kpi-error-state").innerText(), /From Date cannot be later than To Date/);
	assert.equal(await page.locator(".kpi-retry").count(), 1);
	record("日期错误与重试", "开始日期晚于截止日期时显示明确错误和 Retry 操作");

	const result = {tested_at: new Date().toISOString(), browser: "Chromium", base_url: `http://127.0.0.1:${port}/`, results, limitations: ["使用模拟 frappe.call 数据，未替代真实登录站点、权限矩阵和 MariaDB SQL 验证", "真实环境需复测财务收入来源、应收周转天数口径和销售团队分摊"]};
	await fs.writeFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_kpi_dashboard_result.json", JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
	await new Promise((resolve) => server.close(resolve));
}
