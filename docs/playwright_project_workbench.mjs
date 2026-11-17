import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
try {
 const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
 const errors = [];
 page.on("pageerror", e => {if (!errors.includes(e.stack)) errors.push(e.stack);});
 await page.goto("http://127.0.0.1:8300/login");
 await page.locator("#login_email").fill("Administrator");
 await page.locator("#login_password").fill("admin");
 await page.locator("button.btn-login").click();
 await page.waitForURL(/desk|app/, {timeout: 30000});
 await page.goto("http://127.0.0.1:8300/app/project-workbench");
 await page.getByText("暂无符合条件的节点", {exact: true}).waitFor({timeout: 30000});
 await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/project_workbench.png", fullPage: true});
 console.log(JSON.stringify({page_loaded: true, errors}));
 if (errors.length) throw new Error(errors.join("; "));
} finally { await browser.close(); }
