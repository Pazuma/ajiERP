import fs from "node:fs";
import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const evidenceDir = "/workspace/docs/china-finance-test-evidence";
const marker = `CF-CONNECT-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
const resultFile = `${evidenceDir}/voucher-flow.json`;
const screenshot = `${evidenceDir}/voucher-flow.png`;
fs.mkdirSync(evidenceDir, { recursive: true });

const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const result = { marker, company: "阿基视觉（东莞）", amount: 100, steps: [] };

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto(`${baseUrl}/desk/china-new-voucher`, { waitUntil: "domcontentloaded" });
	await page.locator(".cf-manual-voucher").waitFor({ state: "visible", timeout: 20000 });

	const rows = page.locator(".cf-entry-grid tbody tr");
	await rows.nth(0).locator(".cf-remarks").fill(marker);
	await rows.nth(0).locator(".cf-account input").fill("100201 - 基本存款账户 - T");
	await rows.nth(0).locator(".cf-debit-input").fill("100.00");
	await rows.nth(1).locator(".cf-remarks").fill(marker);
	await rows.nth(1).locator(".cf-account input").fill("6001 - 主营业务收入 - T");
	await rows.nth(1).locator(".cf-credit-input").fill("100.00");
	result.steps.push({ name: "凭证录入与借贷平衡", passed: (await page.locator(".cf-voucher-balance").innerText()).includes("平衡") });

	await page.getByRole("button", { name: "保存并记账" }).click();
	await page.waitForURL(/\/desk\/journal-entry\//, { timeout: 30000 });
	result.journal_entry = decodeURIComponent(page.url().split("/").pop());
	result.steps.push({ name: "Journal Entry 提交", passed: Boolean(result.journal_entry) });

	result.database = await page.evaluate(async ({ marker, journalEntry }) => {
		const response = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "China Accounting Voucher",
				filters: { source_doctype: "Journal Entry", source_name: journalEntry, source_event: "Posting" },
				fields: ["name", "statutory_number", "docstatus", "total_debit", "total_credit"],
				limit_page_length: 1,
			},
		});
		const voucher = response.message?.[0] || null;
		const gl = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "GL Entry",
				filters: { voucher_type: "Journal Entry", voucher_no: journalEntry, is_cancelled: 0 },
				fields: ["name", "account", "debit", "credit", "remarks"],
				limit_page_length: 20,
			},
		});
		let assignment = [];
		if (voucher) {
			assignment = (await frappe.call({
				method: "frappe.client.get_list",
				args: { doctype: "China Cash Flow Assignment", filters: { china_accounting_voucher: voucher.name }, fields: ["name", "status", "docstatus"], limit_page_length: 5 },
			})).message || [];
		}
		return { marker, voucher, gl_entries: gl.message || [], cash_flow_assignments: assignment };
	}, { marker, journalEntry: result.journal_entry });
	result.steps.push({ name: "中国会计凭证快照", passed: Boolean(result.database.voucher) });
	result.steps.push({ name: "总账分录", passed: result.database.gl_entries.length === 2 });
	result.steps.push({ name: "现金流指定未自动生成（启用日期为空）", passed: result.database.cash_flow_assignments.length === 0 });
	await page.screenshot({ path: screenshot, fullPage: true });
	result.screenshot = screenshot;
} catch (error) {
	result.error = { name: error.name, message: error.message };
	await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
} finally {
	await browser.close();
	fs.writeFileSync(resultFile, JSON.stringify(result, null, 2));
}

console.log(JSON.stringify(result, null, 2));
if (result.error || result.steps.some((step) => !step.passed)) process.exitCode = 1;
