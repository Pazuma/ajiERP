import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

try {
	const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
	await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });
	await page.goto("http://127.0.0.1:8300/app/project", { waitUntil: "networkidle" });
	await page.locator(".list-row-container").first().waitFor({ state: "visible", timeout: 15000 });
	await page.waitForTimeout(1000);
	const state = await page.evaluate(() => {
		const settings = frappe.listview_settings.Project || {};
		const listview = cur_list;
		const doc = listview?.data?.find((row) => row.project_name === "222" || row.name === "PROJ-0008");
		return {
			add_fields: settings.add_fields,
			has_marker: settings._client_akivision_project_progress,
			fields: listview?.fields,
			doc,
			indicator: doc && settings.get_indicator ? settings.get_indicator(doc) : null,
			script_names: Array.from(document.scripts).map((script) => script.src).filter((src) => src.includes("document_export_list") || src.includes("project_list")),
		};
	});
	console.log(JSON.stringify(state, null, 2));
} finally {
	await browser.close();
}
