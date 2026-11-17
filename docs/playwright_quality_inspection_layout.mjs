// Layout acceptance only: new unsaved documents, no save/submit calls.
import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";
const browser = await chromium.launch({ headless: true, executablePath: "/usr/bin/chromium-headless-shell", args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("pageerror", e => errors.push(e.message));
try {
	await page.goto("http://127.0.0.1:8300/login");
	await page.locator("#login_email").fill(process.env.TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/);
	await page.goto("http://127.0.0.1:8300/app/quality-inspection/new-quality-inspection");
	await page.waitForFunction(() => window.cur_frm?.doctype === "Quality Inspection" && document.querySelector(".akv-quality-inspection-layout"));
	const state = await page.evaluate(async () => {
		const frm = cur_frm;
		const options = frm.fields_dict.reference_type.df.options.split("\n");
		if (options.includes("Job Card") || !options.includes("Work Order")) throw Error("Work Order reference options incorrect");
		const visible = name => !!frm.fields_dict[name]?.$wrapper.is(":visible");
		const sections = Object.values(frm.layout.sections_dict).filter(s => s.wrapper.is(":visible")).map(s => ({ name: s.df.fieldname, label: s.df.label, width: s.body.width(), columns: s.columns.length }));
		if (visible("reference_name")) throw Error("Empty reference selector should be hidden");
		await frm.set_value("reference_type", "Work Order");
		if (visible("reference_name") || !visible("custom_work_order")) throw Error("Duplicate Work Order selector visibility incorrect");
		const orders = await frappe.db.get_list("Work Order", { filters: { company: frm.doc.company, docstatus: ["!=", 2] }, fields: ["name", "production_item"], limit: 1 });
		if (!orders.length) throw Error("No Work Order available for read-only acceptance");
		await frm.set_value("custom_work_order", orders[0].name);
		if (frm.doc.reference_name !== orders[0].name || frm.doc.item_code !== orders[0].production_item) throw Error("Visible Work Order selection did not synchronize");
		await frm.set_value("custom_work_order", "");
		if (frm.doc.reference_name) throw Error("Cleared Work Order left a hidden reference");
		await frm.set_value("reference_type", "Stock Entry");
		if (!visible("reference_name")) throw Error("Reference selector did not appear");
		await frm.set_value("inspection_type", "In Process");
		if (!visible("custom_work_order")) throw Error("Production source unavailable");
		await frm.set_value("custom_rejected_qty", 1);
		if (!frm.layout.sections_dict.custom_qi_reason_section.wrapper.is(":visible")) throw Error("Rejection reason did not appear");
		await frm.set_value("custom_rejection_reason", "布局检查，不保存");
		await frm.set_value("custom_rejected_qty", 0);
		if (!visible("custom_rejection_reason")) throw Error("Existing reason was hidden");
		await frm.set_value("custom_rejection_reason", "");
		return { sections, other_collapsed: frm.layout.sections_dict.custom_qi_other_section.is_collapsed(), description_collapsed: frm.layout.sections_dict.custom_qi_description_section.is_collapsed() };
	});
	if (!state.other_collapsed || !state.description_collapsed) throw Error("Low-frequency sections are not collapsed");
	console.log(JSON.stringify(state));
	await page.screenshot({ path: "/workspace/docs/quality-inspection-layout-desktop.png", fullPage: true });
	await page.evaluate(async () => {
		// Use an unsaved local branch fixture; no link fetch or database writes.
		cur_frm.doc.custom_purchase_order = "LAYOUT-UNSAVED-PO";
		await cur_frm.script_manager.trigger("refresh");
		if (!cur_frm.fields_dict.custom_purchase_quality_items.$wrapper.is(":visible")) throw Error("Purchase quality grid hidden");
		if (cur_frm.layout.sections_dict.custom_qi_quantity_section.wrapper.is(":visible")) throw Error("Duplicate purchase quantity section");
		cur_frm.doc.custom_purchase_order = null;
		await cur_frm.script_manager.trigger("refresh");
	});
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: "/workspace/docs/quality-inspection-layout-mobile.png", fullPage: true });
	const overflow = await page.evaluate(() => {
		const root = document.querySelector(".akv-quality-inspection-layout");
		return root.scrollWidth > root.clientWidth + 2;
	});
	if (overflow) throw Error("Form overflows mobile viewport");
	if (errors.length) throw Error(errors.join("; "));
	console.log("PASS grouped sections, source conditions, rejection reason, collapsible settings and mobile layout; no business writes");
} finally {
	await browser.close();
}
