import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";

const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
try {
	const page = await browser.newPage({acceptDownloads: true});
	await page.goto("http://127.0.0.1:8300/login");
	await page.locator("#login_email").fill(process.env.EXPORT_TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.EXPORT_TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/);
	await page.goto("http://127.0.0.1:8300/app/item");
	await page.waitForFunction(() => window.cur_list?.doctype === "Item" && cur_list.data?.length);
	await page.getByRole("button", {name: "导出物料信息", exact: true}).waitFor();
	await page.locator(".list-row-container .list-row-checkbox").first().check();
	for (const entry of ["button", "native"]) {
		const pending = page.waitForEvent("download");
		if (entry === "button") await page.getByRole("button", {name: "导出物料信息", exact: true}).click();
		else await page.evaluate(() => {
			const label = __("Export", null, "Button in list view actions menu");
			cur_list.get_actions_menu_items().find(item => item.label === label).action();
		});
		const download = await pending;
		if (!download.suggestedFilename().endsWith(".xlsx")) throw new Error("Expected XLSX");
		await download.saveAs(`/tmp/item-information-${entry}.xlsx`);
		console.log(JSON.stringify({entry, filename: download.suggestedFilename(), error: await download.failure()}));
	}
} finally {
	await browser.close();
}
