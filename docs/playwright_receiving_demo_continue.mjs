import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";
const out='/workspace/development/frappe-bench/apps/client_akivision/docs';
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium-headless-shell',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100}});
async function snap(name){await page.screenshot({path:`${out}/receiving_flow_${name}.png`,fullPage:true});}
async function action(label,doctype){
 await page.evaluate(label=>{const a=[...document.querySelectorAll('.custom-actions a,.custom-actions button')].find(x=>x.textContent.trim()===label);if(!a)throw Error('Missing action '+label);a.click();},label);
 await page.waitForFunction(dt=>cur_frm?.doctype===dt,doctype);
 await page.waitForTimeout(700);
}
async function submit(){
 await page.evaluate(async()=>{if(cur_frm.doc.docstatus===0)await cur_frm.save('Submit');});
 await page.waitForFunction(()=>cur_frm.doc.docstatus===1);
}
try{
 await page.goto('http://127.0.0.1:8300/login');
 await page.locator('#login_email').fill('Administrator');await page.locator('#login_password').fill('admin');
 await page.locator('button.btn-login').click();await page.waitForURL(/desk|app/);
 await page.goto('http://127.0.0.1:8300/desk/purchase-order/PUR-ORD-2026-00050',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>cur_frm?.doc?.name==='PUR-ORD-2026-00050');
 await submit();await snap('01_order');console.log('ORDER_SUBMITTED');
 await action('创建收料通知单','Purchase Receiving Notice');
 console.log('NOTICE',await page.evaluate(()=>cur_frm.doc.name));
 await submit();await snap('02_notice');
 console.log('NOTICE_SUBMITTED',await page.evaluate(()=>cur_frm.doc.name));
 await action('创建质量检验','Quality Inspection');
 await page.evaluate(async()=>{
  const r=cur_frm.doc.custom_purchase_quality_items[0];
  await frappe.model.set_value(r.doctype,r.name,'accepted_qty',96);
  await frappe.model.set_value(r.doctype,r.name,'rejected_qty',4);
  await frappe.model.set_value(r.doctype,r.name,'remarks','演示：到货100件，96件合格，4件外观划伤待退；整单完成不代表全部合格。');
  await cur_frm.save();
 });
 await submit();await snap('03_quality');
 console.log('QUALITY_SUBMITTED',await page.evaluate(()=>({name:cur_frm.doc.name,rows:cur_frm.doc.custom_purchase_quality_items})));
 await action('创建采购入库单','Purchase Receipt');
 await snap('04_receipt_draft');
 console.log('RECEIPT',await page.evaluate(()=>({name:cur_frm.doc.name,docstatus:cur_frm.doc.docstatus,notice:cur_frm.doc.custom_receiving_notice,items:cur_frm.doc.items.map(r=>({qty:r.qty,received_qty:r.received_qty,rejected_qty:r.rejected_qty,quality_inspection:r.quality_inspection}))})));
}catch(e){await snap('error');console.log('PAGE_TEXT',(await page.locator('body').innerText()).slice(-7000));throw e;}
finally{await browser.close();}
