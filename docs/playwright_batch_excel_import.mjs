import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
import fs from "node:fs";

const baseUrl = "http://127.0.0.1:8300";
const dataDir = "/home/cst/frappe_docker/development/frappe-bench/sites/aji_test.localhost/private/files/数据";
const output = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/真实导入结果.json";
const jobs = [
  ["Customer", "客户清单.xlsx"],
  ["Supplier", "供应商清单.xlsx"],
  ["Payment Terms Template", "收款模式清单.xlsx"],
  ["Project", "研发项目清单.xlsx"],
  ["Item", "ERP表格模板(2)(1)_产品清单.xlsx"],
  ["Item Reorder", "安全库存参数.xlsx"],
  ["Sales Order", "销售订单.xlsx"],
  ["Purchase Order", "ERP表格模板(2)(1)_采购清单.xlsx"],
  ["Purchase Receipt", "ERP表格模板(2)(1)_入库清单.xlsx"],
  ["Delivery Note", "ERP表格模板(2)(1)_送货清单.xlsx"],
  ["Payment Entry", "ERP表格模板(2)(1)_回款记录.xlsx"],
  ["Payment Entry", "ERP表格模板(2)(1)_采购付款记录表.xlsx"],
  ["Stock Entry", "ERP表格模板(2)(1)_出库清单.xlsx"],
  ["Asset", "ERP表格模板(2)(1)_固定资产清单.xlsx"],
  ["Timesheet", "ERP表格模板(2)(1)_工时记录.xlsx"],
  ["Sample Loan Out", "ERP表格模板(2)(1)_借出样品清单.xlsx"],
  ["Sample Loan In", "ERP表格模板(2)(1)_借回样品清单.xlsx"],
];
const routes = {
  Customer: "customer", Supplier: "supplier", "Payment Terms Template": "payment-terms-template",
  Project: "project", Item: "item", "Item Reorder": "item-reorder", "Sales Order": "sales-order",
  "Purchase Order": "purchase-order", "Purchase Receipt": "purchase-receipt", "Delivery Note": "delivery-note",
  "Payment Entry": "payment-entry", "Stock Entry": "stock-entry", Asset: "asset", Timesheet: "timesheet",
  "Sample Loan Out": "sample-loan-out", "Sample Loan In": "sample-loan-in",
};
const skipped = [
  "实时库存.xlsx", "ERP表格模板(2)(1)_供应商回顾.xlsx", "ERP表格模板(2)(1)_成品状态.xlsx",
  "ERP表格模板(2)(1)_汇总计算.xlsx", "ERP表格模板(2)(1)_各项指标汇总或看板数据.xlsx",
  "ERP表格模板(2)(1).xlsx",
];

const browser = await chromium.launch({ headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const results = { started_at: new Date().toISOString(), jobs: [], skipped };
const log = (message) => console.log(`[${new Date().toISOString()}] ${message}`);

async function login() {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#login_email").fill("Administrator");
  await page.locator("#login_password").fill("admin");
  await page.locator("button.btn-login").click();
  await page.waitForURL(/desk/, { timeout: 20000 });
}

async function importOne(doctype, filename) {
  const started = Date.now();
  const result = { doctype, filename, status: "探查失败", messages: [], started_at: new Date().toISOString() };
  const file = `${dataDir}/${filename}`;
  if (!fs.existsSync(file)) { result.messages.push("文件不存在"); return result; }
  try {
    await page.goto(`${baseUrl}/desk/${routes[doctype]}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const menu = page.getByRole("button", { name: "菜单" });
    if (!(await menu.count())) { result.messages.push("列表页未找到菜单按钮"); return result; }
    await menu.click();
    const importItem = page.getByText("导入", { exact: true });
    if (!(await importItem.count())) { result.messages.push("菜单中没有导入入口"); return result; }
    await importItem.click();
    const modal = page.locator(".client-inline-import-dialog");
    await modal.waitFor({ state: "visible", timeout: 5000 });
    result.entry = (await modal.locator(".modal-title").innerText()).trim();
    await modal.locator(".btn-attach").click();
    const fileInput = page.locator("input[type=file]").last();
    await fileInput.waitFor({ state: "attached", timeout: 5000 });
    await fileInput.setInputFiles(file);
    const uploadModal = page.locator(".modal.show").last();
    const uploadButton = uploadModal.getByRole("button", { name: "上传", exact: true });
    if (await uploadButton.count()) await uploadButton.click();
    await page.waitForTimeout(5000);
    result.preview_text = (await modal.innerText()).slice(-12000);
    result.alerts = await modal.locator(".alert").allTextContents();
    result.preview_rows = await modal.locator(".client-import-preview tbody tr").count().catch(() => 0);
    const bodyText = result.preview_text;
    const hasError = /错误|失败|不存在|必填|无效|重复/.test(bodyText) || result.alerts.some((x) => /错误|失败/.test(x));
    result.status = hasError ? "预览发现问题，未提交" : "预览通过，未提交";
    await page.screenshot({ path: `/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/real_import_${doctype.toLowerCase().replaceAll(" ", "_")}.png`, fullPage: true });
    await modal.locator(".btn-modal-close").click().catch(() => {});
    await page.locator(".modal.show").last().locator("[data-dismiss=modal], .btn-modal-close").first().click().catch(() => {});
  } catch (error) {
    result.messages.push(error.message);
  }
  result.elapsed_ms = Date.now() - started;
  return result;
}

try {
  await login();
  for (const [doctype, filename] of jobs) {
    log(`预览 ${doctype} <- ${filename}`);
    const result = await importOne(doctype, filename);
    results.jobs.push(result);
    fs.writeFileSync(output, JSON.stringify(results, null, 2));
    log(`${result.status}`);
  }
} finally {
  results.finished_at = new Date().toISOString();
  fs.writeFileSync(output, JSON.stringify(results, null, 2));
  await browser.close();
}
