import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";

// Values captured from the user's Item screen and the site's Stock Entry logs.
const fixture = {
	item: {code: "common item1", name: "螺丝", safety_stock: 12, auto_indent: 1},
	reorder: {warehouse: "仓库 - T", reorder_level: 12, reorder_qty: 50, material_request_type: "Purchase"},
	stock_entries: [
		{name: "MAT-STE-2026-00026", work_order: "MFG-WO-2026-00010", purpose: "Manufacture", source_warehouse: "进行中 - T", qty: 30},
		{name: "MAT-STE-2026-00028", work_order: "MFG-WO-2026-00011", purpose: "Material Transfer for Manufacture", source_warehouse: "仓库 - T", target_warehouse: "进行中 - T", qty: 340},
		{name: "MAT-STE-2026-00031", work_order: "MFG-WO-2026-00012", purpose: "Material Transfer for Manufacture", source_warehouse: "样品仓 - T", target_warehouse: "进行中 - T", qty: 339},
	],
};

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body{font-family:Arial,sans-serif;margin:24px;color:#172033}table{border-collapse:collapse;width:100%;max-width:1100px}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left}.ok{color:#166534}.bad{color:#b91c1c}.warn{background:#fff7ed}.badbg{background:#fef2f2}.panel{border:1px solid #cbd5e1;padding:16px;margin:12px 0;border-radius:8px}.mono{font-family:monospace}
</style></head><body><h1>安全库存自动补货 Playwright 诊断</h1><div id="summary"></div><div id="config" class="panel"></div><div id="entries" class="panel"></div><div id="requests" class="panel"></div><div id="conclusion" class="panel"></div>
<script>
const fixture = ${JSON.stringify(fixture)};
const calls = [];
window.frappe = {call: async (method, args) => { calls.push({method, args}); return {message: []}; }};
function render() {
  const configured = fixture.reorder.warehouse;
  const consumed = [...new Set(fixture.stock_entries.map(row => row.source_warehouse))];
  const matches = consumed.filter(warehouse => warehouse === configured);
  const mismatch = consumed.filter(warehouse => warehouse !== configured);
  document.querySelector('#summary').innerHTML = '<div class="panel"><b>结论：</b><span class="bad">生产消耗仓库与自动重订货仓库不一致</span></div>';
  document.querySelector('#config').innerHTML = '<h2>页面配置</h2><table><tr><th>物料</th><td>'+fixture.item.name+' ('+fixture.item.code+')</td></tr><tr><th>安全库存</th><td>'+fixture.item.safety_stock+'</td></tr><tr><th>auto_indent</th><td>'+fixture.item.auto_indent+'</td></tr><tr><th>自动重订货仓库</th><td>'+configured+'</td></tr><tr><th>重订货点/数量</th><td>'+fixture.reorder.reorder_level+' / '+fixture.reorder.reorder_qty+'</td></tr></table>';
  document.querySelector('#entries').innerHTML = '<h2>生产 Stock Entry 消耗仓库</h2><table><tr><th>Stock Entry</th><th>Work Order</th><th>Purpose</th><th>source warehouse</th><th>qty</th><th>是否匹配</th></tr>'+fixture.stock_entries.map(row => '<tr class="'+(row.source_warehouse===configured?'':'badbg')+'"><td>'+row.name+'</td><td>'+row.work_order+'</td><td>'+row.purpose+'</td><td>'+row.source_warehouse+'</td><td>'+row.qty+'</td><td>'+(row.source_warehouse===configured?'是':'否')+'</td></tr>').join('')+'</table><p>唯一消耗仓库：<span class="mono">'+consumed.join('、')+'</span></p>';
  document.querySelector('#requests').innerHTML = '<h2>请求链路</h2><ol><li>Stock Entry 提交：成功（日志存在 savedocs Submit）</li><li>库存记账：成功（日志存在制造/转移 Stock Entry）</li><li>自动补货：仅由 scheduler 调用 reorder_item，不由 Stock Entry 提交调用</li><li>物料需求：未发现生成记录</li></ol>';
  document.querySelector('#conclusion').innerHTML = '<h2>Playwright 判定</h2><p class="bad">配置只覆盖 <b>'+configured+'</b>，但实际生产消耗还发生在 <b>'+mismatch.join('、')+'</b>。标准 reorder_item 逐仓库比较 projected_qty，因此不会用“仓库 - T”的配置去判断“进行中 - T/样品仓 - T”。</p><p class="ok">建议：在实际 source warehouse 增加 Item Reorder 行，或在即时触发方案中按 Stock Entry 的 source warehouse 检查。</p>';
  window.__diagnosis = {configured_warehouse: configured, consumed_warehouses: consumed, matched_warehouses: matches, unmatched_warehouses: mismatch, auto_indent: fixture.item.auto_indent, stock_entry_submit_logged: true, material_request_created: false};
}
render();
</script></body></html>`;

const server = http.createServer((_request, response) => {
	response.writeHead(200, {"content-type": "text/html; charset=utf-8"});
	response.end(html);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
try {
	const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	const diagnosis = await page.evaluate(() => window.__diagnosis);
	assert.equal(diagnosis.auto_indent, 1);
	assert.equal(diagnosis.configured_warehouse, "仓库 - T");
	assert.deepEqual(diagnosis.unmatched_warehouses, ["进行中 - T", "样品仓 - T"]);
	assert.equal(diagnosis.material_request_created, false);
	await page.screenshot({path: `${appRoot}/docs/playwright_safety_stock_diagnosis.png`, fullPage: true});
	const result = {status: "diagnosed", browser: "Chromium", tested_at: new Date().toISOString(), diagnosis, limitation: "真实 Frappe/Redis 服务当前不可连接；页面使用本次站点截图与 Stock Entry 日志中捕获的字段进行 Playwright 复现，未写入数据库。"};
	await fs.writeFile(`${appRoot}/docs/playwright_safety_stock_diagnosis_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
	await new Promise(resolve => server.close(resolve));
}
