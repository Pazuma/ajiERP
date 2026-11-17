import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";
const script = await fs.readFile(`${appRoot}/client_akivision/public/js/inline_data_import.js`, "utf8");
const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { font-family: sans-serif; margin: 16px; } .modal { max-width: 1100px; margin: auto; } .hidden { display: none; }
.table-responsive { overflow-x: auto; } .client-flat-bom-preview table { min-width: 980px; border-collapse: collapse; } .client-flat-bom-summary { display: flex; flex-wrap: wrap; gap: 8px 20px; }
@media (max-width: 640px) { .client-flat-bom-summary { display: grid; grid-template-columns: 1fr; gap: 6px; } }
th, td { border: 1px solid #cbd5e1; padding: 6px; white-space: nowrap; } .alert { padding: 10px; }
</style></head><body><div id="root"></div><script>
const wrap = (node) => ({
  el: node, empty() { node.innerHTML = ""; return this; }, html(value) { node.innerHTML = value; return this; },
  prepend(value) { node.insertAdjacentHTML("afterbegin", value); return this; }, addClass(name) { node.classList.add(...name.split(" ")); return this; },
  toggle(visible) { node.hidden = !visible; return this; },
  find(selector) { const result = { each: (cb) => node.querySelectorAll(selector).forEach((item, i) => cb(i, item)), prop: (_name, value) => { node.querySelectorAll(selector).forEach((item) => item.checked = value); return result; }, text: (value) => { const item = node.querySelector(selector); if (item) item.textContent = value; return result; }, on: (eventName, delegatedSelector, callback) => { const type = String(eventName).split(".")[0]; const handler = typeof delegatedSelector === "string" ? callback : delegatedSelector; node.addEventListener(type, (event) => { const target = typeof delegatedSelector === "string" ? event.target.closest(delegatedSelector) : event.target; if (!target || !node.contains(target)) return; handler.call(target, event); }); return result; }, off: () => result }; return result; },
});
const translate = (value, args) => args ? value.replace(/\\{(\\d+)\\}/g, (_, i) => args[i] ?? "") : value;
window.__ = translate; window.open_url_post = () => {};
window.flat_warning = false;
window.frappe = {
  views: { ListView: class { get_menu_items() { return [{label: "Import", standard: true}]; } } },
  get_meta: () => ({is_submittable: false}),
  utils: {escape_html: (value) => String(value).replace(/[&<>]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[char]))},
  require: (_bundle, callback) => callback(), msgprint: () => {},
  call: async (request) => {
    const method = request.method;
    if (method.endsWith("create_inline_import")) return {message: {name: "BOM Import Test"}};
    if (method.endsWith("preview_inline_import")) return {message: {custom_mode: "bom_flattened", summary: {root: "AKY-55R5-CGTC", company: "Test Company", quantity: 1, components: 40}, columns: [{header_title: "Excel 行号"}, {header_title: "型号"}, {header_title: "层级"}, {header_title: "物料名称"}, {header_title: "图纸号"}, {header_title: "用量"}, {header_title: "匹配物料编码"}, {header_title: "单位"}, {header_title: "匹配状态"}], data: [[2, "AKY-55R5-CGTC", 0, "1141", "1141101100-v0", 1, "AKY-55R5-CGTC", "Pcs", "已匹配"], [3, "AKY-55R5-CGTC", 1, "PE袋270x180x0.08", "1007209102-v0", 1, "1007209102-v0", "Pcs", "已匹配"]], warnings: window.flat_warning ? [{type: "error", message: "第 3 行无法唯一匹配物料"}] : [], import_log: []}};
    if (method.endsWith("get_import_tables")) return {message: [{sheet_id: "bom", table_label: "BOM表", doctype: "BOM", importable: true}]};
    if (method.endsWith("get_import_fields")) return {message: []};
    if (method.endsWith("start_inline_import")) return {message: {queued: false}};
    if (method.endsWith("get_inline_import_status")) return {message: {status: "Success", total: 1, success: 1, failed: 0}};
    throw new Error("Unexpected method: " + method);
  },
  ui: { Dialog: class {
    constructor(options) { this.options = options; this.fields_dict = {}; this.$wrapper = wrap(document.createElement("div")); this.$wrapper.el.className = "modal hidden"; this.$wrapper.el.innerHTML = "<h2>" + options.title + "</h2><div data-field='body'></div>"; document.body.appendChild(this.$wrapper.el); for (const field of options.fields || []) { const node = document.createElement("div"); node.dataset.fieldname = field.fieldname; const control = {df: field, value: field.default ?? "", $wrapper: wrap(node), $input: wrap(node), get_value() {return this.value;}, set_value(value) {this.value = value; field.onchange?.call(this);}, refresh() {}}; this.fields_dict[field.fieldname] = control; this.$wrapper.el.querySelector("[data-field=body]").appendChild(node); } this.primary_action = options.primary_action; }
    get_values() { return Object.fromEntries(Object.entries(this.fields_dict).map(([key, field]) => [key, field.value])); }
    get_value(name) { return this.fields_dict[name]?.value || ""; } set_value(name, value) { this.fields_dict[name]?.set_value(value); }
    set_df_property(name, property, value) { if (this.fields_dict[name]) this.fields_dict[name].df[property] = value; }
    show() { this.$wrapper.el.classList.remove("hidden"); } hide() { this.$wrapper.el.classList.add("hidden"); this.onhide?.(); }
    disable_primary_action() { this.disabled = true; } enable_primary_action() { this.disabled = false; }
    set_primary_action(label, action) { this.primary_action = action; this.primary_label = label; }
  }},
};
window.frappe.model = {with_doctype: (_doctype, callback) => callback()};
</script><script>${script}</script><script>window.list = new frappe.views.ListView(); window.list.doctype = "BOM"; window.list.get_menu_items()[0].action();</script></body></html>`;

const server = http.createServer((_request, response) => { response.writeHead(200, {"content-type": "text/html; charset=utf-8"}); response.end(html); });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
const page = await browser.newPage({viewport: {width: 390, height: 844}});
const results = [];
try {
  await page.goto(`http://127.0.0.1:${server.address().port}/`, {waitUntil: "load"});
  await page.waitForTimeout(100);
  assert.match(await page.locator(".modal").innerText(), /使用展开表直接导入/);
  await page.getByRole("button", {name: "使用展开表直接导入"}).click();
  await page.evaluate(() => window.client_akivision.inline_import_dialog.fields_dict.flat_company.set_value("Test Company"));
  await page.evaluate(() => window.client_akivision.inline_import_dialog.fields_dict.import_file.set_value("/private/files/BOM表.xlsx"));
  await page.waitForTimeout(100);
  assert.match(await page.locator(".modal").innerText(), /匹配物料编码/);
  assert.match(await page.locator(".modal").innerText(), /已识别 1 张 BOM 和 40 条直接组件/);
  assert.equal(await page.locator(".client-flat-bom-preview tbody tr").count(), 2);
  const table = await page.locator(".client-flat-bom-preview").evaluate((node) => ({overflow: getComputedStyle(node).overflowX, scrollWidth: node.scrollWidth, clientWidth: node.clientWidth}));
  assert.equal(table.overflow, "auto");
  assert.ok(table.scrollWidth >= table.clientWidth);
  results.push({name: "五列表 BOM 直接导入预览", status: "passed", details: "识别 1 张 BOM、40 条组件并展示匹配编码和单位"});
  await page.evaluate(() => window.client_akivision.inline_import_dialog.primary_action());
  await page.waitForTimeout(1700);
  assert.match(await page.locator(".modal").innerText(), /导入完成/);
  results.push({name: "直接导入启动反馈", status: "passed", details: "预览通过后可启动任务并显示完成状态"});
  await page.evaluate(() => { window.flat_warning = true; window.client_akivision.inline_import_dialog.fields_dict.import_file.set_value("/private/files/BOM表-问题.xlsx"); });
  await page.waitForTimeout(100);
  assert.match(await page.locator(".modal").innerText(), /第 3 行无法唯一匹配物料/);
  assert.equal(await page.evaluate(() => window.client_akivision.inline_import_dialog.disabled), true);
  results.push({name: "阻断警告与问题记录", status: "passed", details: "匹配失败行显示具体错误并阻止启动"});
  await page.screenshot({path: `${appRoot}/docs/playwright_flat_bom_import_ui.png`, fullPage: true});
  const output = {status: "passed", browser: "Chromium", tested_at: new Date().toISOString(), results};
  await fs.writeFile(`${appRoot}/docs/playwright_flat_bom_import_ui_result.json`, JSON.stringify(output, null, 2) + "\n");
  console.log(JSON.stringify(output, null, 2));
} finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
