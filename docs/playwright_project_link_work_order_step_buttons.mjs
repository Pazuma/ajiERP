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
	await page.goto("http://127.0.0.1:8300/app/project/PROJ-0008", { waitUntil: "networkidle" });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Project");
	await page.evaluate(() => {
		const button = document.querySelector('button.btn-new[data-doctype="Work Order"]');
		button.scrollIntoView({ block: "center" });
		button.click();
	});
	await page.locator(".modal-dialog:visible").waitFor({ timeout: 15000 });
	const select = page.locator('select[data-fieldname="progress_step"]');
	await select.waitFor({ state: "visible", timeout: 15000 });
	const options = await select.locator("option").allTextContents();
	await select.selectOption({ label: "STEP-001 - 11（进行中）" });
	await page.locator(".modal-dialog:visible .modal-footer .btn-primary").click();
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Work Order", { timeout: 15000 });
	const values = await page.evaluate(() => ({
		doctype: cur_frm.doctype,
		project: cur_frm.doc.project,
		step: cur_frm.doc.custom_progress_milestone_code,
		stepName: cur_frm.doc.custom_progress_step_name,
	}));
	assert.equal(options.filter(Boolean).length, 2);
	assert.ok(options.includes("STEP-001 - 11（进行中）"));
	assert.equal(values.doctype, "Work Order");
	assert.equal(values.project, "PROJ-0008");
	assert.equal(values.step, "STEP-001");
	assert.equal(values.stepName, "11");
	const beforeSaveValues = await page.evaluate(async () => {
		cur_frm.doc.project = "";
		cur_frm.doc.custom_progress_milestone_code = "";
		cur_frm.doc.custom_progress_step_name = "";
		await cur_frm.script_manager.trigger("before_save");
		return {
			project: cur_frm.doc.project,
			step: cur_frm.doc.custom_progress_milestone_code,
			stepName: cur_frm.doc.custom_progress_step_name,
		};
	});
	assert.deepEqual(beforeSaveValues, { project: "PROJ-0008", step: "STEP-001", stepName: "11" });
	await page.screenshot({ path: `${appRoot}/docs/playwright_project_link_work_order_step_buttons.png`, fullPage: true });
	const result = { status: "passed", options, values, beforeSaveValues };
	await fs.writeFile(`${appRoot}/docs/playwright_project_link_work_order_step_buttons_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
