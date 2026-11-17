import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from '../development/erpnext.official/node_modules/playwright/index.mjs';
const state=JSON.parse(await fs.readFile('docs/pcq-full-flow-result.json','utf8'));
const browser=await chromium.launch({headless:true,executablePath:'/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1540,height:1050}});
try{
 await page.goto('http://127.0.0.1:8300/login');await page.locator('#login_email').fill('Administrator');await page.locator('#login_password').fill('admin');await page.locator('.btn-login').click();await page.waitForURL(/\/(app|desk)/);
 await page.goto(`http://127.0.0.1:8300/app/product-cost-quotation/${state.quotation}`,{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.cur_frm?.doc?.docstatus===1);
 assert.equal(await page.getByRole('button',{name:'读取来源 / 刷新预览',exact:true}).count(),0);
 state.confirmed_readonly=await page.evaluate(()=>cur_frm.doc.docstatus===1&&!!cur_frm.doc.snapshot_hash);
 if(state.manual_test_draft){await page.goto(`http://127.0.0.1:8300/app/product-cost-quotation/${state.manual_test_draft}`,{waitUntil:'networkidle'});await page.waitForFunction(()=>cur_frm.doc.docstatus===0);}else{
 await page.getByRole('button',{name:'复制为新版本',exact:true}).click();
 await page.waitForFunction(()=>cur_frm.is_new()&&cur_frm.doc.docstatus===0);
 assert.equal(await page.evaluate(()=>cur_frm.doc.estimate_acknowledged),0);
 await page.evaluate(()=>{cur_frm.save();});await page.waitForFunction(()=>!cur_frm.is_new()&&!cur_frm.is_dirty());
 state.manual_test_draft=await page.evaluate(()=>cur_frm.doc.name);
 assert.equal(await page.evaluate(()=>cur_frm.doc.previous_version),state.quotation);
 }
 const before=await page.evaluate(()=>cur_frm.doc.operations.length);
 await page.getByRole('button',{name:'读取来源 / 刷新预览',exact:true}).click();await page.getByRole('dialog').getByText('核对来源变更',{exact:true}).waitFor();
 await page.getByRole('button',{name:'应用选中分组',exact:true}).click();await page.getByRole('dialog').filter({hasText:'核对来源变更'}).waitFor({state:'hidden'});await page.waitForFunction(()=>!frappe.request.ajax_count);await page.evaluate(async()=>await cur_frm.reload_doc());
 assert.equal(await page.evaluate(()=>cur_frm.doc.operations.length),before);state.refresh_preserves_manual_operations=true;
 await page.evaluate(()=>{for(const r of cur_frm.doc.materials)Object.assign(r,{tax_basis:'Exclusive',purchase_tax_rate:13});for(const r of cur_frm.doc.investments)Object.assign(r,{allocation_percent:100,remaining_estimate:r.actual_amount?1000:0,amortization_qty:500,recovery_method:'Amortize'});cur_frm.dirty();cur_frm.refresh_fields();cur_frm.save();});
 await page.waitForFunction(()=>!cur_frm.is_dirty()&&!frappe.request.ajax_count);
 assert.equal(await page.evaluate(()=>cur_frm.doc.scenarios[0].full_unit_cost),54);
 await page.getByRole('tab',{name:'成本核算',exact:true}).click();await page.screenshot({path:'docs/pcq-manual-draft.png',fullPage:true});
 await fs.writeFile('docs/pcq-full-flow-result.json',JSON.stringify(state,null,2));console.log(JSON.stringify(state,null,2));
}finally{await browser.close();}
