import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
const browser = await chromium.launch({headless:true, executablePath:"/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args:["--no-sandbox"]});
const page = await browser.newPage();
await page.goto("http://127.0.0.1:8300/login", {waitUntil:"domcontentloaded"});
await page.locator("#login_email").fill("Administrator"); await page.locator("#login_password").fill("admin"); await page.locator("button.btn-login").click(); await page.waitForURL(/desk/);
await page.goto("http://127.0.0.1:8300/desk/bom", {waitUntil:"domcontentloaded"}); await page.waitForTimeout(1500); await page.getByRole("button", {name:"菜单"}).click(); await page.getByText("导入", {exact:true}).click();
const modal=page.locator(".client-inline-import-dialog"); await modal.waitFor({state:"visible"}); await modal.locator('[data-role="flat-bom-mode"]').click(); await page.waitForTimeout(300);
console.log((await modal.innerHTML()).slice(0,12000)); await browser.close();
