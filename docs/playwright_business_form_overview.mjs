import assert from "node:assert/strict";
import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const baseUrl = process.env.FRAPPE_BASE_URL || "http://127.0.0.1:8000";
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#login_email").fill(process.env.FRAPPE_USER || "Administrator");
  await page.locator("#login_password").fill(process.env.FRAPPE_PASSWORD || "admin");
  await page.locator("button.btn-login").click();
  await page.waitForURL(/\/app|\/desk/, { timeout: 20000 });
  await page.goto(`${baseUrl}/app/business-form-overview`, { waitUntil: "networkidle", timeout: 30000 });
  const body = await page.locator("body").innerText();
  assert.ok(!body.includes("页面 business-form-overview未找到"), body.slice(0, 500));
  await page.screenshot({ path: "/tmp/business-form-overview-playwright.png", fullPage: true });
  console.log(JSON.stringify({ passed: true, url: page.url(), errors }, null, 2));
} finally {
  await browser.close();
}
