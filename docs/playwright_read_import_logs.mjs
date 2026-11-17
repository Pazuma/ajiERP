import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const browser = await chromium.launch({ headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.goto("http://127.0.0.1:8300/login", { waitUntil: "domcontentloaded" });
await page.locator("#login_email").fill("Administrator");
await page.locator("#login_password").fill("admin");
await page.locator("button.btn-login").click();
await page.waitForURL(/desk/);

async function call(method, args) {
  return page.evaluate(async ({ method, args }) => {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": frappe.csrf_token },
      body: JSON.stringify(args),
    });
    return response.json();
  }, { method, args });
}

const imports = await call("frappe.client.get_list", {
  doctype: "Data Import",
  filters: { reference_doctype: process.env.IMPORT_DOCTYPE || "Delivery Note" },
  fields: ["name", "status", "import_file", "payload_count", "modified", "template_options"],
  order_by: "modified desc",
  limit_page_length: 5,
});
const output = [];
for (const row of imports.message || []) {
  const logs = await call("frappe.client.get_list", {
    doctype: "Data Import Log",
    filters: { data_import: row.name },
    fields: ["row_indexes", "success", "exception", "messages", "docname"],
    order_by: "creation asc",
    limit_page_length: 100,
  });
  output.push({ ...row, logs: logs.message || [] });
}
console.log(JSON.stringify(output, null, 2));
await browser.close();
