// Read-only check of the actual Item purchasing and pricing tabs.
const playwright = (await import(process.env.PLAYWRIGHT_MODULE_PATH || "/workspace/development/erpnext.official/node_modules/playwright/index.js")).default;
const browser = await playwright.chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const requests = [];
page.on("pageerror", error => errors.push(error.message));
page.on("response", response => {
	if (response.status() >= 400 && response.url().includes("/api/")) requests.push(`${response.status()} ${response.url()}`);
});
const base = process.env.BASE_URL || "http://127.0.0.1:8300";
const item = process.env.ITEM_CODE || "1007209102-v0";
try {
	await page.goto(`${base}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill(process.env.TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 30000 });
	await page.goto(`${base}/app/item/${encodeURIComponent(item)}`, { waitUntil: "domcontentloaded" });
	await page.locator(".form-layout").waitFor({ timeout: 30000 });
	await page.getByText("采购", { exact: true }).first().click();
	await page.locator('[data-fieldname="supplier_items"]').waitFor({ state: "visible" });
	await page.waitForTimeout(1600);
	const $company = page.locator('[data-fieldname="custom_purchase_average_cost_html"] .purchase-average-company');
	if (await $company.count() && process.env.COMPANY) {
		await $company.selectOption(process.env.COMPANY);
		await page.waitForTimeout(1000);
	}
	const purchase = await page.evaluate(() => ({
		lastPurchaseRate: cur_frm.doc.last_purchase_rate,
		supplierRows: (cur_frm.doc.supplier_items || []).length,
		purchaseAverageInTab: !!cur_frm.fields_dict.custom_purchase_average_cost_html?.$wrapper?.text()?.includes("历史采购平均单价"),
		purchaseAverageResult: cur_frm.fields_dict.custom_purchase_average_cost_html?.$wrapper?.find(".purchase-average-result")?.text()?.trim() || "",
		purchaseAverageCompany: cur_frm.fields_dict.custom_purchase_average_cost_html?.$wrapper?.find(".purchase-average-company")?.val() || "",
		purchaseTierField: !!cur_frm.fields_dict.custom_cf_purchase_pricing_html,
	}));
	await page.screenshot({ path: "/tmp/item-purchase-readonly.png" });
	await page.getByText("定价", { exact: true }).first().click();
	await page.waitForTimeout(1400);
	const pricing = await page.evaluate(() => ({
		itemPriceRows: [...(cur_frm.fields_dict.prices_html?.$wrapper?.find(".price-row") || [])].map(row => row.textContent?.trim().replace(/\s+/g, " ").slice(0, 180)),
		tierEmpty: cur_frm.fields_dict.custom_cf_tier_pricing_html?.$wrapper?.text()?.includes("该物料没有按物料编码关联的 Pricing Rule") || false,
		salesTierCount: cur_frm._cf_pricing_data?.rows?.length ?? null,
	}));
	await page.screenshot({ path: "/tmp/item-pricing-readonly.png" });
	console.log(JSON.stringify({ item, purchase, pricing, errors, requests }, null, 2));
} finally {
	await browser.close();
}
