// Read-only UI smoke check; opens unsaved forms and never creates business data.
import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";

const browser = await chromium.launch({headless: true, executablePath: process.env.COMMISSION_CHROMIUM || "/usr/bin/chromium-headless-shell", args: ["--no-sandbox"]});
const page = await browser.newPage();
const errors = [];
page.on("pageerror", error => errors.push(error.message));
try {
	const base = process.env.COMMISSION_TEST_URL || "http://127.0.0.1:8300";
	await page.goto(`${base}/login`);
	await page.locator("#login_email").fill(process.env.COMMISSION_TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.COMMISSION_TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/);
	for (const [doctype, route, field] of [
		["Sales Commission Sheet", "sales-commission-sheet", "basis_type"],
		["Sales Commission Receipt Allocation", "sales-commission-receipt-allocation", "verified_source_amount"],
		["Sales Commission Disbursement", "sales-commission-disbursement", "payment_reference"],
	]) {
		await page.goto(`${base}/app/${route}`);
		await page.waitForFunction(dt => window.cur_list?.doctype === dt, doctype);
		await page.evaluate(dt => frappe.new_doc(dt), doctype);
		await page.waitForFunction(dt => window.cur_frm?.doctype === dt && !cur_frm.is_loading, doctype);
		const found = await page.evaluate(name => !!cur_frm.fields_dict[name], field);
		if (!found) throw new Error(`Missing field ${doctype}.${field}`);
		console.log(`PASS list and new form: ${doctype}`);
	}
	await page.goto(`${base}/app/query-report/Sales%20Commission%20Summary`);
	await page.waitForFunction(() => window.frappe?.query_report?.report_name === "Sales Commission Summary" && frappe.query_report.get_filter("mode"));
	console.log("PASS commission report filters");
	if (errors.length) throw new Error(errors.join("; "));
} finally {
	await browser.close();
}
