import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://aji_test.localhost:8200";
const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision";
const resultPath = `${appRoot}/docs/playwright_unified_stock_entry_form_result.json`;
const screenshotDesktop = `${appRoot}/docs/playwright_unified_stock_entry_form_desktop.png`;
const screenshotMobile = `${appRoot}/docs/playwright_unified_stock_entry_form_mobile.png`;
const runtimeIssues = [];

const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

const result = {
	status: "failed",
	tested_at: new Date().toISOString(),
	browser: "Chromium",
	base_url: baseUrl,
	viewport: {},
	assertions: [],
	runtime_issues: runtimeIssues,
	known_site_issues: [],
	observations: [],
};

try {
	const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
	const page = await context.newPage();
	page.on("pageerror", (error) => runtimeIssues.push(`pageerror: ${error.message}`));
	page.on("requestfailed", (request) => runtimeIssues.push(`requestfailed: ${request.url()}`));

	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });

	await page.goto(`${baseUrl}/app/stock-entry/new-stock-entry-1`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(3500);
	result.viewport.desktop = await page.evaluate(() => ({
		width: document.documentElement.clientWidth,
		scrollWidth: document.documentElement.scrollWidth,
	}));

	const fieldState = await page.evaluate(() => {
		const names = [
			"company",
			"custom_stock_direction",
			"custom_stock_reason",
			"custom_stock_entry_number",
			"posting_date",
			"posting_time",
			"stock_entry_type",
			"custom_excel_outbound_no",
			"custom_excel_receipt_type",
			"custom_stock_history_section",
		];
		return Object.fromEntries(names.map((name) => {
			const field = cur_frm?.fields_dict?.[name];
			return [name, {
				exists: Boolean(field),
				visible: Boolean(field?.$wrapper?.is(":visible")),
				value: field?.get_value?.() ?? null,
				options: field?.df?.options ?? null,
			}];
		}));
	});

	for (const name of ["company", "custom_stock_direction", "custom_stock_reason", "custom_stock_entry_number", "posting_date", "posting_time"]) {
		assert.equal(fieldState[name].exists, true, `字段 ${name} 存在`);
	}
	result.assertions.push("首屏核心字段完整：公司、方向、原因、单号、日期和时间");
	assert.equal(fieldState.custom_stock_direction.visible, true);
	assert.equal(fieldState.custom_stock_reason.visible, true);
	assert.equal(fieldState.custom_stock_entry_number.visible, true);
	assert.match(await page.locator('[data-fieldname="custom_stock_entry_number"]').innerText(), /保存后系统自动生成/);
	result.assertions.push("新建单据显示系统自动生成单号提示");

	const direction = page.locator('[data-fieldname="custom_stock_direction"] select');
	const reason = page.locator('[data-fieldname="custom_stock_reason"] select');
	await direction.selectOption({ label: "出库" });
	await page.waitForTimeout(250);
	const outboundReasons = await reason.locator("option").allTextContents();
	assert.deepEqual(outboundReasons.filter(Boolean), ["生产领料", "生产补料", "外发领料", "产线借用", "其它领用"]);
	await reason.selectOption({ label: "生产领料" });
	await page.waitForTimeout(250);
	const outboundType = await page.evaluate(() => cur_frm.doc.stock_entry_type);
	assert.equal(outboundType, "组装领料");
	result.assertions.push("出库方向仅显示出库原因，生产领料映射为组装领料");

	await direction.selectOption({ label: "入库" });
	await page.waitForTimeout(250);
	const inboundReasons = await reason.locator("option").allTextContents();
	assert.deepEqual(inboundReasons.filter(Boolean), ["生产退料", "生产入库", "采购入库"]);
	assert.equal(await reason.inputValue(), "");
	await reason.selectOption({ label: "生产入库" });
	await page.waitForTimeout(250);
	assert.equal(await page.evaluate(() => cur_frm.doc.stock_entry_type), "生产制造");
	result.assertions.push("切换入库会清空不兼容原因，并将生产入库映射为生产制造");

	await reason.selectOption({ label: "采购入库" });
	await page.waitForTimeout(300);
	const purchaseDialogVisible = await page.locator(".modal-dialog").filter({ hasText: "采购入库需使用采购收货单" }).isVisible().catch(() => false);
	assert.equal(purchaseDialogVisible, true);
	result.assertions.push("采购入库提示使用采购收货单，避免丢失供应商和采购关联");
	await page.getByRole("button", { name: "否", exact: true }).click();
	await page.locator(".modal-dialog").waitFor({ state: "hidden" });
	await page.locator(".modal-backdrop").waitFor({ state: "detached" }).catch(() => {});

	await reason.selectOption({ label: "采购入库" });
	await page.getByRole("button", { name: "是", exact: true }).click();
	await page.waitForFunction(() => cur_frm?.doc?.doctype === "Purchase Receipt", null, { timeout: 15000 });
	assert.equal(await page.evaluate(() => cur_frm.doc.doctype), "Purchase Receipt");
	result.assertions.push("确认采购入库后进入采购收货单新建页");

	await page.goto(`${baseUrl}/app/stock-entry/new-stock-entry-1`, { waitUntil: "domcontentloaded" });
	await page.waitForTimeout(2500);
	await page.locator('[data-fieldname="custom_stock_direction"] select').selectOption({ label: "入库" });
	await page.locator('[data-fieldname="custom_stock_reason"] select').selectOption({ label: "生产退料" });

	const hiddenOnNew = await page.evaluate(() => {
		const isVisible = (fieldname) => Boolean(cur_frm.fields_dict[fieldname]?.$wrapper?.is(":visible"));
		return {
			stockEntryTypeVisible: isVisible("stock_entry_type"),
			namingSeriesVisible: isVisible("naming_series"),
			historySectionVisible: isVisible("custom_stock_history_section"),
			legacyOutboundVisible: isVisible("custom_excel_outbound_no"),
			missingFields: ["stock_entry_type", "custom_stock_history_section", "custom_excel_outbound_no"].filter(
				(fieldname) => !cur_frm.fields_dict[fieldname],
			),
		};
	});
	assert.equal(hiddenOnNew.stockEntryTypeVisible, false);
	assert.equal(hiddenOnNew.namingSeriesVisible, false);
	assert.equal(hiddenOnNew.historySectionVisible, false);
	assert.equal(hiddenOnNew.legacyOutboundVisible, false);
	result.assertions.push("新建手工单据隐藏底层库存类型、编号模板和历史导入字段");

	await page.locator(".alert, .toast-message").evaluateAll((elements) => elements.forEach((element) => element.remove()));
	await page.screenshot({ path: screenshotDesktop, fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.waitForTimeout(500);
	await page.evaluate(() => frappe.app.sidebar.close());
	result.viewport.mobile = await page.evaluate(() => ({
		width: document.documentElement.clientWidth,
		scrollWidth: document.documentElement.scrollWidth,
		horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
	}));
	assert.equal(result.viewport.mobile.horizontalOverflow, false);
	result.assertions.push("移动端无横向溢出，字段可在窄屏正常排版");
	await page.locator(".alert, .toast-message").evaluateAll((elements) => elements.forEach((element) => element.remove()));
	await page.screenshot({ path: screenshotMobile, fullPage: true });

	result.known_site_issues = runtimeIssues.filter((issue) =>
		issue.includes("custom_filters/public/js/naming_series_i18n.js") ||
		issue.includes("Cannot read properties of null (reading 'join')") ||
		issue.includes("play() failed because the user didn't interact with the document first")
	);
	const unexpectedIssues = runtimeIssues.filter((issue) => !result.known_site_issues.includes(issue));
	assert.deepEqual(unexpectedIssues, []);
	result.status = "passed";
	result.observations.push("页面首屏将方向、原因和系统单号集中在出入库信息区，历史字段不干扰新建流程。");
} catch (error) {
	result.error = error instanceof Error ? error.stack : String(error);
	throw error;
} finally {
	await fs.writeFile(resultPath, JSON.stringify(result, null, 2) + "\n");
	await browser.close();
}

console.log(JSON.stringify(result, null, 2));
