import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const script = await fs.readFile(
	"/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/js/inline_data_import.js",
	"utf8"
);

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { font-family: sans-serif; margin: 24px; }
.modal { border: 1px solid #d1d5db; padding: 16px; max-width: 900px; }
.hidden { display: none; }
.status { padding: 8px; background: #eef6ff; }
.preview { min-height: 80px; border: 1px solid #d1d5db; padding: 12px; }
</style></head><body><div id="route">/app/Customer</div><div id="list"></div>
<script>
const wrap = (node) => ({
  el: node,
  empty() { node.innerHTML = ""; return this; },
  html(value) { node.innerHTML = value; return this; },
  append(value) { node.insertAdjacentHTML("beforeend", value); return this; },
  prepend(value) { node.insertAdjacentHTML("afterbegin", value); return this; },
  addClass(name) { node.classList.add(...name.split(" ")); return this; },
  toggle(visible) { node.hidden = !visible; return this; },
  find(selector) { const result = {each: (callback) => node.querySelectorAll(selector).forEach((item, index) => callback(index, item)), prop: (_name, value) => { node.querySelectorAll(selector).forEach((item) => { item.checked = value; }); return result; }, length: node.querySelectorAll(selector).length, text: (value) => { const item = node.querySelector(selector); if (item) item.textContent = value; return result; }, on: (eventName, delegatedSelector, callback) => { const eventType = String(eventName).split(".")[0]; const isDelegated = typeof delegatedSelector === "string"; const handler = isDelegated ? callback : delegatedSelector; if (!handler) return result; if (isDelegated) { node.addEventListener(eventType, (event) => { const target = event.target.closest(delegatedSelector); if (!target || !node.contains(target)) return; handler.call(target, event); }); } else { node.querySelectorAll(selector).forEach((item) => item.addEventListener(eventType, (event) => handler.call(item, event))); } return result; }, off: () => result}; return result; },
  off() { return this; },
  on() { return this; },
});
const translate = (value, args) => args ? value.replace(/\\{(\\d+)\\}/g, (_, i) => args[i] ?? "") : value;
window.__ = translate;
window.open_url_post = () => { window.template_posted = true; };
window.frappe = {
  views: { ListView: class { constructor() { this.doctype = "Customer"; this.refreshed = false; } refresh() { this.refreshed = true; } get_menu_items() { return [{label: "Import", standard: true, action: () => { window.route_changed = true; }}]; } } },
  get_meta: () => ({is_submittable: false}),
  utils: {escape_html: (value) => String(value).replace(/[&<>]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[char]))},
  require: (_bundle, callback) => callback(),
  msgprint: () => {},
  call: async (request) => {
    const method = request.method;
    if (method.endsWith("create_inline_import")) return {message: {name: "Customer Import on Test"}};
    if (method.endsWith("preview_inline_import") || method.endsWith("update_inline_import_template_options")) return {message: {data: [["CUST-001", "Acme"]], columns: [], warnings: [], import_log: []}};
    if (method.endsWith("start_inline_import")) return {message: {queued: true}};
    if (method.endsWith("get_inline_import_status")) return {message: {status: "Success", total: 1, success: 1, failed: 0}};
    if (method.endsWith("get_import_tables")) return {message: [{sheet_id: "customer_list", table_label: "客户清单", doctype: "Customer", importable: true}]};
    if (method.endsWith("get_import_fields")) return {message: [{key: "Customer", label: "客户", doctype: "Customer", fields: [{fieldname: "customer_name", label: "客户名称", writable: true, default_selected: true}, {fieldname: "customer_group", label: "客户组", writable: true, default_selected: false}]}]};
    if (method.endsWith("validate_import_context")) return {message: {doctype: "Customer", fields: {Customer: ["customer_name"]}}};
    throw new Error("Unexpected method: " + method);
  },
  ui: {
    Dialog: class {
      constructor(options) {
        this.options = options;
        this.fields_dict = {};
        this.$wrapper = wrap(document.createElement("div"));
        this.$wrapper.el.className = "modal hidden";
        this.$wrapper.el.innerHTML = "<h2>" + options.title + "</h2><div data-field='body'></div>";
        document.body.appendChild(this.$wrapper.el);
        for (const field of options.fields || []) {
          const node = document.createElement("div");
          node.dataset.fieldname = field.fieldname;
          const control = {
            df: field,
            value: field.default ?? "",
            $wrapper: wrap(node),
            $input: wrap(node),
            get_value() { return this.value; },
            set_value(value) { this.value = value; field.onchange?.call(this); },
          };
          this.fields_dict[field.fieldname] = control;
          this.$wrapper.el.querySelector("[data-field=body]").appendChild(node);
        }
        this.standard_actions = { find: () => ({}) };
        this.primary_action = options.primary_action;
        this.primary_label = options.primary_action_label;
      }
      get_values() { return Object.fromEntries(Object.entries(this.fields_dict).map(([key, field]) => [key, field.value])); }
      get_value(fieldname) { return this.fields_dict[fieldname]?.value || ""; }
      set_value(fieldname, value) { if (this.fields_dict[fieldname]) this.fields_dict[fieldname].set_value(value); }
      set_df_property(fieldname, property, value) { if (this.fields_dict[fieldname]) this.fields_dict[fieldname].df[property] = value; }
      show() { this.$wrapper.el.classList.remove("hidden"); }
      hide() { this.$wrapper.el.classList.add("hidden"); this.onhide?.(); }
      disable_primary_action() { this.disabled = true; }
      enable_primary_action() { this.disabled = false; }
      set_primary_action(label, action) { this.primary_label = label; this.primary_action = action; }
      set_secondary_action() {}
    },
  },
  model: {with_doctype: (_doctype, callback) => callback()},
  data_import: {
    ImportPreview: class { constructor({wrapper, preview_data}) { wrapper.html("<div class='preview'>预览行：" + preview_data.data.length + "</div>"); } },
    DataExporter: class { constructor() { window.template_downloaded = true; } },
  },
};
</script><script>${script}</script><script>window.list = new frappe.views.ListView(); window.menu = window.list.get_menu_items();</script></body></html>`;

const server = http.createServer((request, response) => {
	response.writeHead(request.url === "/" ? 200 : 404, {"content-type": "text/html; charset=utf-8"});
	response.end(request.url === "/" ? html : "not found");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({viewport: {width: 390, height: 844}});
page.on("pageerror", (error) => console.error("PAGEERROR", error.message));
page.on("console", (message) => console.error("CONSOLE", message.text()));
const results = [];

try {
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	await page.evaluate(() => window.menu.find((item) => item.label === "Import").action());
	assert.equal(await page.locator(".modal").count(), 1);
	assert.equal(await page.locator(".modal").evaluate((node) => node.classList.contains("hidden")), false);
	assert.equal(await page.evaluate(() => window.route_changed || false), false);
	results.push({name: "导入入口弹窗化", status: "passed", details: "列表导入菜单打开弹窗且未改变路由"});
	await page.waitForTimeout(100);
	assert.match(await page.locator(".modal").innerText(), /下载推荐模板/);
	assert.doesNotMatch(await page.locator(".modal").innerText(), /客户名称/);
	await page.getByRole("button", {name: "下载推荐模板"}).click();
	await page.waitForTimeout(50);
	assert.equal(await page.evaluate(() => window.template_posted || false), true);
	await page.getByRole("button", {name: "高级设置"}).click();
	assert.match(await page.locator(".modal").innerText(), /客户名称/);
	assert.equal(await page.locator('input[data-fieldname="customer_name"]').count(), 1);
	results.push({name: "简化默认路径与高级字段选择", status: "passed", details: "默认只显示推荐模板和上传入口，展开高级设置后展示字段选择"});

	const dialogState = await page.evaluate(async () => {
		const fileField = document.querySelector('[data-fieldname="import_file"]');
		const active = document.querySelector(".modal");
		return {fileField: Boolean(fileField), active: Boolean(active)};
	});
	assert.equal(dialogState.fileField, true);
	await page.evaluate(() => {
		window.client_akivision.inline_import_dialog.fields_dict.import_file.set_value("/private/files/customer.xlsx");
	});
	await page.waitForTimeout(100);
	assert.match(await page.locator(".modal").innerText(), /预览行/);
	results.push({name: "上传与预览", status: "passed", details: "上传文件后在弹窗内展示预览"});
	await page.evaluate(() => window.client_akivision.inline_import_dialog.primary_action());
	await page.waitForTimeout(1700);
	assert.match(await page.locator(".modal").innerText(), /导入完成/);
	results.push({name: "后台导入反馈", status: "passed", details: "弹窗启动标准导入任务并显示完成状态"});
	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_inline_data_import.png", fullPage: true});
	await fs.writeFile(
		"/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_inline_data_import_result.json",
		JSON.stringify({tested_at: new Date().toISOString(), browser: "Chromium", results}, null, 2) + "\n"
	);

	await browser.close();
	await new Promise((resolve) => server.close(resolve));
	console.log(JSON.stringify({status: "passed", results}, null, 2));
} catch (error) {
	await browser.close();
	await new Promise((resolve) => server.close(resolve));
	throw error;
}
