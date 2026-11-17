import fs from 'node:fs/promises';

// Reuse the existing representative payload and Frappe harness.
const existing = await fs.readFile(new URL('./playwright_kpi_dashboard_ui.mjs', import.meta.url), 'utf8');
const harness = existing.slice(0, existing.indexOf('const server = http.createServer')).replace('from "/home/', 'from "file:///home/');
const checks = `
const server = http.createServer((req,res) => { res.writeHead(200, {'content-type':'text/html; charset=utf-8'}); res.end(html); });
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({headless:true, executablePath:'/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome', args:['--no-sandbox']});
try {
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const errors = [];
 page.on('pageerror', error => errors.push(error.message));
 await page.goto('http://127.0.0.1:' + server.address().port);
 await page.waitForSelector('.kpi-card');
 assert.equal(await page.locator('[role=tab]').count(),5);
 assert.equal(await page.locator('[role=tab][aria-selected=true]').innerText(),'经营总览');
 assert.equal(await page.locator('.kpi-card').count(),8);
 assert.equal(await page.locator('.kpi-metric-table').count(),0);
 const tabs = ['overview','sales','receivable','operations','high_tech'];
 for (const tab of tabs) {
  await page.locator('#kpi-tab-' + tab).click();
  assert.equal(await page.locator('[aria-selected=true]').getAttribute('id'),'kpi-tab-' + tab);
  assert.equal(await page.locator('.kpi-section').first().locator('.kpi-card').count(),4);
  assert.equal(await page.locator('.kpi-chart > .kpi-table-card').count(),0);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
  await page.screenshot({path:appRoot + '/../../docs/kpi-tabs-' + tab + '.png',fullPage:true});
 }
 await page.locator('#kpi-tab-sales').click();
 assert.ok(await page.locator('body').innerText().then(t => t.includes('张三')));
 assert.equal(await page.locator('.kpi-metric-table').count(),0);
 await page.locator('.kpi-card').filter({hasText:'Total Sales Amount'}).click();
 assert.deepEqual(await page.evaluate(() => window.__routes.at(-1)),['query-report','Sales Order List']);
 await page.locator('select[data-fieldname=salesperson_limit]').selectOption('All');
 await page.waitForTimeout(50);
 assert.equal(await page.evaluate(() => window.__calls.at(-1).args.filters.salesperson_limit),'all');
 assert.equal(await page.locator('[aria-selected=true]').innerText(),'销售与交付');
 await page.locator('button[data-action=export]').click();
 assert.ok(await page.evaluate(() => window.__exportPayload.cmd.includes('export_kpi_dashboard')));
 await page.setViewportSize({width:390,height:844});
 for (const tab of tabs) {
  await page.locator('#kpi-tab-' + tab).click();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false,tab + ' mobile overflow');
 }
 assert.deepEqual(errors,[]);
 console.log('PASS: five business tabs, isolated content, four primary cards, full-width details, drilldown, filters, export, desktop/mobile overflow, no browser errors. Charts use the existing mocked harness.');
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
`;
await import('data:text/javascript;base64,' + Buffer.from(harness + checks).toString('base64'));
