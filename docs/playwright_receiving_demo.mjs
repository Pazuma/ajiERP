import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";
const out = "/workspace/development/frappe-bench/apps/client_akivision/docs";
const browser = await chromium.launch({headless:true, executablePath:"/usr/bin/chromium-headless-shell", args:["--no-sandbox"]});
try {
 const page = await browser.newPage({viewport:{width:1600,height:1050}});
 await page.goto("http://127.0.0.1:8300/login");
 await page.locator("#login_email").fill("Administrator");
 await page.locator("#login_password").fill("admin");
 await page.locator("button.btn-login").click();
 await page.waitForURL(/desk|app/);
 await page.goto("http://127.0.0.1:8300/desk/purchase-order/PUR-ORD-2026-00050", {waitUntil:"networkidle"});
 await page.waitForFunction(() => window.cur_frm?.doc?.name === "PUR-ORD-2026-00050");
 await page.screenshot({path:`${out}/playwright_receiving_demo_order.png`,fullPage:true});
 console.log(JSON.stringify(await page.evaluate(() => ({name:cur_frm.doc.name,docstatus:cur_frm.doc.docstatus,qty:cur_frm.doc.items.map(r=>r.qty),buttons:[...document.querySelectorAll('button')].filter(b=>b.getClientRects().length).map(b=>b.innerText)}))));
 await page.goto("http://127.0.0.1:8300/desk/purchase-receiving-notice/new-purchase-receiving-notice", {waitUntil:"networkidle"});
 await page.waitForFunction(() => window.cur_frm?.doctype === "Purchase Receiving Notice");
 const data = await page.evaluate(async () => {
  const po = (await frappe.db.get_doc('Purchase Order','PUR-ORD-2026-00050'));
  await cur_frm.set_value('company',po.company);
  await cur_frm.set_value('supplier',po.supplier);
  await cur_frm.set_value('purchase_order',po.name);
  await cur_frm.set_value('remarks','演示流程检查：到货100件，计划合格96件、不合格4件。');
  const source=po.items[0];
  cur_frm.clear_table('items');
  const row=cur_frm.add_child('items');
  Object.assign(row,{item_code:source.item_code,item_name:source.item_name,purchase_order_item:source.name,ordered_qty:100,received_qty:100,uom:source.uom,warehouse:source.warehouse});
  cur_frm.refresh_field('items');
  return {source:po.name,docstatus:po.docstatus};
 });
 await page.getByRole('button',{name:'保存',exact:true}).click();
 await page.waitForFunction(() => document.querySelector('.modal.show')?.innerText.includes('采购订单必须'));
 await page.screenshot({path:`${out}/playwright_receiving_demo_blocked.png`,fullPage:true});
 console.log(JSON.stringify({source:data,validation:await page.locator('.modal.show').innerText()}));
} finally { await browser.close(); }
