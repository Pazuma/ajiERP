import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const config = JSON.parse(await fs.readFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/config/other_forms_sidebar.json", "utf8"));
const moduleItems = {
	Selling: [
		{type: "Link", link_type: "DocType", link_to: "Customer", label: "客户"},
		{type: "Link", link_type: "DocType", link_to: "Quotation", label: "报价单"},
		{type: "Link", link_type: "DocType", link_to: "Sales Order", label: "销售订单"},
		{type: "Link", link_type: "DocType", link_to: "Delivery Note", label: "送货单"},
		{type: "Link", link_type: "DocType", link_to: "Sales Invoice", label: "销售发票"},
		{type: "Link", link_type: "DocType", link_to: "Item Price", label: "物料价格"},
		{type: "Section Break", label: "Main", links: []},
		{type: "Link", link_type: "DocType", link_to: "Blanket Order", label: "Blanket Order"},
		{type: "Link", link_type: "DocType", link_to: "Sales Partner", label: "Sales Partner"},
		{type: "Section Break", label: "Reports", links: ["Sales Order Analysis"]},
	],
	Buying: [
		{type: "Link", link_type: "DocType", link_to: "Supplier", label: "供应商"},
		{type: "Link", link_type: "DocType", link_to: "Material Request", label: "采购申请"},
		{type: "Link", link_type: "DocType", link_to: "Request for Quotation", label: "询价单"},
		{type: "Link", link_type: "DocType", link_to: "Supplier Quotation", label: "供应商报价"},
		{type: "Link", link_type: "DocType", link_to: "Purchase Order", label: "采购订单"},
		{type: "Link", link_type: "DocType", link_to: "Purchase Receipt", label: "采购收货"},
		{type: "Link", link_type: "DocType", link_to: "Purchase Invoice", label: "采购发票"},
		{type: "Section Break", label: "Main", links: []},
		{type: "Link", link_type: "DocType", link_to: "Purchase Comparison", label: "Purchase Comparison"},
		{type: "Section Break", label: "Reports", links: ["Purchase List"]},
	],
	Stock: [
		{type: "Link", link_type: "DocType", link_to: "Item", label: "物料"},
		{type: "Link", link_type: "DocType", link_to: "Item Group", label: "物料组"},
		{type: "Link", link_type: "DocType", link_to: "Warehouse", label: "仓库"},
		{type: "Link", link_type: "DocType", link_to: "UOM", label: "单位"},
		{type: "Link", link_type: "DocType", link_to: "Stock Entry", label: "库存凭证"},
		{type: "Link", link_type: "DocType", link_to: "Purchase Receipt", label: "采购入库"},
		{type: "Link", link_type: "DocType", link_to: "Delivery Note", label: "销售出库"},
		{type: "Section Break", label: "Items", links: []},
		{type: "Link", link_type: "DocType", link_to: "Product Bundle", label: "Product Bundle"},
		{type: "Section Break", label: "Reports", links: ["Realtime Inventory"]},
	],
	"KPI Dashboard": [
		{type: "Link", link_type: "Page", link_to: "operations-kpi-dashboard", label: "运营指标看板"},
		{type: "Section Break", label: "设置", links: ["KPI Target", "KPI Metric Definition"]},
		{type: "Link", link_type: "DocType", link_to: "Aging Period Rule", label: "账龄区间规则"},
	],
};

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { margin: 0; font-family: Arial, sans-serif; background: #f8fafc; }
.layout { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }
.sidebar { padding: 22px 16px; background: #fff; border-right: 1px solid #dbe3ed; }
.module { margin-bottom: 20px; }
.module h2 { margin: 0 0 10px; font-size: 16px; }
.section { margin: 12px 0 5px; color: #64748b; font-size: 12px; font-weight: 700; }
.link { display: block; padding: 7px 8px; color: #1e293b; text-decoration: none; }
.link:hover { background: #eff6ff; }
.other-forms { border-left: 3px solid #2490ef; padding-left: 8px; }
.main { padding: 32px; }
@media (max-width: 640px) { .layout { grid-template-columns: 1fr; } .sidebar { border-right: 0; border-bottom: 1px solid #dbe3ed; } .main { padding: 20px 16px; } }
</style></head><body><div class="layout"><aside class="sidebar" id="sidebar"></aside><main class="main"><h1>工作区预览</h1><p>只展示导航分组，不改变表单、权限和业务数据。</p></main></div>
<script>
window.__config = ${JSON.stringify(config)};
window.__items = ${JSON.stringify(moduleItems)};
function renderModule(name, items) {
  const root = document.createElement("section"); root.className = "module";
  root.innerHTML = "<h2>" + name + "</h2>";
  const configured = new Set((window.__config[name]?.links || []).map((row) => row.link_type + "::" + row.link_to));
  const expanded = items.flatMap((item) => item.type === "Section Break" ? [{type: item.type, label: item.label}, ...item.links.map((link) => ({type: "Link", link_type: "DocType", link_to: link, label: link}))] : [item]);
  const other = expanded.filter((item) => item.type === "Link" && configured.has(item.link_type + "::" + item.link_to));
  const normal = expanded.filter((item) => !(item.type === "Link" && configured.has(item.link_type + "::" + item.link_to)));
  function appendSection(label, children) { const heading = document.createElement("div"); heading.className = "section"; heading.textContent = label; root.appendChild(heading); children.forEach((link) => { const a = document.createElement("a"); a.className = "link"; a.textContent = link.label; a.href = "/app/" + encodeURIComponent(link.link_to); root.appendChild(a); }); }
  let current = []; normal.forEach((item) => { if (item.type === "Section Break") { if (current.length) appendSection(item.previousLabel || "业务入口", current); item.previousLabel = item.label; current = []; } else if (item.type === "Link") current.push(item); }); if (current.length) appendSection("业务入口", current);
  if (other.length) { const heading = document.createElement("div"); heading.className = "section other-forms"; heading.textContent = "其他表单"; root.appendChild(heading); other.forEach((link) => { const a = document.createElement("a"); a.className = "link other-form-link"; a.textContent = link.label; a.href = "/app/" + encodeURIComponent(link.link_to); root.appendChild(a); }); }
  document.querySelector("#sidebar").appendChild(root);
}
Object.entries(window.__items).forEach(([name, items]) => renderModule(name, items));
</script></body></html>`;

const server = http.createServer((request, response) => {
	response.writeHead(request.url === "/" ? 200 : 404, {"content-type": "text/html; charset=utf-8"});
	response.end(request.url === "/" ? html : "not found");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
const results = [];
const record = (name, details) => results.push({name, status: "passed", details});

try {
	const page = await browser.newPage({viewport: {width: 1440, height: 1000}, deviceScaleFactor: 1});
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	for (const moduleName of Object.keys(moduleItems)) {
		const module = page.locator(".module").filter({hasText: moduleName});
		const headings = await module.locator(".section").allTextContents();
		assert.equal(headings.filter((label) => label === "常用表单").length, 0, `${moduleName} still has Common Forms section`);
		assert.equal(headings.filter((label) => label === "其他表单").length, 1, `${moduleName} Other Forms section is not unique`);
		const otherLinks = module.locator(".other-form-link");
		assert.ok(await otherLinks.count() > 0, `${moduleName} has no moved links`);
	}
	const sellingLinks = page.locator(".module").filter({hasText: "Selling"}).locator(".link");
	assert.equal(await sellingLinks.first().textContent(), "客户");
	assert.equal(await sellingLinks.nth(5).textContent(), "物料价格");
	assert.equal(await sellingLinks.filter({hasText: "客户"}).count(), 1);
	assert.equal(await page.locator(".module").filter({hasText: "Selling"}).locator(".other-forms").evaluate((el) => el.nextElementSibling.textContent), "Blanket Order");
	assert.equal(await page.locator(".module").filter({hasText: "Selling"}).getByRole("link", {name: "销售订单", exact: true}).count(), 1);
	assert.equal(await page.locator(".module").filter({hasText: "Selling"}).getByRole("link", {name: "Sales Order Analysis", exact: true}).count(), 1);
	record("模块分组与保留入口", "Selling/Buying/Stock/KPI Dashboard 均只有一个其他表单分组，主流程和报表仍可见");

	const allOtherLinks = await page.locator(".other-form-link").allTextContents();
	for (const expected of ["Blanket Order", "Sales Partner", "Purchase Comparison", "Product Bundle", "账龄区间规则"]) assert.ok(allOtherLinks.includes(expected), `missing moved link: ${expected}`);
	record("收纳入口完整", "配置声明的代表性低频表单均出现在其他表单分组");

	await page.setViewportSize({width: 390, height: 844});
	const mobile = await page.evaluate(() => ({scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth, sections: document.querySelectorAll(".other-forms").length}));
	assert.ok(mobile.scrollWidth <= mobile.clientWidth + 1, JSON.stringify(mobile));
	assert.equal(mobile.sections, Object.keys(moduleItems).length);
	record("移动端导航体验", "390px 视口无横向溢出，其他表单分组仍可识别");

	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_other_forms_sidebar.png", fullPage: true});
	const result = {tested_at: new Date().toISOString(), browser: "Chromium", base_url: `http://127.0.0.1:${port}/`, results, limitations: ["使用模拟 Workspace Sidebar 数据，未替代真实站点 after_migrate、角色过滤和 Frappe Desk 渲染", "配置中不存在的模块/DocType 需在真实迁移日志中确认并按警告处理"]};
	await fs.writeFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_other_forms_sidebar_result.json", JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
	await new Promise((resolve) => server.close(resolve));
}
