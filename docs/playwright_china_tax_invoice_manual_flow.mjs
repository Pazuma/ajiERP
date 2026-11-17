import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const screenshot = "/workspace/docs/china-finance-test-evidence/china-tax-invoice-manual-flow.png";
const evidence = "/workspace/docs/china-finance-test-evidence/china-tax-invoice-manual-flow.json";
const testData = {
	company: "阿基视觉（东莞）",
	direction: "进项",
	invoice_type: "增值税专用发票",
	invoice_number: "TI202609070001",
	invoice_code: "44002610000001",
	invoice_date: "2026-09-07",
	invoice_status: "蓝票",
	seller_name: "深圳市测试供应链有限公司",
	seller_tax_id: "91440300TESTSUPP01",
	buyer_name: "阿基视觉（东莞）",
	buyer_tax_id: "",
	currency: "CNY",
	original_file: "/private/files/悦为智能技术（东莞）有限公司_20260721150445.pdf",
	item: {
		item_name: "技术服务费",
		specification: "测试",
		unit: "项",
		quantity: 1,
		unit_price: 100,
		net_amount: 100,
		tax_rate: 6,
		tax_amount: 6,
		goods_service_code: "3040000000000000000",
	},
};

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
page.on("response", async (response) => {
	if (response.status() >= 400) {
		responseErrors.push({
			status: response.status(),
			url: response.url(),
			method: response.request().method(),
		});
	}
});

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });

	await page.goto(`${baseUrl}/desk/china-tax-invoice/view/list`, { waitUntil: "domcontentloaded" });
	await page.getByRole("button", { name: "添加中国税务发票" }).click();
	await page.waitForURL(/\/desk\/china-tax-invoice\/new-/, { timeout: 20000 });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doc && cur_frm.doc.__islocal === 1, null, { timeout: 20000 });

	const saved = await page.evaluate(async (data) => {
		const frm = cur_frm;
		await frm.set_value("company", data.company);
		await frm.set_value("direction", data.direction);
		await frm.set_value("invoice_type", data.invoice_type);
		await frm.set_value("invoice_number", data.invoice_number);
		await frm.set_value("invoice_code", data.invoice_code);
		await frm.set_value("invoice_date", data.invoice_date);
		await frm.set_value("invoice_status", data.invoice_status);
		await frm.set_value("seller_name", data.seller_name);
		await frm.set_value("seller_tax_id", data.seller_tax_id);
		await frm.set_value("buyer_name", data.buyer_name);
		await frm.set_value("buyer_tax_id", data.buyer_tax_id);
		await frm.set_value("currency", data.currency);
		await frm.set_value("original_file", data.original_file);
		await frm.set_value("remarks", "Playwright manual flow smoke test");
		frm.clear_table("items");
		const row = frm.add_child("items");
		Object.assign(row, data.item);
		frm.refresh_field("items");
		frm.dirty();
		await frm.save();
		await frm.save("Submit");
		return {
			name: frm.doc.name,
			docstatus: frm.doc.docstatus,
			net_amount: frm.doc.net_amount,
			tax_amount: frm.doc.tax_amount,
			gross_amount: frm.doc.gross_amount,
			items: (frm.doc.items || []).map((item) => ({
				item_name: item.item_name,
				net_amount: item.net_amount,
				tax_amount: item.tax_amount,
				gross_amount: item.gross_amount,
			})),
		};
	}, testData);

	await page.screenshot({ path: screenshot, fullPage: true });

	const result = { saved, consoleErrors, responseErrors, screenshot, testData };
	await page.context().storageState();
	console.log(JSON.stringify(result, null, 2));
	await browser.close();
	if (saved.docstatus !== 1) process.exitCode = 1;
} catch (error) {
	await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
	await browser.close();
	throw error;
}
