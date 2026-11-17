// Read-only acceptance: does not save tax figures or create business records.
import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";
const browser = await chromium.launch({ headless: true, executablePath: "/usr/bin/chromium-headless-shell", args: ["--no-sandbox"] });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", e => errors.push(e.message));
try {
	const base = process.env.TAX_TEST_URL || "http://127.0.0.1:8300";
	await page.goto(`${base}/login`);
	await page.locator("#login_email").fill(process.env.TAX_TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.TAX_TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/);
	await page.goto(`${base}/app/china-tax-calculation-sheet`);
	await page.waitForFunction(() => document.querySelector(".cf-tax-calculation-sheet"));
	await page.getByRole("button", { name: "维护本期数据", exact: true }).waitFor({ state: "visible" });
	await page.getByRole("button", { name: "维护本期数据", exact: true }).click();
	await page.locator(".modal:visible").waitFor();
	if (!await page.locator('.modal:visible [data-fieldname="basis"]').count()) throw Error("Missing evidence field");
	if (!await page.locator('.modal:visible [data-fieldname="ordinary_vat"]').count()) throw Error("Missing VAT scope confirmation");
	await page.locator(".modal:visible .btn-modal-close").click();
	await page.locator('[data-tax-type="SURCHARGE"]').click();
	await page.waitForFunction(() => document.querySelector(".cf-tax-heading h4")?.textContent === "附加税费");
	if (errors.length) throw Error(errors.join("; "));
	console.log("PASS worksheet page, VAT maintenance dialog, evidence field and tax switching; no business writes");
} finally {
	await browser.close();
}
