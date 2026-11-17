import fs from "node:fs";
import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = process.env.CF_BASE_URL || "http://aki_test.localhost:8300";
const evidenceDir = "/workspace/docs/china-finance-test-evidence";
const resultFile = `${evidenceDir}/new-voucher-amount-clear.json`;
const screenshot = `${evidenceDir}/new-voucher-amount-clear.png`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH
	|| "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";

fs.mkdirSync(evidenceDir, { recursive: true });

const result = {
	base_url: baseUrl,
	writes_business_documents: false,
	steps: [],
	console_errors: [],
	page_errors: [],
	http_errors: [],
};
let browser;
let page;

function assert(condition, message) {
	if (!condition) throw new Error(message);
}

async function amountCells(row, side) {
	return row.locator(`.cf-${side}-input`).locator("..").locator(".cf-digit-cells span").allTextContents();
}

async function assertCleared(row, side, totalSelector) {
	assert(await row.locator(`.cf-${side}-input`).inputValue() === "", `${side} input should be empty`);
	assert((await amountCells(row, side)).every((value) => value === ""), `${side} digit cells should be empty`);
	assert((await page.locator(totalSelector).innerText()).includes("0.00"), `${side} total should be 0.00`);
}

try {
	browser = await chromium.launch({
		headless: true,
		executablePath,
		args: ["--no-sandbox"],
	});
	page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
	page.on("console", (message) => {
		if (message.type() === "error") result.console_errors.push(message.text());
	});
	page.on("pageerror", (error) => result.page_errors.push(error.message));
	page.on("response", (response) => {
		if (response.status() >= 400) result.http_errors.push({ status: response.status(), url: response.url() });
	});

	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill(process.env.CF_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.CF_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto(`${baseUrl}/desk/china-new-voucher`, { waitUntil: "domcontentloaded" });
	await page.locator(".cf-manual-voucher").waitFor({ state: "visible", timeout: 20000 });

	const row = page.locator(".cf-entry-grid tbody tr").first();
	const debit = row.locator(".cf-debit-input");
	const credit = row.locator(".cf-credit-input");

	await debit.fill("100.00");
	assert((await amountCells(row, "debit")).some((value) => value !== ""), "debit digit cells should render after input");
	result.steps.push({ name: "录入借方金额后显示金额九格", passed: true });

	await debit.press("Control+A");
	await debit.press("Backspace");
	await assertCleared(row, "debit", ".cf-total-debit");
	result.steps.push({ name: "Backspace 清空借方金额、九格及合计", passed: true });

	await debit.fill("100.00");
	await debit.press("Control+A");
	await debit.press("Delete");
	await assertCleared(row, "debit", ".cf-total-debit");
	result.steps.push({ name: "Delete 清空借方金额、九格及合计", passed: true });

	await debit.fill("100.00");
	await credit.fill("100.00");
	assert(await debit.inputValue() === "", "credit input should clear debit input");
	assert((await amountCells(row, "debit")).every((value) => value === ""), "credit input should clear debit digit cells");
	assert(await credit.inputValue() === "100.00", "credit input should keep entered amount");
	assert((await amountCells(row, "credit")).some((value) => value !== ""), "credit digit cells should render");
	result.steps.push({ name: "同一行借贷互斥且九格同步", passed: true });

	await page.screenshot({ path: screenshot, fullPage: true });
	result.screenshot = screenshot;
} catch (error) {
	result.error = { name: error.name, message: error.message };
} finally {
	if (browser) await browser.close();
	fs.writeFileSync(resultFile, JSON.stringify(result, null, 2));
}

console.log(JSON.stringify(result, null, 2));
if (result.error || result.steps.some((step) => !step.passed)) process.exitCode = 1;
