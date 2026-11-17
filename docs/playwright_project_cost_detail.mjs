import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

try {
	const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
	const errors = [];
	page.on("pageerror", (error) => errors.push(error.message));
	await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, { timeout: 15000 });
	await page.goto("http://127.0.0.1:8300/app/project/PROJ-0003", {
		waitUntil: "domcontentloaded",
	});
	await page.waitForTimeout(3000);
	await page.getByText("成本核算", { exact: true }).click();
	await page.waitForTimeout(1000);
	const result = await page.evaluate(() => ({
		fields: [
			"custom_project_cost_details_section",
			"custom_project_cost_details",
			"custom_project_cost_detail_total",
		].map((fieldname) => ({
			fieldname,
			in_meta: Boolean(frappe.get_meta("Project").fields.find((field) => field.fieldname === fieldname)),
			in_form: Boolean(cur_frm?.fields_dict?.[fieldname]),
			visible: Boolean(cur_frm?.fields_dict?.[fieldname]?.wrapper?.offsetParent),
		})),
		body_has_cost_detail: document.body.innerText.includes("成本明细"),
	}));
	console.log(JSON.stringify({ ...result, errors }, null, 2));
	await page.screenshot({
		path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_project_cost_detail.png",
		fullPage: true,
	});
} finally {
	await browser.close();
}
