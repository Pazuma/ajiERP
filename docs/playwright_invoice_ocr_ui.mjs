import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const invoiceFile = "/workspace/悦为智能技术（东莞）有限公司_20260721150445.pdf";
const screenshot = "/workspace/docs/playwright_invoice_ocr_ui.png";
const results = [];
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
page.on("console", (message) => {
	if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto(`${baseUrl}/desk/china-tax-invoice/view/list`, { waitUntil: "domcontentloaded" });
	await page.getByRole("button", { name: /添加|新建/ }).click();
	await page.waitForURL(/\/desk\/china-tax-invoice\/new-/, { timeout: 20000 });
	await page.locator(".page-actions:visible").first().waitFor({ state: "visible", timeout: 20000 });
	await page.waitForTimeout(1500);

	await page.route("**/api/method/china_finance.services.invoice_recognition.recognize_invoice_for_form", async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({ message: {
				task: "CTIR-2026-TEST",
				data: {
					invoice_type: "数电普通发票", invoice_number: "TEST202609040001", invoice_code: "",
					invoice_date: "2026-07-21", seller_name: "测试销售方", seller_tax_id: "91441900SELLER01",
					buyer_name: "悦为智能技术（东莞）有限公司", buyer_tax_id: "91441900BUYER001",
					currency: "CNY", invoice_status: "蓝票",
					items: [{ item_name: "技术服务费", specification: "测试", unit: "项", quantity: 1, unit_price: 100, net_amount: 100, tax_rate: 6, tax_amount: 6 }],
				},
				warnings: ["Playwright 模拟识别结果，请人工核对"],
			} }),
		});
	});

	await page.getByRole("button", { name: "发票操作" }).click();
	await page.locator(".dropdown-menu:visible").getByText("识别发票", { exact: true }).click();
	const dialog = page.locator(".modal:visible");
	await dialog.getByText("上传并识别发票", { exact: true }).waitFor({ state: "visible", timeout: 10000 });
	results.push({ name: "上传识别弹窗", passed: await dialog.getByText("上传并识别发票").isVisible() });

	const fileInput = page.locator('input[type="file"]');
	if (await fileInput.count()) {
		await fileInput.first().setInputFiles(invoiceFile);
	} else {
		await dialog.getByText(/添加文件|上传文件/).click();
		const dynamicInput = page.locator('input[type="file"]');
		await dynamicInput.first().waitFor({ state: "attached", timeout: 10000 });
		await dynamicInput.first().setInputFiles(invoiceFile);
	}
	await page.waitForTimeout(1200);
	await dialog.getByRole("button", { name: "上传并识别" }).click();
	await dialog.waitFor({ state: "hidden", timeout: 20000 });
	await page.waitForTimeout(800);

	const invoiceNumber = await page.locator('[data-fieldname="invoice_number"] input').inputValue();
	const invoiceDate = await page.locator('[data-fieldname="invoice_date"] input').inputValue();
	const sellerName = await page.locator('[data-fieldname="seller_name"] input').inputValue();
	const buyerName = await page.locator('[data-fieldname="buyer_name"] input').inputValue();
	const originalFile = await page.locator('[data-fieldname="original_file"] .attached-file-link').textContent().catch(() => "");
	const rowText = await page.locator('[data-fieldname="items"] .grid-body').innerText();
	results.push({ name: "发票头自动回填", passed: invoiceNumber === "TEST202609040001" && invoiceDate === "2026-07-21" && sellerName === "测试销售方" && buyerName.includes("悦为智能") });
	results.push({ name: "附件回填", passed: Boolean(originalFile?.trim()) });
	results.push({ name: "明细自动回填", passed: rowText.includes("技术服务费") && rowText.includes("100.00") });
	await page.screenshot({ path: screenshot, fullPage: true });
} finally {
	await browser.close();
}

console.log(JSON.stringify({ results, consoleErrors, screenshot }, null, 2));
if (results.some((result) => !result.passed)) process.exitCode = 1;
