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
	await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });
	await page.goto("http://127.0.0.1:8300/app/work-order/new-work-order", { waitUntil: "networkidle" });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Work Order");
	await page.evaluate(async () => {
		await cur_frm.set_value("project", "PROJ-0008");
	});
	await page.waitForFunction(() => {
		const options = cur_frm.fields_dict.custom_progress_milestone_code?.df?.options || "";
		return String(options).includes("STEP-001");
	});
	const input = page.locator('input[data-fieldname="custom_progress_milestone_code"]');
	await input.click();
	await input.fill("STEP");
	await page.waitForTimeout(500);
	const visibleOptions = await page.locator('[data-fieldname="custom_progress_milestone_code"] .awesomplete li, .awesomplete li').allTextContents();
	assert.ok(visibleOptions.some((text) => text.includes("STEP-001")));
	assert.ok(visibleOptions.some((text) => text.includes("STEP-002")));
	await page.screenshot({ path: `${appRoot}/docs/playwright_work_order_progress_step_dropdown.png`, fullPage: true });
	const result = { status: "passed", visibleOptions };
	await fs.writeFile(`${appRoot}/docs/playwright_work_order_progress_step_dropdown_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
