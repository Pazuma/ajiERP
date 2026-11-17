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
	await page.goto("http://127.0.0.1:8300/app/project/PROJ-0008", { waitUntil: "networkidle" });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Project");
	await page.getByText("流程进度", { exact: true }).click();
	await page.locator(".client-progress-reference-summary").waitFor({ state: "visible", timeout: 15000 });
	const summaryText = await page.locator(".client-progress-reference-summary").innerText();
	assert.match(summaryText, /节点关联表单/);
	assert.match(summaryText, /STEP-001/);
	assert.match(summaryText, /暂无绑定表单/);
	await page.screenshot({ path: `${appRoot}/docs/playwright_project_progress_reference_summary.png`, fullPage: true });
	const result = { status: "passed", project: "PROJ-0008", summaryText };
	await fs.writeFile(`${appRoot}/docs/playwright_project_progress_reference_summary_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
