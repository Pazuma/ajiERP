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
	await page.goto("http://127.0.0.1:8300/app/work-order/new-work-order", { waitUntil: "networkidle" });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Work Order");
	await page.evaluate(async () => {
		await cur_frm.set_value("project", "PROJ-0008");
	});
	await page.waitForFunction(() => {
		const field = cur_frm.fields_dict.custom_progress_milestone_code;
		const options = field?.df?.options || [];
		return Array.isArray(options) && options.some((option) => String(option).includes("STEP-001"));
	});
	const result = await page.evaluate(async () => {
		const field = cur_frm.fields_dict.custom_progress_milestone_code;
		const options = field.df.options || [];
		await cur_frm.set_value("custom_progress_milestone_code", "STEP-001 - 11（进行中）");
		await new Promise((resolve) => setTimeout(resolve, 300));
		return {
			project: cur_frm.doc.project,
			options,
			step: cur_frm.doc.custom_progress_milestone_code,
			stepName: cur_frm.doc.custom_progress_step_name,
		};
	});
	assert.equal(result.project, "PROJ-0008");
	assert.ok(result.options.some((option) => option.includes("STEP-001 - 11")));
	assert.ok(result.options.some((option) => option.includes("STEP-002 - 22")));
	assert.equal(result.stepName, "11");
	await page.screenshot({ path: `${appRoot}/docs/playwright_work_order_progress_steps.png`, fullPage: true });
	await fs.writeFile(`${appRoot}/docs/playwright_work_order_progress_steps_result.json`, JSON.stringify({ status: "passed", ...result }, null, 2) + "\n");
	console.log(JSON.stringify({ status: "passed", ...result }));
} finally {
	await browser.close();
}
