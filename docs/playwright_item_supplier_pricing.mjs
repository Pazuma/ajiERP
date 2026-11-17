const playwrightPath = process.env.PLAYWRIGHT_MODULE_PATH || "/workspace/development/erpnext.official/node_modules/playwright/index.js";
const playwright = (await import(playwrightPath)).default;

const { chromium } = playwright;

const baseUrl = process.env.BASE_URL || "http://frappe:8300";
const screenshotPath = process.env.SCREENSHOT_PATH || "/workspace/docs/item-supplier-pricing-dialog.png";
const previewScreenshotPath = process.env.PREVIEW_SCREENSHOT_PATH || "/workspace/docs/item-supplier-pricing-preview.png";
const browser = await chromium.launch({
	headless: true,
	executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH,
	args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
// The pricing dialog is intentionally tall; use an acceptance viewport that
// captures both its read-only context header and rule fields in one frame.
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
page.on("pageerror", (error) => console.error(`Page error: ${error.stack || error.message}`));
const suffix = Date.now().toString(36);
const itemCode = `_PW-PRICE-${suffix}`;
let supplier;
let rule;

async function call(method, args = {}) {
	return page.evaluate(async ({ method, args }) => {
		const response = await frappe.call({ method, args });
		return response.message;
	}, { method, args });
}

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/);
	await page.waitForFunction(() => window.frappe?.db?.get_list, null, { timeout: 30000 });

	const defaults = await page.evaluate(async () => {
		const [uom, itemGroup, supplierGroup] = await Promise.all([
			frappe.db.get_list("UOM", { fields: ["name"], limit: 1 }),
			frappe.db.get_list("Item Group", { fields: ["name"], filters: { is_group: 0 }, limit: 1 }),
			frappe.db.get_list("Supplier Group", { fields: ["name"], filters: { is_group: 0 }, limit: 1 }),
		]);
		return { uom: uom[0].name, itemGroup: itemGroup[0].name, supplierGroup: supplierGroup[0].name };
	});
	supplier = await call("frappe.client.insert", { doc: { doctype: "Supplier", supplier_name: `_PW Formula Supplier ${suffix}`, supplier_group: defaults.supplierGroup, supplier_type: "Company" } });
	await call("frappe.client.insert", { doc: { doctype: "Item", item_code: itemCode, item_name: `Formula Item ${suffix}`, item_group: defaults.itemGroup, stock_uom: defaults.uom, is_stock_item: 0 } });

	await page.goto(`${baseUrl}/app/item/${encodeURIComponent(itemCode)}`, { waitUntil: "domcontentloaded" });
	await page.waitForSelector(".form-layout", { timeout: 20000 });
	const purchaseTab = page.getByText("采购", { exact: true }).first();
	await purchaseTab.click();
	const actions = page.locator('.cf-purchase-pricing-actions');
	await actions.getByRole('button', { name: '添加供应商以及报价', exact: true }).click();
	const addDialog = page.locator('.modal-dialog').filter({ hasText: '保存供应商' });
	await addDialog.locator('[data-fieldname="supplier"] input').fill(supplier.name);
	await addDialog.locator('[data-fieldname="supplier_part_no"] input').fill('PW-PART-001');
	await addDialog.getByRole('button', { name: '保存供应商', exact: true }).click();
	await addDialog.waitFor({ state: 'hidden' });
	await page.waitForFunction(() => cur_frm.doc.supplier_items?.length === 1 && !cur_frm.is_dirty());
	console.log('PASS: purchase panel adds supplier to an empty item');
	const grid = page.locator('[data-fieldname="supplier_items"]');
	await grid.waitFor({ state: "hidden" });
	const supplierTable = page.locator('.cf-supplier-table');
	await supplierTable.getByText(supplier.supplier_name, { exact: true }).waitFor();
	await supplierTable.getByRole('button', { name: '编辑', exact: true }).click();
	const editDialog = page.locator('.modal-dialog').filter({ hasText: '编辑供应商物料号' });
	await editDialog.locator('[data-fieldname="supplier_part_no"] input').fill('PW-PART-EDITED');
	await editDialog.getByRole('button', { name: '保存', exact: true }).click();
	await editDialog.waitFor({ state: 'hidden' });
	await supplierTable.getByText('PW-PART-EDITED', { exact: true }).waitFor();
	await supplierTable.getByRole('button', { name: '添加报价', exact: true }).click();

	const dialog = page.locator(".modal-dialog").filter({ hasText: "供应商报价规则" });
	await dialog.waitFor({ state: "visible" });
	const itemName = (await dialog.locator('[data-fieldname="item_name"] .control-value').textContent())?.trim() || "";
	const supplierName = (await dialog.locator('[data-fieldname="supplier_name"] .control-value').textContent())?.trim() || "";
	if (!itemName.includes(suffix) || !supplierName.includes(suffix)) throw new Error("Basic item/supplier information was not loaded.");
	await page.waitForTimeout(500);
	await dialog.screenshot({ path: screenshotPath });

	await dialog.locator('[data-fieldname="rule_type"] select').selectOption({ label: "阶梯降价" });
	console.log(`Selected rule: ${await dialog.locator('[data-fieldname="rule_type"] select').inputValue()}`);
	await dialog.locator('[data-fieldname="base_rate"] input').fill("10");
	await dialog.locator('[data-fieldname="start_qty"] input').fill("100");
	await dialog.locator('[data-fieldname="step_qty"] input').fill("100");
	await dialog.locator('[data-fieldname="discount_percent"] input').fill("5");
	await dialog.locator('[data-fieldname="minimum_rate"] input').fill("7");
	await dialog.locator('[data-fieldname="test_qty"] input').fill("300");
	await dialog.getByRole("button", { name: "试算" }).click();
	await dialog.getByText(/8\.5/).waitFor();
	await page.screenshot({ path: previewScreenshotPath, fullPage: true });

	await dialog.getByRole("button", { name: "保存报价规则" }).click();
	await dialog.waitFor({ state: "hidden" });
	rule = await page.evaluate(async ({ itemCode, supplier }) => {
		const item = await frappe.db.get_doc("Item", itemCode);
		return (item.supplier_items || []).find((row) => row.supplier === supplier);
	}, { itemCode, supplier: supplier.name });
	console.log(`Rule lookup: ${JSON.stringify(rule)}`);
	if (!rule.custom_active_pricing_rule || !rule.custom_pricing_rule_summary) throw new Error("Pricing rule was not linked back to Item Supplier.");
	await page.locator('.cf-quote-table').getByText(supplier.supplier_name, { exact: true }).waitFor();
	await supplierTable.getByRole('button', { name: '编辑报价', exact: true }).waitFor();
	await page.locator('.cf-quote-supplier-filter').selectOption(supplier.name);
	const folded = await page.evaluate(() => ({
		average: document.querySelector('.purchase-average-fold')?.open,
		other: document.querySelector('.cf-purchase-other')?.open,
		deliveryControls: document.querySelectorAll('.cf-purchase-other input[data-fieldname="delivered_by_supplier"]').length,
		addButtons: document.querySelectorAll('.cf-purchase-pricing-actions button').length,
	}));
	if (folded.average !== false || folded.other !== false || folded.deliveryControls !== 1 || folded.addButtons !== 1) throw new Error(`Unexpected panel layout: ${JSON.stringify(folded)}`);
	await page.locator('.cf-purchase-other summary').click();
	await page.locator('.cf-purchase-other input[data-fieldname="delivered_by_supplier"]').check();
	await page.evaluate(async () => { await cur_frm.save(); });
	await page.waitForFunction(() => !cur_frm._cf_purchase_pricing_loading);
	if (!(await page.evaluate(() => cur_frm.doc.delivered_by_supplier))) throw new Error('Moved delivery control did not save');
	await supplierTable.getByRole('button', { name: '编辑报价', exact: true }).waitFor();
	await page.screenshot({ path: '/workspace/docs/item-supplier-purchase-layout.png', fullPage: true });
	console.log('PASS: inline supplier edit, quote detail, filtering, folded sections and delivery save');
	console.log(JSON.stringify({ itemCode, supplier: supplier.name, rule: rule.custom_active_pricing_rule, itemName, supplierName, previewRate: 8.5 }));
	await supplierTable.getByRole('button', { name: '移除', exact: true }).click();
	const confirmation = page.locator('.modal-dialog').filter({ hasText: '确认移除供应商' });
	await confirmation.locator('.btn-primary').click();
	await page.waitForFunction(() => cur_frm.doc.supplier_items.length === 0 && !cur_frm.is_dirty());
	const persisted = await call('frappe.client.get', { doctype: 'Item', name: itemCode });
	if (persisted.supplier_items.length) throw new Error('Supplier removal was not saved');
	console.log('PASS: remove supplier association');
} finally {
	try {
		if (rule?.custom_active_pricing_rule) {
			const rowExists = await page.evaluate(async name => !!(await frappe.db.exists('Item Supplier', name)), rule.name);
			if (rowExists) await call("frappe.client.set_value", { doctype: "Item Supplier", name: rule.name, fieldname: "custom_active_pricing_rule", value: "" });
			await call("frappe.client.delete", { doctype: "Item Supplier Pricing Rule", name: rule.custom_active_pricing_rule });
		}
		if (supplier) {
			await call("frappe.client.delete", { doctype: "Item", name: itemCode });
			await call("frappe.client.delete", { doctype: "Supplier", name: supplier.name });
		}
	} catch (cleanupError) {
		console.error(`Cleanup warning: ${cleanupError.message}`);
	}
	await browser.close();
}
