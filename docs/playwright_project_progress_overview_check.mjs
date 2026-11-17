import { chromium } from '../development/erpnext.official/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const app = '/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision';
const context = {
  frappe: { ui: {form: {on() {}}}, utils: {escape_html: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;')} },
  __: value => value, flt: value => Number(value || 0),
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(`${app}/public/js/project_progress.js`, 'utf8'), context);
const rows = [
  {progress_category: '光学参数', subject: '图纸确认', business_summary: '现有系统进度', weight: 40, actual_completed_on: '2026-10-20 10:00:00', remarks: '<script>危险文本</script>', references: [{reference_doctype: 'Sales Order', reference_name: 'SO-001'}]},
  {progress_category: '光学参数', subject: '参数确认', weight: 30},
  {progress_category: '结构', subject: '模型加工', weight: 20},
  {progress_category: '光学参数', subject: '最终确认', weight: 10},
];
const html = context.build_progress_reference_summary_html(rows);
assert(html.includes('rowspan="2"'));
assert(html.includes('&lt;script>'));
assert(!html.includes('<script>危险文本'));
assert(html.includes('现有系统进度'));
assert(html.includes('2026-10-20'));
assert(!html.includes('2026-10-20 10:00:00'));
assert(html.indexOf('模型加工') < html.indexOf('最终确认'));
assert(context.build_progress_reference_summary_html([]).includes('colspan="10"'));

const browser = await chromium.launch({headless: true, executablePath: '/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome', args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1920, height: 1080}});
page.on('pageerror', error => console.error('PAGE ERROR:', error.message));
try {
  await page.goto('http://127.0.0.1:8300/login');
  await page.locator('#login_email').fill('Administrator');
  await page.locator('#login_password').fill('admin');
  await page.locator('button.btn-login').click();
  await page.waitForURL(/\/app|\/desk/);
  await page.goto('http://127.0.0.1:8300/app/project/PROJ-0010');
  await page.waitForFunction(() => window.cur_frm?.doc?.name === 'PROJ-0010' && document.querySelector('.client-project-progress-overview'));
  await page.locator('[role="tab"][data-fieldname="custom_progress_tab"]').click();
  const table = page.locator('.client-project-progress-overview');
  await table.waitFor({state: 'visible'});
  assert.equal(await table.locator('th').count(), 10);
  assert.equal(await table.locator('tbody tr').count(), await page.evaluate(() => Math.max(1, cur_frm.doc.custom_project_progress_items.length)));
  const grid = page.locator('[data-fieldname="custom_project_progress_items"]');
  assert.equal(await grid.isVisible(), false);
  await page.locator('[data-edit-progress]').click();
  await grid.waitFor({state: 'visible'});
  assert.equal(await page.evaluate(() => frappe.get_meta('Project Progress Item').fields.find(f => f.fieldname === 'progress_category').label), '进度类别');
  await page.locator('[data-edit-progress]').click();
  await grid.waitFor({state: 'hidden'});
  const dimensions = await table.evaluate(el => ({width: el.getBoundingClientRect().width, container: el.parentElement.getBoundingClientRect().width, overflow: getComputedStyle(el.parentElement).overflowX, firstWidth: el.querySelector('th').getBoundingClientRect().width}));
  assert(dimensions.width >= 1635);
  assert(dimensions.firstWidth < 150);
  await page.screenshot({path: '/home/cst/frappe_docker/docs/project-progress-overview-implemented.png', fullPage: true});
  console.log(JSON.stringify({passed: true, headers: await table.locator('th').allTextContents(), dimensions}, null, 2));
} catch (error) {
  console.error(await page.evaluate(() => ({url: location.href, doc: window.cur_frm?.doc?.name, summary: document.querySelector('.client-progress-reference-summary')?.innerHTML, text: document.body.innerText.slice(-5000)})));
  throw error;
} finally {
  await browser.close();
}
