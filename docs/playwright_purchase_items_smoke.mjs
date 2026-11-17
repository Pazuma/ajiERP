import playwright from '../development/erpnext.official/node_modules/playwright/index.js';

const browser = await playwright.chromium.launch({
	headless: true,
	executablePath: '/usr/bin/chromium-headless-shell',
	args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const context = await browser.newContext({
	viewport: { width: 1440, height: 900 },
});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
	await page.goto('http://aki_test.localhost:8300/login');
	await page.locator('#login_email').fill(process.env.TEST_USER || 'Administrator');
	await page.locator('#login_password').fill(process.env.TEST_PASSWORD || 'admin');
	await page.locator('button.btn-login').click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
	await page.goto('http://aki_test.localhost:8300/app/purchase-items');
	await page.waitForTimeout(2500);
	console.log(JSON.stringify({ url: page.url(), title: await page.title(), heading: await page.locator('h1, .page-title').allTextContents(), rows: await page.locator('.purchase-items-page tbody tr').count(), errors }, null, 2));
	await page.screenshot({ path: '/workspace/docs/purchase_items_desktop.png', fullPage: true });
	const firstRow = page.locator('.purchase-items-page tbody tr').first();
	if ((await firstRow.boundingBox()).height > 50) throw new Error('物料行未达到紧凑高度');
	const more = page.getByRole('button', { name: '加载更多', exact: true });
	if (await more.count() && await more.isEnabled()) {
		const before = await page.locator('.purchase-items-page [data-item]').count();
		await more.click();
		await page.waitForFunction(count => document.querySelectorAll('.purchase-items-page [data-item]').length > count, before);
	}
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: '/workspace/docs/purchase_items_mobile.png', fullPage: true });
	await page.setViewportSize({ width: 1440, height: 900 });
	if (await page.locator('.purchase-items-page tbody tr').count()) {
		await page.locator('.purchase-items-page .pi-select-row').first().check();
		if (await page.locator('.modal-dialog:visible').count()) throw new Error('勾选物料不应打开弹窗');
		await page.locator('.purchase-items-page .pi-open').first().click();
		const dialog = page.locator('.modal-dialog:visible');
		await dialog.getByText('供应商列表：').waitFor({ timeout: 10000 });
		for (const label of ['默认采购单位', '交期（天）', '最小起订量', '最近采购价', '安全库存', '安全库存备注', '由供应商交货（直运）', '供应商采购阶梯价']) {
			if (!await dialog.getByText(label, { exact: true }).count()) throw new Error(`缺少字段：${label}`);
		}
		if (await dialog.getByText('规则类型').count()) throw new Error('报价表单不应出现在供应商列表');
		await dialog.getByRole('button', { name: '添加供应商' }).click();
		await page.locator('.modal-dialog:visible').getByText('规则类型').waitFor({ timeout: 10000 });
		console.log(JSON.stringify({ supplierList: true, pricingAfterAdd: true, errors }, null, 2));
	}
} finally {
	await browser.close();
}
