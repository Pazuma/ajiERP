import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = process.env.FRAPPE_BASE_URL || "http://127.0.0.1:8300";
const project = process.env.PROJECT_NAME || "PROJ-0007";
const browser = await chromium.launch({
	headless: true,
	executablePath: "/usr/bin/chromium-headless-shell",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill(process.env.FRAPPE_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.FRAPPE_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto(`${baseUrl}/app/project/${project}`, { waitUntil: "domcontentloaded" });
	await page.waitForSelector('[data-fieldname="custom_project_files_tab"]', { timeout: 20000 });
	await page.locator('[role="tab"][data-fieldname="custom_project_files_tab"]').click();
	await page.waitForSelector('[data-fieldname="custom_project_files_html"]', { state: "visible" });

	const result = await page.evaluate(() => ({
		tabs: Array.from(document.querySelectorAll('[role="tab"]')).map((node) => node.textContent.trim()),
		projectFilesVisible: Boolean(document.querySelector('[data-fieldname="custom_project_files_html"]')?.offsetParent),
		addButton: Array.from(document.querySelectorAll("button")).some((node) => node.textContent.trim() === "添加文件"),
		emptyText: document.querySelector(".project-files-empty")?.textContent.trim(),
		hiddenStorageTable: !document.querySelector('[data-fieldname="custom_project_files"]')?.offsetParent,
	}));

	if (!result.projectFilesVisible) throw new Error("项目文件列表不可见");
	if (!result.addButton) throw new Error("缺少添加文件按钮");
	if (!result.hiddenStorageTable) throw new Error("底层文件子表不应直接显示");
	if (!result.tabs.includes("成本核算") || !result.tabs.includes("流程进度")) {
		throw new Error(`既有项目页签不完整：${result.tabs.join(", ")}`);
	}

	const deleteButton = page.locator('.project-file-actions button[title="删除"]').first();
	if (await deleteButton.count()) {
		await page.evaluate(() => {
			window.__projectFileSaveCalled = false;
			window.cur_frm.save = async () => {
				window.__projectFileSaveCalled = true;
			};
		});
		await deleteButton.click();
		await page.locator(".modal:visible .btn-primary").click();
		await page.waitForFunction(() => window.__projectFileSaveCalled === true);
		const deletion = await page.evaluate(() => ({
			dirty: Boolean(window.cur_frm.doc.__unsaved),
			saveCalled: window.__projectFileSaveCalled,
		}));
		if (!deletion.dirty || !deletion.saveCalled) {
			throw new Error(`删除未触发表单保存：${JSON.stringify(deletion)}`);
		}
		await page.reload({ waitUntil: "domcontentloaded" });
	}

	await page.screenshot({ path: "docs/project-files-playwright.png", fullPage: true });
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
}
