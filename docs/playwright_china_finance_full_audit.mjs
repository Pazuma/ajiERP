import fs from "node:fs";
import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const evidenceDir = "/workspace/docs/china-finance-test-evidence";
const resultFile = `${evidenceDir}/page-audit.json`;
const summaryFile = `${evidenceDir}/page-audit-summary.json`;
const browserPath = "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";

const doctypes = [
	"China Accounting Policy", "China Accounting Voucher", "China Accounting Voucher Entry",
	"China Cash Equivalent Scope", "China Cash Flow Assignment", "China Cash Flow Assignment Item",
	"China Closing Check", "China Closing Run", "China Electronic Document", "China Finance Settings",
	"China Financial Statement Mapping", "China Financial Statement Notes",
	"China Financial Statement Reclassification Rule", "China Financial Statement Row",
	"China Financial Statement Template", "China Input Tax Deduction Batch", "China Input Tax Deduction Item",
	"China Invoice Control Rule", "China Prior Period Error Adjustment", "China Prior Period Error Adjustment Line",
	"China Purchase Reconciliation Rule", "China Reconciliation Difference", "China Reconciliation Line",
	"China Reconciliation Scope", "China Reconciliation Statement", "China Report Snapshot",
	"China Sales Invoice Control", "China Sales Settlement", "China Sales Settlement Item",
	"China Sales Settlement Rule", "China Tax Account Mapping", "China Tax Integration Call",
	"China Tax Invoice", "China Tax Invoice Allocation", "China Tax Invoice Item",
	"China Tax Invoice Recognition", "China Tax Invoice Request", "China Tax Invoice Request Item",
	"China Voucher Recycle Bin Item", "China Voucher Sequence", "China Voucher Sync Issue",
];

const reports = [
	"China AR AP Ledger Reconciliation", "China Business Document Chain", "China Daily Ledger",
	"China Financial Statements", "China Output Invoice Reconciliation", "China Purchase Document Chain",
	"China Purchase Reconciliation", "China VAT Ledger", "China VAT Return Worksheet",
	"China Voucher Integrity", "China Voucher Ledger",
];

const slug = (value) => value.toLowerCase().replaceAll(" ", "-").replaceAll("/", "-");

function classifyFailure(event) {
	if (event.type === "pageerror") return { category: "frontend-runtime", severity: "P1" };
	if (event.type === "console") return { category: "browser-console", severity: "P2" };
	if (event.status >= 500) return { category: "server", severity: "P0" };
	if (event.url.includes("/api/method/") || event.url.includes("/api/resource/")) return { category: "api", severity: "P1" };
	if (event.url.includes("/assets/")) return { category: "asset", severity: "P2" };
	return { category: "route-or-other", severity: "P2" };
}

function failureKey(event) {
	return [event.type, event.method || "GET", event.status || "", event.url, event.message || ""].join("|");
}

function summarizeFailures(events) {
	const unique = new Map();
	for (const event of events) {
		const key = failureKey(event);
		const existing = unique.get(key);
		if (existing) {
			existing.occurrenceCount += 1;
			continue;
		}
		unique.set(key, { ...event, ...classifyFailure(event), occurrenceCount: 1, firstSeenPage: event.page || event.url });
	}
	const failures = [...unique.values()];
	return {
		eventCount: events.length,
		uniqueCount: failures.length,
		byCategory: Object.groupBy(failures, ({ category }) => category),
		bySeverity: Object.groupBy(failures, ({ severity }) => severity),
		failures,
	};
}
fs.mkdirSync(evidenceDir, { recursive: true });

const browser = await chromium.launch({ headless: true, executablePath: browserPath, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const globalErrors = [];
page.on("pageerror", (error) => globalErrors.push({ type: "pageerror", url: page.url(), message: error.message }));
page.on("console", (message) => {
	if (message.type() === "error") globalErrors.push({ type: "console", url: page.url(), message: message.text() });
});
page.on("response", (response) => {
	if (response.status() >= 400) globalErrors.push({ type: "http", method: response.request().method(), resourceType: response.request().resourceType(), url: response.url(), status: response.status(), page: page.url() });
});

await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
await page.locator("#login_email").fill("Administrator");
await page.locator("#login_password").fill("admin");
await page.locator("button.btn-login").click();
await page.waitForURL(/\/(app|desk)/, { timeout: 20000 });

const metadata = await page.evaluate(async ({ doctypes, reports }) => {
	const call = async (method, args) => {
		const response = await fetch(`/api/method/${method}`, {
			method: "POST", headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": window.frappe.csrf_token },
			body: JSON.stringify(args),
		});
		return { status: response.status, body: await response.json().catch(() => ({})) };
	};
	const result = { doctypes: {}, reports: {} };
	for (const doctype of doctypes) {
		const meta = await call("frappe.client.get", { doctype: "DocType", name: doctype });
		const doc = meta.body.message || {};
		let count = null;
		if (!doc.istable && !doc.issingle) {
			const counted = await call("frappe.client.get_count", { doctype });
			count = counted.body.message ?? null;
		}
		result.doctypes[doctype] = { installed: meta.status === 200, istable: Boolean(doc.istable), issingle: Boolean(doc.issingle), count };
	}
	for (const report of reports) {
		const response = await call("frappe.client.get", { doctype: "Report", name: report });
		result.reports[report] = { installed: response.status === 200, report_type: response.body.message?.report_type || null };
	}
	return result;
}, { doctypes, reports });

const pages = [];
for (const [doctype, meta] of Object.entries(metadata.doctypes)) {
	if (!meta.installed || meta.istable) {
		pages.push({ kind: "doctype", name: doctype, skipped: true, reason: !meta.installed ? "not installed" : "child table" });
		continue;
	}
	const path = meta.issingle ? `/desk/${slug(doctype)}` : `/desk/${slug(doctype)}/view/list`;
	const errorStart = globalErrors.length;
	let loadError = null;
	try {
		await page.goto(`${baseUrl}${path}`, { waitUntil: "domcontentloaded", timeout: 20000 });
		await page.waitForTimeout(800);
	} catch (error) { loadError = error.message; }
	pages.push({ kind: "doctype", name: doctype, path, finalUrl: page.url(), title: await page.title(), loadError, errors: globalErrors.slice(errorStart) });
}

for (const report of reports) {
	const path = `/desk/query-report/${encodeURIComponent(report)}`;
	const errorStart = globalErrors.length;
	let loadError = null;
	try {
		await page.goto(`${baseUrl}${path}`, { waitUntil: "domcontentloaded", timeout: 20000 });
		await page.waitForTimeout(1200);
	} catch (error) { loadError = error.message; }
	pages.push({ kind: "report", name: report, path, finalUrl: page.url(), title: await page.title(), loadError, errors: globalErrors.slice(errorStart) });
}

await page.screenshot({ path: `${evidenceDir}/last-page.png`, fullPage: true });
fs.writeFileSync(resultFile, JSON.stringify({ generatedAt: new Date().toISOString(), metadata, pages, globalErrors }, null, 2));
const summary = summarizeFailures(globalErrors);
fs.writeFileSync(summaryFile, JSON.stringify({ generatedAt: new Date().toISOString(), ...summary }, null, 2));
console.log(JSON.stringify({ resultFile, summaryFile, doctypes: doctypes.length, reports: reports.length, visited: pages.filter((row) => !row.skipped).length, errors: summary.eventCount, uniqueErrors: summary.uniqueCount }, null, 2));
await browser.close();
