import fs from "node:fs";
import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = process.env.CF_BASE_URL || "http://aki_test.localhost:8300";
const evidenceDir = "/workspace/docs/china-finance-test-evidence";
const resultFile = `${evidenceDir}/manual-voucher-lifecycle.json`;
const screenshot = `${evidenceDir}/manual-voucher-lifecycle.png`;
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH
	|| "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
const allowDraftWrite = process.env.CF_ALLOW_DRAFT_WRITE === "1";

fs.mkdirSync(evidenceDir, { recursive: true });

const result = {
	base_url: baseUrl,
	writes_business_documents: false,
	writes_draft_data: allowDraftWrite,
	steps: [],
	console_errors: [],
	page_errors: [],
	http_errors: [],
};
let browser;
let page;

function assert(condition, message) {
	if (!condition) throw new Error(message);
}

async function call(method, args) {
	return page.evaluate(async ({ method, args }) => {
		const response = await frappe.call({ method, args });
		return response.message;
	}, { method, args });
}

try {
	browser = await chromium.launch({ headless: true, executablePath, args: ["--no-sandbox"] });
	page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
	page.on("console", (message) => {
		if (message.type() === "error") result.console_errors.push(message.text());
	});
	page.on("pageerror", (error) => result.page_errors.push(error.message));
	page.on("response", (response) => {
		if (response.status() >= 400) result.http_errors.push({ status: response.status(), url: response.url() });
	});

	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill(process.env.CF_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.CF_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto(`${baseUrl}/desk/china-new-voucher`, { waitUntil: "domcontentloaded" });
	await page.locator(".cf-manual-voucher").waitFor({ state: "visible", timeout: 20000 });

	const voucherWords = await page.locator(".cf-voucher-word option").allTextContents();
	assert(voucherWords.length >= 1, "voucher word selector must have at least one option");
	result.steps.push({ name: "凭证字选择器已加载", passed: true, words: voucherWords });

	const status = await page.locator(".cf-posting-status").innerText();
	assert(status.includes("期间状态"), "posting-period pre-check should be displayed");
	result.steps.push({ name: "关闭/冻结期间预检已显示", passed: true, status });

	await page.locator(".cf-load-draft").click();
	result.steps.push({ name: "我的草稿入口可点击", passed: true });
	await page.keyboard.press("Escape");

	if (allowDraftWrite) {
		const debitAccount = process.env.CF_DEBIT_ACCOUNT;
		const creditAccount = process.env.CF_CREDIT_ACCOUNT;
		assert(debitAccount && creditAccount, "CF_ALLOW_DRAFT_WRITE=1 requires CF_DEBIT_ACCOUNT and CF_CREDIT_ACCOUNT");

		const rows = page.locator(".cf-entry-grid tbody tr");
		await rows.nth(0).locator(".cf-remarks").fill("PW-手工凭证草稿连通性测试");
		await rows.nth(0).locator(".cf-account input").fill(debitAccount);
		await rows.nth(0).locator(".cf-debit-input").fill("100.00");
		await rows.nth(1).locator(".cf-remarks").fill("PW-手工凭证草稿连通性测试");
		await rows.nth(1).locator(".cf-account input").fill(creditAccount);
		await rows.nth(1).locator(".cf-credit-input").fill("100.00");
		await page.locator(".cf-attachment-count").fill("3");
		await page.locator(".cf-save-draft").click();
		await page.locator(".alert-message").filter({ hasText: "草稿已保存" }).waitFor({ timeout: 15000 });
		const draftName = await page.locator(".alert-message").innerText();
		const match = draftName.match(/CMVD-\d+/);
		assert(match, "saved draft identifier should be shown");

		const draft = await call("china_finance.services.manual_voucher.get_manual_voucher_draft", { name: match[0] });
		assert(draft.attachment_count === 3, "attachment count should persist on the draft");
		assert(draft.entries.length === 2, "two draft entries should persist");
		assert(!draft.source_journal_entry, "saving a draft must not create Journal Entry");
		await call("china_finance.services.manual_voucher.cancel_manual_voucher_draft", { name: match[0] });
		result.steps.push({ name: "受控草稿保存、读取、取消", passed: true, draft: match[0] });
	} else {
		result.steps.push({
			name: "受控草稿写入",
			passed: true,
			skipped: true,
			reason: "默认不写入；设置 CF_ALLOW_DRAFT_WRITE=1 并提供两个末级科目后执行。",
		});
	}

	await page.screenshot({ path: screenshot, fullPage: true });
	result.screenshot = screenshot;
} catch (error) {
	result.error = { name: error.name, message: error.message };
} finally {
	if (browser) await browser.close();
	fs.writeFileSync(resultFile, JSON.stringify(result, null, 2));
}

console.log(JSON.stringify(result, null, 2));
if (result.error || result.steps.some((step) => !step.passed)) process.exitCode = 1;
