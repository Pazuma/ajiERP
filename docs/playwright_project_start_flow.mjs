import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";
const projectName = "PROJ-0008";
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

async function getFieldText(page, fieldname) {
	const field = page.locator(`[data-fieldname="${fieldname}"]`);
	const input = field.locator("input, textarea, select").first();
	if (await input.count()) {
		return (await input.inputValue()).trim();
	}
	return (await field.locator(".control-value, .like-disabled-input").first().innerText()).trim();
}

try {
	const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
	page.on("pageerror", (error) => console.log(`pageerror: ${error.message}`));
	await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });
	await page.goto(`http://127.0.0.1:8300/app/project/${projectName}`, { waitUntil: "domcontentloaded" });
	await page.waitForLoadState("networkidle");

	await page.getByText("流程进度", { exact: true }).click();
	await page.locator('[data-fieldname="custom_project_stage"]').waitFor({ state: "visible", timeout: 15000 });
	const beforeStage = await getFieldText(page, "custom_project_stage");
	const grid = page.locator('[data-fieldname="custom_project_progress_items"]');
	const beforeGridText = await grid.innerText();

	if (beforeStage !== "进行中") {
		await page.getByRole("button", { name: "进度" }).click();
		await page.getByText("项目开始", { exact: true }).click();
		await page.locator(".modal-dialog:visible").last().locator(".btn-primary").click();
		await page.waitForFunction(() => !document.querySelector(".modal-dialog.show"));
		await page.waitForLoadState("networkidle");
		await page.reload({ waitUntil: "networkidle" });
		await page.getByText("流程进度", { exact: true }).click();
	}

	const afterStage = await getFieldText(page, "custom_project_stage");
	const afterGridText = await page.locator('[data-fieldname="custom_project_progress_items"]').innerText();
	const pageIndicatorText = (await page.locator(".indicator-pill").first().innerText()).trim();
	const alertText = await page.locator(".frappe-alert").allTextContents();

	assert.equal(afterStage, "进行中");
	assert.match(afterGridText, /进行中/);
	assert.match(pageIndicatorText, /进行中/);
	await page.screenshot({ path: `${appRoot}/docs/playwright_project_start_flow.png`, fullPage: true });
	const result = { status: "passed", project: projectName, beforeStage, afterStage, pageIndicatorText, beforeGridText, afterGridText, alertText };
	await fs.writeFile(`${appRoot}/docs/playwright_project_start_flow_result.json`, JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
