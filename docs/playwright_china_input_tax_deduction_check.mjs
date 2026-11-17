import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
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
	if (response.status() >= 400) responseErrors.push({ status: response.status(), url: response.url(), method: response.request().method() });
});

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });

	await page.goto(`${baseUrl}/desk/china-tax-invoice/view/list`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(1000);
	const invoiceList = await page.evaluate(() => Array.from(document.querySelectorAll("button")).map((button) => button.innerText.trim()).filter(Boolean).slice(0, 40));

	await page.goto(`${baseUrl}/app/china-input-tax-deduction-batch`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(1000);
	const batchList = await page.evaluate(() => ({
		title: document.title,
		h1: document.querySelector(".page-head .title-text, .page-title-text")?.textContent?.trim() || "",
		buttons: Array.from(document.querySelectorAll("button")).map((button) => button.innerText.trim()).filter(Boolean).slice(0, 20),
		url: location.href,
	}));

	console.log(JSON.stringify({ invoiceList, batchList, consoleErrors, responseErrors }, null, 2));
} finally {
	await browser.close();
}
