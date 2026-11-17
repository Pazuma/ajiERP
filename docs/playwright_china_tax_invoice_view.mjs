import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const screenshot = "/workspace/docs/china-finance-test-evidence/china-tax-invoice-view.png";
const resultFile = "/workspace/docs/china-finance-test-evidence/china-tax-invoice-view.json";

const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
const consoleErrors = [];
const responseErrors = [];

page.on("console", (message) => {
	if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("response", (response) => {
	if (response.status() >= 400) {
		responseErrors.push({ status: response.status(), url: response.url(), method: response.request().method() });
	}
});

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });

	await page.goto(`${baseUrl}/app/china-tax-invoice/CTI-2026-00001`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(2000);

	const snapshot = await page.evaluate(() => {
		const doc = window.cur_frm?.doc || {};
		const customButtons = Array.from(document.querySelectorAll(".page-actions button, .custom-actions button")).map((button) => button.innerText.trim()).filter(Boolean);
		return {
			name: doc.name,
			docstatus: doc.docstatus,
			company: doc.company,
			direction: doc.direction,
			invoice_type: doc.invoice_type,
			invoice_number: doc.invoice_number,
			invoice_date: doc.invoice_date,
			invoice_status: doc.invoice_status,
			verification_status: doc.verification_status,
			deduction_status: doc.deduction_status,
			usage_status: doc.usage_status,
			accounting_status: doc.accounting_status,
			original_file: doc.original_file,
			customButtons,
			itemCount: (doc.items || []).length,
		};
	});

	await page.screenshot({ path: screenshot, fullPage: true });
	const payload = { snapshot, consoleErrors, responseErrors, screenshot };
	console.log(JSON.stringify(payload, null, 2));
	if (resultFile) {
		await page.evaluate(() => {});
	}
} finally {
	await browser.close();
}
