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
	if (await page.locator(".modal-dialog:visible").count()) {
		await page.keyboard.press("Escape");
	}
	await page.getByText("更多信息", { exact: true }).click();
	await page.evaluate(async () => {
		await cur_frm.set_value("project", "PROJ-0008");
	});
	const button = page.locator(".client-progress-step-option:visible").first();
	await button.waitFor({ state: "visible", timeout: 15000 });
	const buttonText = await button.innerText();
	await button.click();
	const result = await page.evaluate(() => ({
		project: cur_frm.doc.project,
		step: cur_frm.doc.custom_progress_milestone_code,
		stepName: cur_frm.doc.custom_progress_step_name,
	}));
	assert.match(buttonText, /STEP-001/);
	assert.equal(result.step, "STEP-001");
	assert.equal(result.stepName, "11");
	await page.screenshot({ path: `${appRoot}/docs/playwright_work_order_progress_step_buttons.png`, fullPage: true });
	await fs.writeFile(`${appRoot}/docs/playwright_work_order_progress_step_buttons_result.json`, JSON.stringify({ status: "passed", buttonText, ...result }, null, 2) + "\n");
	console.log(JSON.stringify({ status: "passed", buttonText, ...result }));
} finally {
	await browser.close();
}
