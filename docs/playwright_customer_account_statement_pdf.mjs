import fs from "node:fs";
import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const statementName = process.env.STATEMENT_NAME || "CNR-2026-00001";
const evidenceDir = "/workspace/docs/china-finance-test-evidence";
const browserPath = process.env.PLAYWRIGHT_CHROMIUM_PATH
	|| "/home/cst/.cache/ms-playwright/chromium-1169/chrome-linux/chrome";
const errors = [];

fs.mkdirSync(evidenceDir, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: browserPath, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (error) => errors.push({ type: "pageerror", message: error.message }));
page.on("console", (message) => {
	if (message.type() === "error") errors.push({ type: "console", message: message.text() });
});
page.on("response", (response) => {
	if (response.status() >= 400) errors.push({ type: "http", status: response.status(), url: response.url() });
});

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/(app|desk)/, { timeout: 20000 });

	await page.goto(`${baseUrl}/app/china-reconciliation-statement/${statementName}`, { waitUntil: "networkidle", timeout: 30000 });
	await page.locator(".title-text-form").filter({ hasText: statementName }).waitFor({ timeout: 20000 });
	const reconcileMenu = page.getByRole("button", { name: "对账", exact: true }).last();
	await reconcileMenu.click();
	const exportButton = page.getByRole("button", { name: "导出客户对账单 PDF", exact: true });
	await exportButton.waitFor({ state: "visible", timeout: 10000 });
	await page.screenshot({ path: `${evidenceDir}/customer-account-statement-form.png`, fullPage: true });

	const downloadPromise = page.waitForEvent("download", { timeout: 30000 });
	await exportButton.click();
	const download = await downloadPromise;
	const pdfPath = `${evidenceDir}/customer-account-statement.pdf`;
	await download.saveAs(pdfPath);
	const pdfPage = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
	await pdfPage.goto(`file://${pdfPath}`, { waitUntil: "domcontentloaded", timeout: 30000 });
	await pdfPage.waitForTimeout(1500);
	await pdfPage.screenshot({ path: `${evidenceDir}/customer-account-statement-pdf-viewer.png`, fullPage: true });
	await pdfPage.close();
	const bodyText = await page.locator("body").innerText();
	const result = {
		statementName,
		pageUrl: page.url(),
		exportVisible: true,
		downloadFilename: download.suggestedFilename(),
		pdfPath,
		pdfBytes: fs.statSync(pdfPath).size,
		showsOrderDetails: bodyText.includes("订单账单明细"),
		errors,
	};
	fs.writeFileSync(`${evidenceDir}/customer-account-statement-playwright.json`, JSON.stringify(result, null, 2));
	console.log(JSON.stringify(result));
} finally {
	await browser.close();
}
