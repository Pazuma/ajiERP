import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = "http://127.0.0.1:8300";
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const consoleErrors = [];
const responseErrors = [];
page.on("console", (message) => message.type() === "error" && consoleErrors.push(message.text()));
page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("response", (response) => response.status() >= 400 && responseErrors.push({ status: response.status(), url: response.url() }));

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto(`${baseUrl}/app/project/PROJ-0006`, { waitUntil: "domcontentloaded" });
	await page.waitForSelector('[data-fieldname="custom_progress_section"]', { state: "attached", timeout: 20000 });
	const tabInfo = await page.evaluate(() => Array.from(document.querySelectorAll('[role="tab"], .nav-tabs a, .form-tabs a')).map((node) => ({ text: node.textContent.trim(), fieldname: node.dataset.fieldname, href: node.getAttribute("href") })));
	const progressTab = page.locator('[role="tab"][data-fieldname="custom_progress_tab"]');
	if (await progressTab.count()) await progressTab.click();
	await page.waitForTimeout(1500);
	const result = await page.evaluate(() => ({
		url: location.href,
		fields: ["custom_progress_section", "custom_progress_template", "custom_expected_progress", "custom_actual_process_progress", "custom_progress_variance", "custom_progress_health", "custom_project_progress_items"].map((fieldname) => ({
			fieldname,
			exists: Boolean(document.querySelector(`[data-fieldname="${fieldname}"]`)),
			visible: Boolean(document.querySelector(`[data-fieldname="${fieldname}"]`)?.offsetParent),
		})),
		buttons: Array.from(document.querySelectorAll("button")).map((button) => button.innerText.trim()).filter((text) => /进度模板|同步进度|手工更新/.test(text)),
		progressMenuItems: Array.from(document.querySelectorAll("button, a, .dropdown-item")).map((node) => node.textContent.trim()).filter((text) => /应用进度模板|保存为进度模板|重新同步进度|手工更新节点/.test(text)),
		customButtonKeys: Object.keys(window.cur_frm?.custom_buttons || {}),
		formScriptHandlers: Object.keys(frappe.ui.form.handlers?.Project || {}),
		health: {
			value: window.cur_frm?.doc?.custom_progress_health,
			dfHidden: window.cur_frm?.fields_dict?.custom_progress_health?.df?.hidden,
			wrapperDisplay: window.cur_frm?.fields_dict?.custom_progress_health?.wrapper && getComputedStyle(window.cur_frm.fields_dict.custom_progress_health.wrapper).display,
		},
		progressGrid: (() => {
			const grid = document.querySelector('[data-fieldname="custom_project_progress_items"]');
			const section = document.querySelector('[data-fieldname="custom_progress_section"]');
			const hierarchy = [];
			let node = grid;
			while (node && node !== section.parentElement) {
				hierarchy.push({ className: node.className, width: Math.round(node.getBoundingClientRect().width) });
				node = node.parentElement;
			}
			return {
				headings: Array.from(grid?.querySelectorAll('.grid-heading-row .static-area') || []).map((node) => node.textContent.trim()).filter(Boolean),
				width: Math.round(grid?.getBoundingClientRect().width || 0),
				sectionWidth: Math.round(section?.getBoundingClientRect().width || 0),
				hierarchy,
			};
		})(),
		standardFieldWidth: Math.round(document.querySelector('[data-fieldname="custom_progress_template"]')?.getBoundingClientRect().width || 0),
		progressColumnWidth: Math.round(document.querySelector('[data-fieldname="custom_progress_template"]')?.closest('.form-column')?.getBoundingClientRect().width || 0),
		gridRight: Math.round(document.querySelector('[data-fieldname="custom_project_progress_items"]')?.getBoundingClientRect().right || 0),
		mainRight: Math.round(document.querySelector('.layout-main-section')?.getBoundingClientRect().right || 0),
		ancestors: (() => {
			let node = document.querySelector('[data-fieldname="custom_progress_section"]');
			const values = [];
			while (node) {
				values.push({ tag: node.tagName, className: node.className, fieldname: node.dataset?.fieldname, display: getComputedStyle(node).display });
				node = node.parentElement;
			}
			return values.slice(0, 8);
		})(),
		resources: performance.getEntriesByType("resource").map((entry) => entry.name).filter((name) => /project.*(__js|js)/i.test(name)),
		panes: Array.from(document.querySelectorAll(".form-tab-content > .tab-pane")).map((pane, index) => ({ index, className: pane.className, display: getComputedStyle(pane).display, fields: Array.from(pane.querySelectorAll("[data-fieldname]")).slice(0, 8).map((node) => node.dataset.fieldname) })),
	}));
	await page.screenshot({ path: "/home/cst/frappe_docker/docs/project-progress-playwright.png", fullPage: true });
	console.log(JSON.stringify({ result, tabInfo, consoleErrors, responseErrors }, null, 2));
	const invisibleFields = result.fields.filter((field) => !field.visible && !(field.fieldname === "custom_progress_health" && !result.health.value));
	if (invisibleFields.length) throw new Error(`进度字段不可见: ${invisibleFields.map((field) => field.fieldname).join(", ")}`);
	if (result.progressMenuItems.length < 4) throw new Error(`进度操作按钮不完整: ${result.progressMenuItems.join(", ")}`);
	if (!result.progressGrid.headings.includes("实际完成时间") || !result.progressGrid.headings.includes("备注")) throw new Error(`进度表列不完整: ${result.progressGrid.headings.join(", ")}`);
	const gridRatio = result.progressGrid.width / result.progressGrid.sectionWidth;
	const fieldRatio = result.progressColumnWidth / result.progressGrid.sectionWidth;
	if (gridRatio < 0.6 || gridRatio > 0.75) throw new Error(`进度表宽度不符合蓝框比例: ${result.progressGrid.width}/${result.progressGrid.sectionWidth}`);
	if (fieldRatio < 0.3 || fieldRatio > 0.5) throw new Error(`普通进度字段宽度不符合红框比例: ${result.progressColumnWidth}/${result.progressGrid.sectionWidth}`);
	if (result.gridRight > result.mainRight) throw new Error(`进度表侵入右侧栏: ${result.gridRight}/${result.mainRight}`);
	if (consoleErrors.some((message) => message.includes("project__list_js"))) throw new Error("项目列表脚本仍存在运行时异常");
} finally {
	await browser.close();
}
