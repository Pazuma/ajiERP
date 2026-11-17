import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
import fs from "node:fs";
const base="http://127.0.0.1:8300", file="/home/cst/frappe_docker/development/frappe-bench/sites/aji_test.localhost/private/files/数据/ERP表格模板(2)(1)_成品状态.xlsx";
const browser=await chromium.launch({headless:true,executablePath:"/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",args:["--no-sandbox"]});
const page=await browser.newPage({viewport:{width:1440,height:1000}}); const out={};
try {
 await page.goto(`${base}/login`); await page.locator('#login_email').fill('Administrator'); await page.locator('#login_password').fill('admin'); await page.locator('button.btn-login').click(); await page.waitForTimeout(5000); out.after_login=page.url();
 await page.goto(`${base}/desk/finished-goods-status`,{waitUntil:'domcontentloaded'}); await page.waitForTimeout(1500);
const menu=page.getByRole('button',{name:'菜单'}); out.menu=await menu.count();
 if(out.menu){ await menu.click(); const imp=page.getByText('导入',{exact:true}); out.import_entry=await imp.count(); if(out.import_entry){ await imp.click(); const modal=page.locator('.client-inline-import-dialog'); await modal.waitFor({state:'visible',timeout:5000}); await modal.locator('.btn-attach').click(); const input=page.locator('input[type=file]').last(); await input.setInputFiles(file); const up=page.locator('.modal.show').last().getByRole('button',{name:'上传',exact:true}); if(await up.count()) await up.click(); await page.waitForTimeout(5000); out.text=(await modal.innerText()).slice(-12000); out.alerts=await modal.locator('.alert').allTextContents(); out.preview_rows=await modal.locator('.client-import-preview tbody tr').count(); await page.screenshot({path:'/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_finished_goods_import.png',fullPage:true}); } }
} catch(e) { out.error=e.message; }
finally { fs.writeFileSync('/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_finished_goods_import_result.json',JSON.stringify(out,null,2)); await browser.close(); }
console.log(JSON.stringify(out,null,2));
