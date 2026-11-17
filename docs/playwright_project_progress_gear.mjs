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
	console.log("open login");
	await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });
	console.log("open project");
	await page.goto("http://127.0.0.1:8300/app/project/PROJ-0008", { waitUntil: "domcontentloaded" });
	await page.getByText("流程进度", { exact: true }).click();
	const grid = page.locator('[data-fieldname="custom_project_progress_items"]');
	await grid.waitFor({ state: "visible", timeout: 15000 });
	console.log("grid visible");
	const gear = grid.locator(".grid-heading-row .grid-static-col.pointer").first();
	await gear.click();
	console.log("gear clicked");
	await page.waitForTimeout(1000);
	console.log("modals", await page.locator(".modal-dialog").allTextContents());
	const dialog = page.locator(".modal-dialog:visible").last();
	await dialog.waitFor({ state: "visible", timeout: 5000 });
	assert.equal(await dialog.isVisible(), true);
	console.log("dialog visible");
	await page.screenshot({ path: `${appRoot}/docs/playwright_project_progress_gear.png`, fullPage: true });
	const result = { status: "passed", project: "PROJ-0008", gear_visible: await gear.isVisible(), dialog_visible: true };
	await fs.writeFile(`${appRoot}/docs/playwright_project_progress_gear_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
