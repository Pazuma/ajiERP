import { chromium } from '../development/erpnext.official/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';

const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',
  args: ['--no-sandbox'],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
try {
  await page.goto('http://127.0.0.1:8300/login');
  await page.locator('#login_email').fill('Administrator');
  await page.locator('#login_password').fill('admin');
  await page.locator('button.btn-login').click();
  await page.waitForURL(/\/(app|desk)/);
  await page.waitForFunction(() => window.frappe?.boot?.desktop_icons && frappe.app?.sidebar);
  const config = await page.evaluate(() => {
    const icon = frappe.boot.desktop_icons.find(i => i.label === 'KPI Dashboard');
    return { type: icon.link_type, route: frappe.utils.get_route_for_icon(icon) };
  });
  assert.equal(config.type, 'Workspace Sidebar');
  assert(config.route.includes('operations-kpi-dashboard'));
  await page.goto('http://127.0.0.1:8300/app/uom');
  await page.waitForFunction(() => window.frappe?.app?.sidebar?.sidebar_title);
  const before = await page.evaluate(() => frappe.app.sidebar.sidebar_title);
  const entry = page.getByText('指标看板', {exact: true}).last();
  await entry.click();
  await page.waitForURL(/operations-kpi-dashboard/);
  await page.waitForFunction(() => frappe.app.sidebar.sidebar_title === 'KPI Dashboard');
  await page.locator('#kpi-business-panel .kpi-card').first().waitFor();
  const result = await page.evaluate(() => ({
    before: null,
    sidebar: frappe.app.sidebar.sidebar_title,
    labels: [...document.querySelectorAll('.body-sidebar .sidebar-item-container')].map(el => el.getAttribute('item-name')),
    url: location.href,
  }));
  result.before = before;
  assert(result.labels.includes('运营指标看板'));
  assert(result.labels.includes('项目节点超时表'));
  assert(result.labels.includes('业务表单总表'));
  await page.screenshot({path: '/home/cst/frappe_docker/docs/kpi-module-navigation-fixed.png', fullPage: true});
  await page.reload();
  await page.waitForFunction(() => window.frappe?.app?.sidebar?.sidebar_title === 'KPI Dashboard');
  console.log(JSON.stringify({passed: true, ...result, reloadPassed: true}));
} catch (error) {
  console.error(await page.evaluate(() => ({url: location.href, sidebar: window.frappe?.app?.sidebar?.sidebar_title, matches: [...document.querySelectorAll('*')].filter(el => el.textContent.trim() === '指标看板' && el.children.length === 0).map(el => el.parentElement.outerHTML.slice(0, 2000))})));
  throw error;
} finally {
  await browser.close();
}
