import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
try {
	const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
	const page = await context.newPage();
	page.on("console", (message) => console.log("CONSOLE", message.type(), message.text()));
	page.on("pageerror", (error) => console.log("PAGEERROR", error.message));
	await page.goto(`${baseUrl}/login`, {waitUntil: "domcontentloaded"});
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, {timeout: 15000});
	await page.waitForTimeout(2500);
	console.log("URL", page.url());
	console.log("BODY", (await page.locator("body").innerText()).slice(0, 5000));
	await page.goto(`${baseUrl}/app/Customer`, {waitUntil: "domcontentloaded"});
	await page.waitForTimeout(2500);
	console.log("CUSTOMER_URL", page.url());
	console.log("BUTTONS", await page.getByRole("button").allTextContents());
	console.log("MENU_ITEMS", await page.locator(".list-sidebar, .page-actions, .dropdown-menu").allTextContents());
	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_real_import_customer.png", fullPage: true});
} finally {
	await browser.close();
}
