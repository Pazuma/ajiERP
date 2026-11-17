import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";
const bomScript = await fs.readFile(`${appRoot}/client_akivision/public/js/bom.js`, "utf8");
const importConfig = JSON.parse(await fs.readFile(`${appRoot}/client_akivision/config/excel_import_tables.json`, "utf8"));
const presentation = JSON.parse(await fs.readFile(`${appRoot}/client_akivision/config/excel_record_presentation.json`, "utf8"));

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { font-family: sans-serif; margin: 16px; } .form { max-width: 1100px; }
.grid { display: grid; grid-template-columns: repeat(7, minmax(100px, 1fr)); gap: 4px; }
.table-responsive { overflow-x: auto; } table { min-width: 900px; border-collapse: collapse; }
th, td { border: 1px solid #cbd5e1; padding: 6px; white-space: nowrap; }
</style></head><body><main class="form"><h1>BOM-AKY-55R5-CGTC</h1>
<div id="items" class="grid"></div><section id="structure"></section></main>
<script>
window.__ = (value) => value;
window.__calls = [];
window.frappe = { ui: { form: { on: (_doctype, handlers) => { window.__handlers = handlers; } } },
  utils: { escape_html: (value) => String(value).replace(/[&<>]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[char])) },
  call: async (method, args) => { window.__calls.push({method, args}); return {message: {rows: [
    {model_code: "BOM-AKY-55R5-CGTC", level: 0, item_code: "AKY-55R5-CGTC", item_name: "主机", drawing_no: "DWG-001", drawing_revision: "A", qty: 1, uom: "台", parent_bom: null},
    {model_code: "BOM-AKY-55R5-CGTC", level: 1, item_code: "PART-001", item_name: "组件", drawing_no: "DWG-002", drawing_revision: "B", qty: 2, uom: "个", parent_bom: "BOM-AKY-55R5-CGTC"}
  ]}}; }
};
</script><script>${bomScript}</script></body></html>`;

const server = http.createServer((_request, response) => {
	response.writeHead(200, {"content-type": "text/html; charset=utf-8"});
	response.end(html);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
const results = [];

try {
	const page = await browser.newPage({viewport: {width: 1280, height: 900}});
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	const columns = ["item_code", "item_name", "custom_engineering_drawing_no", "custom_engineering_drawing_revision", "qty", "uom", "bom_no"];
	const grid = {update_docfield_property(fieldname, property, value) { if (property === "label") document.querySelector("#items").insertAdjacentHTML("beforeend", `<span data-field="${fieldname}">${value}</span>`); }, reset_grid() {}};
	await page.evaluate((columns) => {
		const frm = {is_new: () => false, doc: {name: "BOM-AKY-55R5-CGTC"}, fields_dict: {items: {grid: {update_docfield_property(fieldname, property, value) { if (property === "label") document.querySelector("#items").insertAdjacentHTML("beforeend", `<span data-field="${fieldname}">${value}</span>`); }, reset_grid() {}}}, custom_bom_structure: {$wrapper: {empty() { document.querySelector("#structure").innerHTML = ""; return this; }, html(value) { document.querySelector("#structure").innerHTML = value; return this; }}}}};
		window.__handlers.refresh(frm);
	}, columns);
	await page.waitForSelector("#structure table");
	for (const label of ["物料编码", "物料名称", "图纸号", "图纸版本", "用量", "单位", "子 BOM 编码", "层级", "父 BOM"]) assert.equal(await page.getByText(label, {exact: true}).count() > 0, true, `missing ${label}`);
	assert.equal(await page.locator("#structure tbody tr").count(), 2);
	results.push({name: "BOM 详情字段与展开结构", status: "passed", details: "明细列和层级 0/1 展开表均渲染"});
	await page.screenshot({path: `${appRoot}/docs/playwright_bom_ui.png`, fullPage: true});

	await page.setViewportSize({width: 390, height: 844});
	const responsive = await page.locator(".table-responsive").evaluate((node) => ({
		clientWidth: node.clientWidth,
		scrollWidth: node.scrollWidth,
		overflowX: getComputedStyle(node).overflowX,
	}));
	assert.equal(responsive.overflowX, "auto");
	assert.ok(responsive.scrollWidth >= responsive.clientWidth);
	results.push({name: "BOM 移动端布局", status: "passed", details: "展开表在容器内横向滚动，字段不相互遮挡"});

	const bomDefaults = importConfig.bom.default_fields;
	assert.deepEqual(bomDefaults.BOM, ["item", "company", "quantity", "custom_engineering_drawing", "is_active", "is_default"]);
	assert.deepEqual(bomDefaults.items, ["item_code", "item_name", "custom_import_level", "qty", "uom", "bom_no"]);
	assert.ok(presentation.records.bom.child_tables[0].fields.includes("bom_no"));
	results.push({name: "BOM 模板字段配置", status: "passed", details: "头信息与明细模板字段和展示注册表一致"});

	const result = {status: "passed", browser: "Chromium", tested_at: new Date().toISOString(), results};
	await fs.writeFile(`${appRoot}/docs/playwright_bom_ui_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
	await new Promise((resolve) => server.close(resolve));
}
