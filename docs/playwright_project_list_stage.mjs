import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

try {
	const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
	page.on("pageerror", (error) => console.log(`pageerror: ${error.message}`));
	await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });
	await page.goto("http://127.0.0.1:8300/app/project", { waitUntil: "networkidle" });
	await page.locator(".list-row-container").first().waitFor({ state: "visible", timeout: 15000 });
	const row = page.locator(".list-row-container", { hasText: "222" }).first();
	await row.waitFor({ state: "visible", timeout: 15000 });
	const rowText = await row.innerText();
	const statusText = await row.locator(".indicator-pill").first().innerText();
	assert.match(rowText, /PRO-20260915-00001/);
	assert.match(statusText, /进行中/);
	await page.screenshot({ path: `${appRoot}/docs/playwright_project_list_stage.png`, fullPage: true });
	const result = { status: "passed", project: "PROJ-0008", statusText, rowText };
	await fs.writeFile(`${appRoot}/docs/playwright_project_list_stage_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
