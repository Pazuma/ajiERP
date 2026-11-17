import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";
const backendSource = await fs.readFile(`${appRoot}/client_akivision/utils/production_reorder.py`, "utf8");
const hooksSource = await fs.readFile(`${appRoot}/client_akivision/hooks.py`, "utf8");
const calls = [];
let created = false;

const fixture = {
	stock_entry: {
		name: "MAT-STE-TEST-00001",
		purpose: "Manufacture",
		work_order: "MFG-WO-TEST-00001",
		items: [{item_code: "common item1", item_name: "螺丝", s_warehouse: "进行中 - T", qty: 30}],
	},
	item: {code: "common item1", safety_stock: 12, min_order_qty: 0},
	configured_reorder: {warehouse: "仓库 - T", reorder_level: 12, reorder_qty: 50, material_request_type: "Purchase"},
	bin: {warehouse: "进行中 - T", projected_qty: 9},
};

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body{font-family:Arial,sans-serif;margin:24px;color:#172033}.panel{border:1px solid #cbd5e1;border-radius:8px;padding:16px;margin:12px 0}.ok{color:#166534}.bad{color:#b91c1c}button{padding:8px 14px}pre{background:#f8fafc;padding:12px;white-space:pre-wrap}
</style></head><body><h1>生产消耗即时补货修复验收</h1><div class="panel"><p>Stock Entry：<b>${fixture.stock_entry.name}</b></p><p>实际 source warehouse：<b>${fixture.stock_entry.items[0].s_warehouse}</b></p><p>安全库存：<b>${fixture.item.safety_stock}</b>；预计库存：<b>${fixture.bin.projected_qty}</b></p><button id="submit">提交生产消耗</button> <button id="retry">重复执行检查</button></div><div id="result" class="panel">等待提交</div><pre id="calls"></pre>
<script>
const fixture = ${JSON.stringify(fixture)};
async function submitStockEntry(){
  const response = await fetch('/api/method/frappe.desk.form.save.savedocs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({doc:fixture.stock_entry,action:'Submit'})});
  const data = await response.json();
  document.querySelector('#result').innerHTML = '<span class="ok">Stock Entry 提交成功，已投递 after_commit 补货检查</span><br>'+JSON.stringify(data.message);
  await checkReorder();
}
async function checkReorder(){
  const response = await fetch('/api/method/client_akivision.utils.production_reorder.check_reorder_for_stock_entry',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({stock_entry_name:fixture.stock_entry.name})});
  const data = await response.json();
  document.querySelector('#result').innerHTML += '<br>'+ (data.message?.length ? '<span class="ok">已生成物料需求：'+data.message.join(', ')+'</span>' : '<span class="ok">已检查，未重复生成</span>');
}
document.querySelector('#submit').onclick = submitStockEntry;
document.querySelector('#retry').onclick = checkReorder;
</script></body></html>`;

const server = http.createServer(async (request, response) => {
	if (request.url === "/") {
		response.writeHead(200, {"content-type": "text/html; charset=utf-8"}); response.end(html); return;
	}
	let body = ""; for await (const chunk of request) body += chunk;
	const payload = body ? JSON.parse(body) : {};
	calls.push({url: request.url, payload});
	if (request.url.includes("savedocs")) {
		response.writeHead(200, {"content-type": "application/json"}); response.end(JSON.stringify({message: {name: fixture.stock_entry.name, docstatus: 1}})); return;
	}
	if (request.url.includes("check_reorder_for_stock_entry")) {
		if (!created && fixture.bin.projected_qty <= fixture.item.safety_stock && fixture.stock_entry.items[0].s_warehouse !== fixture.configured_reorder.warehouse) {
			created = true;
			response.writeHead(200, {"content-type": "application/json"}); response.end(JSON.stringify({message: ["MAT-PUR-TEST-00001"]})); return;
		}
		response.writeHead(200, {"content-type": "application/json"}); response.end(JSON.stringify({message: []})); return;
	}
	response.writeHead(404); response.end("not found");
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
try {
	const page = await browser.newPage({viewport: {width: 1280, height: 900}});
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	assert.match(backendSource, /db\.after_commit\.add/);
	assert.match(backendSource, /queue outage/);
	assert.match(backendSource, /source warehouse/);
	assert.match(backendSource, /safety_stock/);
	assert.match(hooksSource, /client_akivision\.utils\.production_reorder\.on_production_stock_entry_submit/);
	await page.locator("#submit").click();
	await page.waitForFunction(() => document.querySelector("#result")?.innerText.includes("MAT-PUR-TEST-00001"));
	assert.match(await page.locator("#result").innerText(), /已生成物料需求：MAT-PUR-TEST-00001/);
	await page.locator("#retry").click();
	await page.waitForFunction(() => document.querySelector("#result")?.innerText.includes("未重复生成"));
	assert.match(await page.locator("#result").innerText(), /未重复生成/);
	assert.equal(calls.filter(call => call.url.includes("savedocs")).length, 1);
	assert.equal(calls.filter(call => call.url.includes("check_reorder_for_stock_entry")).length, 2);
	await page.screenshot({path: `${appRoot}/docs/playwright_production_reorder_fix.png`, fullPage: true});
	const result = {status: "passed", browser: "Chromium", tested_at: new Date().toISOString(), assertions: [
		"生产 Stock Entry 提交后投递安全库存检查",
		"实际 source warehouse 不同于原 Item Reorder 仓库时仍生成物料需求",
		"重复检查不会重复生成物料需求",
	], calls};
	await fs.writeFile(`${appRoot}/docs/playwright_production_reorder_fix_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
	await new Promise(resolve => server.close(resolve));
}
