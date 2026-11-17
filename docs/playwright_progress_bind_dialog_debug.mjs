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
	await page.goto("http://127.0.0.1:8300/app/purchase-order/new-purchase-order", { waitUntil: "networkidle" });
	await page.waitForFunction(() => window.cur_frm && cur_frm.doctype === "Purchase Order");
	await page.locator('[id="page-Purchase Order"]').getByRole("button", { name: "项目" }).click();
	await page.getByText("绑定项目进度节点", { exact: true }).click();
	const dialog = page.locator(".modal-dialog:visible").last();
	await dialog.waitFor({ state: "visible", timeout: 15000 });
	console.log(await dialog.innerHTML());
} finally {
	await browser.close();
}
