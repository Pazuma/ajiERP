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
	await page.goto("http://127.0.0.1:8300/app/purchase-order/new-purchase-order", { waitUntil: "networkidle" });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Purchase Order");
	await page.locator('[id="page-Purchase Order"]').getByRole("button", { name: "项目" }).click();
	await page.getByText("绑定项目进度节点", { exact: true }).click();
	const dialog = page.locator(".modal-dialog:visible").last();
	await dialog.waitFor({ state: "visible", timeout: 15000 });
	await page.evaluate(async () => {
		const dialog = window.client_akivision_progress_bind_dialog;
		dialog.set_value("project", "PROJ-0008");
		await new Promise((resolve) => setTimeout(resolve, 1000));
		dialog.set_value("progress_step", "STEP-001");
	});
	await dialog.locator(".btn-primary").click();
	await page.waitForFunction(() => !document.querySelector(".modal-dialog.show"));
	const values = await page.evaluate(() => ({
		project: cur_frm.doc.project,
		step: cur_frm.doc.custom_progress_milestone_code,
		stepName: cur_frm.doc.custom_progress_step_name,
	}));
	assert.equal(values.project, "PROJ-0008");
	assert.equal(values.step, "STEP-001");
	await page.screenshot({ path: `${appRoot}/docs/playwright_progress_bind_dialog.png`, fullPage: true });
	const result = { status: "passed", doctype: "Purchase Order", values };
	await fs.writeFile(`${appRoot}/docs/playwright_progress_bind_dialog_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
