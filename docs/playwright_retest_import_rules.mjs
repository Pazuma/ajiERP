import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
import fs from "node:fs";

const baseUrl = "http://127.0.0.1:8300";
const dataDir = "/home/cst/frappe_docker/development/frappe-bench/sites/aji_test.localhost/private/files/数据";
const output = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/真实提交结果.json";
const jobs = [
  { doctype: "Customer", route: "customer", filename: "客户清单.xlsx", importType: "Update Existing Records" },
  { doctype: "Item", route: "item", filename: "ERP表格模板(2)(1)_产品清单.xlsx", importType: "Insert New Records" },
  { doctype: "Project", route: "project", filename: "研发项目清单.xlsx", importType: "Insert New Records" },
  { doctype: "Delivery Note", route: "delivery-note", filename: "ERP表格模板(2)(1)_送货清单.xlsx", importType: "Insert New Records" },
];
const activeJobs = process.env.IMPORT_ONLY ? jobs.filter((job) => job.doctype === process.env.IMPORT_ONLY) : jobs;

const browser = await chromium.launch({
  headless: true,
  executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const results = [];

async function login() {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#login_email").fill("Administrator");
  await page.locator("#login_password").fill("admin");
  await page.locator("button.btn-login").click();
  await page.waitForURL(/desk/, { timeout: 20000 });
}

async function importOne(job) {
  const item = { ...job, status: "探查失败", messages: [] };
  try {
    await page.goto(`${baseUrl}/desk/${job.route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1400);
    await page.getByRole("button", { name: "菜单" }).click();
    await page.getByText("导入", { exact: true }).click();
    const modal = page.locator(".client-inline-import-dialog");
    await modal.waitFor({ state: "visible", timeout: 6000 });
    const advanced = modal.locator('[data-role="advanced-toggle"]');
    if (await advanced.count()) await advanced.click();
    const importType = modal.locator('[data-role="import-type"]');
    if (await importType.count()) {
      await importType.selectOption(job.importType);
    } else {
      const select = modal.locator('select').filter({ has: page.locator('option[value="Update Existing Records"]') });
      if (await select.count()) await select.first().selectOption(job.importType);
    }
    await modal.locator(".btn-attach").click();
    const input = page.locator("input[type=file]").last();
    await input.setInputFiles(`${dataDir}/${job.filename}`);
    const upload = page.locator(".modal.show").last().getByRole("button", { name: "上传", exact: true });
    await upload.click();
    await page.waitForTimeout(5000);
    item.preview_alert = (await modal.locator(".alert").allTextContents()).join(" | ");
    const previewText = await modal.innerText();
    item.preview_text = previewText.slice(-2500);
    if (/请先处理|解析失败|错误|不存在|无效|重复/.test(item.preview_alert + previewText)) {
      item.status = "预览阻断，未提交";
    } else {
      await modal.getByRole("button", { name: "开始导入", exact: true }).click();
      await page.waitForTimeout(7000);
      const text = await modal.innerText();
      item.result_text = text.match(/成功\s*\d+\s*\/\s*\d+，失败\s*\d+/)?.[0] || text.match(/导入失败：成功\s*\d+\s*\/\s*\d+，失败\s*\d+/)?.[0] || text.slice(-1000);
      const counts = text.match(/成功\s*(\d+)\s*\/\s*(\d+)，失败\s*(\d+)/);
      item.status = counts && Number(counts[3]) === 0 ? "提交成功" : "提交失败";
    }
    await page.screenshot({ path: `/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/real_retest_${job.route}.png`, fullPage: true });
    await modal.locator(".btn-modal-close").click().catch(() => {});
  } catch (error) {
    item.messages.push(error.message);
  }
  return item;
}

try {
  await login();
  for (const job of activeJobs) {
    const result = await importOne(job);
    results.push(result);
    fs.writeFileSync(output, JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2));
    console.log(JSON.stringify(result));
  }
} finally {
  await browser.close();
}
