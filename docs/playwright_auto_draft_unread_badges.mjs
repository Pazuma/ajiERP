import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = process.env.BASE_URL || "http://aki_test.localhost:8300";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH
	|| "/usr/bin/chromium-headless-shell";
const browser = await chromium.launch({ headless: true, executablePath, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const result = { base_url: baseUrl, lists: [], console_errors: [], page_errors: [], http_errors: [] };

page.on("console", (message) => {
	if (message.type() === "error") result.console_errors.push(message.text());
});
page.on("pageerror", (error) => result.page_errors.push(error.message));
page.on("response", (response) => {
	if (response.status() >= 400) result.http_errors.push({ status: response.status(), url: response.url() });
});

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill(process.env.FRAPPE_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.FRAPPE_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });

	for (const [doctype, route] of [["Work Order", "work-order"], ["Delivery Note", "delivery-note"]]) {
		await page.goto(`${baseUrl}/app/${route}`, { waitUntil: "domcontentloaded" });
		await page.waitForTimeout(1600);
		const listState = await page.evaluate((doctype) => {
			const menu = [...document.querySelectorAll(".sidebar-item-container")]
				.find((node) => node.getAttribute("item-name") === (doctype === "Work Order" ? "生产工单" : "送货单"));
			const tabs = [...document.querySelectorAll(".desk-page .form-tabs, .navbar .nav-item, .page-head")];
			return {
			route: frappe.get_route(),
			badge_script_loaded: (frappe.boot?.doctype_js?.[doctype] || "").includes("auto_draft_read_badge"),
			red_dot_count: document.querySelectorAll(".auto-draft-unread-dot").length,
			red_dot_rows: [...document.querySelectorAll(".auto-draft-unread-dot")].map((dot) => ({
				text: dot.closest(".list-row-container")?.innerText || dot.closest(".list-row")?.innerText || "",
			})),
			sidebar_dot_count: menu?.querySelectorAll(".auto-fulfilment-badge").length || 0,
			sidebar_dot_inline: menu?.querySelector(".auto-fulfilment-badge")
				? getComputedStyle(menu.querySelector(".auto-fulfilment-badge")).position === "static"
				: false,
			topbar_dot_count: tabs.reduce((sum, node) => sum + node.querySelectorAll(".auto-fulfilment-badge").length, 0),
			listview_loaded: Boolean(frappe.views?.ListView && frappe.listview_settings?.[doctype]),
			};
		}, doctype);
		result.lists.push({ doctype, ...listState });
		if (doctype === "Delivery Note" && listState.red_dot_count) {
			const row = page.locator(".auto-draft-unread-dot").first().locator("xpath=ancestor::*[contains(@class,'list-row-container') or contains(@class,'list-row')][1]");
			const documentLink = row.locator('a[href*="/app/delivery-note/"]').first();
			result.delivery_note_name = await documentLink.getAttribute("href");
			await documentLink.click();
			await page.waitForTimeout(1800);
			result.opened_document_route = await page.evaluate(() => frappe.get_route());
			await page.goto(`${baseUrl}/app/delivery-note`, { waitUntil: "domcontentloaded" });
			await page.waitForTimeout(1400);
			result.delivery_note_red_dots_after_open = await page.locator(".auto-draft-unread-dot").count();
		}
	}

	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
}
