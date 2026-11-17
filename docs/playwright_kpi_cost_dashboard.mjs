// Reuse the existing dashboard fixture's Frappe shell; only calls are mocked.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { chromium } from '/workspace/development/erpnext.official/node_modules/playwright/index.mjs';

const docs = path.dirname(new URL(import.meta.url).pathname);
const fixture = (await fs.readFile(path.join(docs, 'playwright_kpi_dashboard_ui.mjs'), 'utf8'))
    .split('const server = http.createServer')[0]
    .replace(/^import .*;\n/gm, '').replaceAll('/home/cst/frappe_docker', '/workspace');
const html = await new (Object.getPrototypeOf(async function(){}).constructor)('fs', 'path', `${fixture}\nreturn html;`)(fs, path);
const browser = await chromium.launch({headless: true, executablePath: '/usr/bin/chromium-headless-shell', args: ['--no-sandbox']});
try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.setContent(html);
    await page.waitForSelector('.kpi-section');
    await page.evaluate(() => {
        const oldCall = frappe.call;
        window.costCalls = [];
        frappe.call = options => {
            if (!options.method.includes('operations_kpi_cost.')) return oldCall(options);
            costCalls.push(options);
            if (window.costHold) return;
            setTimeout(() => options.callback({message: {
                currency: 'CNY', generated_at: '2026-10-16', metrics: {
                    gross_margin: {value: .35, datatype: 'Percent', reason: '参考口径'},
                    revenue: {value: 1000, datatype: 'Currency'},
                    budget_execution: {value: null, reason: '预算尚未配置'}},
                trend: [{period:'2026-10', revenue:1000, sales_cost:650, gross_profit:350}],
                product_rows: [{item_code:'<测试产品>', stock_uom:'Nos', qty:10, production_cost:650, unit_cost:65, entry_count:1}],
                pagination: {page:1, page_length:20, total:1}, warnings:['参考数据，仅测试'], accounts:[]
            }}), 10);
        };
    });
    await page.click('#kpi-tab-cost');
    await page.waitForSelector('.kpi-cost-pagination');
    assert.match(await page.locator('body').innerText(), /35\.00%/);
    assert.match(await page.locator('body').innerText(), /预算尚未配置/);
    assert.equal(await page.locator('td').filter({hasText:'<测试产品>'}).count(), 1);
    await page.click('[data-action="export"]');
    assert.match(await page.evaluate(() => __exportPayload.cmd), /operations_kpi_cost_export/);
    await page.screenshot({path:path.join(docs,'playwright_kpi_cost_dashboard_desktop.png'), fullPage:true});
    await page.setViewportSize({width:390,height:900});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path:path.join(docs,'playwright_kpi_cost_dashboard_mobile.png'),fullPage:true});
    await page.evaluate(() => { window.costHold = true; });
    await page.click('[data-action="refresh"]');
    await page.click('#kpi-tab-sales');
    await page.waitForSelector('.kpi-section');
    await page.evaluate(() => costCalls.at(-1).callback({message:{metrics:{}}}));
    assert.equal(await page.locator('.kpi-cost-pagination').count(), 0);
    await page.click('[data-action="export"]');
    assert.match(await page.evaluate(() => __exportPayload.cmd), /operations_kpi_export/);
    assert.deepEqual(errors, []);
    console.log('PASS: cost rendering, null state, escaping, separate export, mobile layout, late response isolation, sales regression');
} finally { await browser.close(); }
