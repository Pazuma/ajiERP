import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
const failedResponses = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => message.type() === "error" && errors.push(message.text()));
page.on("response", (response) => response.status() >= 400 && failedResponses.push({ status: response.status(), url: response.url() }));

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	const results = [];
	for (const [report, expected] of [
		["Workshop Virtual Warehouse Inventory", ["物料编码", "实际数量", "仓库"]],
		["Finished Goods Inventory", ["成品编码", "实际库存", "成品仓"]],
	]) {
		await page.goto(`${baseUrl}/app/query-report/${encodeURIComponent(report)}`, { waitUntil: "domcontentloaded" });
		await page.waitForFunction(() => Boolean(window.frappe?.call), null, { timeout: 15000 });
		const apiResult = await page.evaluate((reportName) => frappe.call({
			method: "frappe.desk.query_report.run",
			args: { report_name: reportName, filters: {}, ignore_prepared_report: true },
		}), report);
		await page.waitForTimeout(500);
		const result = await page.evaluate(({ apiResult, expected }) => ({
			url: location.pathname,
			title: document.querySelector(".page-title, h3")?.textContent?.trim() || "",
			text: document.querySelector(".datatable")?.innerText || document.querySelector(".layout-main-section")?.innerText || "",
			columns: Array.from(document.querySelectorAll(".dt-cell__content, .list-row-head .ellipsis")).map((cell) => cell.textContent.trim()).filter(Boolean),
			error: document.querySelector(".msgprint")?.innerText || "",
			apiMessage: apiResult.message ? JSON.stringify(apiResult.message).slice(0, 500) : "",
			apiError: apiResult.exc || apiResult._server_messages || "",
			apiColumnsPresent: expected.every((label) => (apiResult.message?.columns || []).some((column) => column.label === label)),
			apiRows: apiResult.message?.result?.length ?? -1,
		}), { apiResult, expected });
		if (!result.url.includes(encodeURIComponent(report))) throw new Error(`${report}: report route did not load`);
		if (/Traceback|Internal Server Error|PermissionError/.test(result.text)) throw new Error(`${report}: report failed: ${result.text}`);
		if (!result.apiColumnsPresent) throw new Error(`${report}: report columns missing from API response`);
		if (result.apiRows !== 0) throw new Error(`${report}: expected fail-closed empty data without configured department warehouses, got ${result.apiRows}`);
		results.push({ report, ...result });
	}
	console.log(JSON.stringify({ results, errors, failedResponses }, null, 2));
	if (errors.some((error) => !error.includes("404 (NOT FOUND)"))) throw new Error(`Browser errors: ${errors.join("; ")}`);
} finally {
	await browser.close();
}
