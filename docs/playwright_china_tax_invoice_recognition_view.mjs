import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const screenshot = "/workspace/docs/china-finance-test-evidence/china-tax-invoice-recognition-view.png";

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

	await page.goto(`${baseUrl}/app/china-tax-invoice-recognition`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(1500);

	const listSnapshot = await page.evaluate(() => ({
		title: document.title,
		h1: document.querySelector(".page-head .title-text, .page-title-text")?.textContent?.trim() || "",
		buttons: Array.from(document.querySelectorAll("button")).map((button) => button.innerText.trim()).filter(Boolean).slice(0, 20),
		url: location.href,
	}));

	await page.goto(`${baseUrl}/app/china-tax-invoice-recognition/new`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(1500);
	const formSnapshot = await page.evaluate(() => ({
		title: document.title,
		h1: document.querySelector(".page-head .title-text, .page-title-text")?.textContent?.trim() || "",
		primaryButtons: Array.from(document.querySelectorAll(".page-actions button")).map((button) => button.innerText.trim()).filter(Boolean),
		fields: Array.from(document.querySelectorAll("[data-fieldname]")).map((el) => el.getAttribute("data-fieldname")).filter(Boolean).slice(0, 20),
		url: location.href,
	}));

	await page.screenshot({ path: screenshot, fullPage: true });
	console.log(JSON.stringify({ listSnapshot, formSnapshot, consoleErrors, responseErrors, screenshot }, null, 2));
} finally {
	await browser.close();
}
