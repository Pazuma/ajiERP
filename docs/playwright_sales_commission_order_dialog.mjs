// Read-only browser acceptance: never saves real business records.
import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";
const browser = await chromium.launch({headless:true, executablePath:"/usr/bin/chromium-headless-shell", args:["--no-sandbox"]});
const page = await browser.newPage();
const errors=[];
page.on("pageerror", e=>{errors.push(e.message);console.error(e.message);});
try {
	const base=process.env.COMMISSION_TEST_URL || "http://127.0.0.1:8300";
	await page.goto(`${base}/login`);
	await page.locator("#login_email").fill(process.env.COMMISSION_TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.COMMISSION_TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/);
	await page.goto(`${base}/app/sales-commission-orders`);
	await page.waitForFunction(()=>window.frappe?.pages["sales-commission-orders"]?.on_page_load && document.querySelector('[data-fieldname="company"]'));
	const fixture=await page.evaluate(async()=>{
		const orders=(await frappe.call({method:"frappe.client.get_list",args:{doctype:"Sales Order",filters:{docstatus:1},fields:["name","company"],limit_page_length:1}})).message;
		return orders[0];
	});
	if(fixture){
		await page.evaluate(company=>frappe.pages["sales-commission-orders"].page.fields_dict.company.set_value(company),fixture.company);
		await page.locator(".commission-open").first().waitFor();
		await page.locator(".commission-open").first().click();
		await page.locator(".modal:visible").waitFor();
		if(!await page.locator('.modal:visible [data-fieldname="sales_people"]').count()) throw Error("Missing allocation table");
		const overview=page.locator('.modal:visible [data-fieldname="order_summary"]');
		await overview.getByText("订单概览（只读）").waitFor();
		if(!await overview.locator("table").count()) throw Error("Missing order item table");
		if(!(await overview.innerText()).includes("订单含税总额")) throw Error("Missing order total");
		console.log("PASS order list and allocation dialog");
	} else console.log("SKIP dialog: no submitted order");
	const sidebar=await page.evaluate(()=>{
		const source=frappe.boot.workspace_sidebar_item?.selling;
		const items=source?.items || source || [];
		const index=items.findIndex(r=>r.link_to==="sales-commission-orders");
		return {entry:items[index],previous:items[index-1]?.link_to,site:frappe.boot.sitename,links:items.map(r=>r.link_to)};
	});
	if(!sidebar.entry || sidebar.entry.child || sidebar.previous!=="Sales Invoice") throw Error(`Sidebar placement incorrect: ${JSON.stringify(sidebar)}`);
	console.log("PASS top-level sidebar entry after Sales Invoice");
	if(errors.length)throw Error(errors.join("; "));
	console.log("PASS no browser JavaScript errors");
}finally{await browser.close();}
