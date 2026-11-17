import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
import fs from "node:fs";

const baseUrl = "http://127.0.0.1:8300";
const dataDir = "/home/cst/frappe_docker/development/frappe-bench/sites/aji_test.localhost/private/files/数据";
const jobs = [
  ["Supplier", "supplier", "供应商清单.xlsx"],
  ["Payment Terms Template", "payment-terms-template", "收款模式清单.xlsx"],
  ["Delivery Note", "delivery-note", "ERP表格模板(2)(1)_送货清单.xlsx"],
  ["Payment Entry 收款", "payment-entry", "ERP表格模板(2)(1)_回款记录.xlsx"],
  ["Stock Entry", "stock-entry", "ERP表格模板(2)(1)_出库清单.xlsx"],
];
const results = [];
const browser = await chromium.launch({ headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

async function login() {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#login_email").fill("Administrator");
  await page.locator("#login_password").fill("admin");
  await page.locator("button.btn-login").click();
  await page.waitForURL(/desk/, { timeout: 20000 });
}

await login();

for (const [doctype, route, filename] of jobs) {
  const item = { doctype, filename, status: "提交失败", messages: [] };
  try {
    await page.goto(`${baseUrl}/desk/${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1600);
    await page.getByRole("button", { name: "菜单" }).click();
    await page.getByText("导入", { exact: true }).click();
    const modal = page.locator(".client-inline-import-dialog");
    await modal.waitFor({ state: "visible", timeout: 6000 });
    await modal.locator(".btn-attach").click();
    const input = page.locator("input[type=file]").last();
    await input.setInputFiles(`${dataDir}/${filename}`);
    const upload = page.locator(".modal.show").last().getByRole("button", { name: "上传", exact: true });
    await upload.click();
    await page.waitForTimeout(5000);
    const previewAlert = (await modal.locator(".alert").allTextContents()).join(" | ");
    item.preview_alert = previewAlert;
    if (/请先处理|解析失败|错误|失败/.test(previewAlert)) {
      item.status = "预览阻断，未提交";
    } else {
      await modal.getByRole("button", { name: "开始导入", exact: true }).click();
      await page.waitForTimeout(6000);
      const text = await modal.innerText();
      item.result_text = text.match(/导入失败：成功\s*\d+\s*\/\s*\d+，失败\s*\d+/)?.[0] || text.match(/成功\s*\d+\s*\/\s*\d+，失败\s*\d+/)?.[0] || text.slice(0, 500);
      const counts = text.match(/成功\s*(\d+)\s*\/\s*(\d+)，失败\s*(\d+)/);
      item.status = counts && Number(counts[3]) === 0 ? "提交成功" : (/导入失败|失败\s*\d+/.test(text) ? "提交失败" : "提交完成或任务已创建");
    }
    await page.screenshot({ path: `/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/real_submit_${route.replaceAll("-", "_")}.png`, fullPage: true });
    await modal.locator(".btn-modal-close").click().catch(() => {});
  } catch (error) {
    item.messages.push(error.message);
  }
  results.push(item);
  fs.writeFileSync("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/真实提交结果.json", JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2));
  console.log(JSON.stringify(item));
}
await browser.close();
