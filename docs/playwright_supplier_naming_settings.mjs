import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";

const out = "/workspace/development/frappe-bench/apps/client_akivision/docs";
const browser = await chromium.launch({headless:true, executablePath:"/usr/bin/chromium-headless-shell", args:["--no-sandbox"]});
const page = await browser.newPage({viewport:{width:1440,height:1000}});
await page.goto("http://127.0.0.1:8300/login", {waitUntil:"domcontentloaded"});
await page.locator("#login_email").fill("Administrator");
await page.locator("#login_password").fill("admin");
await page.locator("button.btn-login").click();
await page.waitForURL(/desk|app/, {timeout:15000});
const result = {};
for (const [key, route] of [["document_naming_settings","/app/document-naming-settings"],["buying_settings","/app/buying-settings"]]) {
  await page.goto(`http://127.0.0.1:8300${route}`, {waitUntil:"networkidle"});
  await page.waitForTimeout(1200);
  await page.screenshot({path:`${out}/playwright_${key}.png`, fullPage:true});
  result[key] = {url: page.url(), title: await page.title(), text: (await page.locator("body").innerText()).slice(0,4000)};
}
await fs.writeFile(`${out}/playwright_supplier_naming_settings_result.json`, JSON.stringify(result,null,2));
await browser.close();
