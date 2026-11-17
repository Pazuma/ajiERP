import assert from 'node:assert/strict';
import {chromium} from '../development/erpnext.official/node_modules/playwright/index.mjs';
const browser=await chromium.launch({headless:true,executablePath:'/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1540,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8300/login');await page.locator('#login_email').fill('Administrator');await page.locator('#login_password').fill('admin');await page.locator('.btn-login').click();await page.waitForURL(/\/(app|desk)/);
 await page.goto('http://127.0.0.1:8300/app/product-cost-quotation/PCQ-2026-00109',{waitUntil:'networkidle'});await page.waitForFunction(()=>cur_frm?.doc?.name==='PCQ-2026-00109');
 const tabs=await page.locator('.form-tabs .nav-link').allInnerTexts();assert.ok(tabs.some(t=>t.includes('人工录入与确认')),JSON.stringify(tabs));
 await page.evaluate(()=>cur_frm.set_df_property('manual_entry_tab','label','人工录入与确认'));
 await page.locator('.form-tabs .nav-link').filter({hasText:'成本核算'}).click();assert.equal(await page.locator('.pcq-overview').count(),1);assert.equal(await page.locator('[data-fieldname="materials"]').isVisible(),false);
 await page.locator('.form-tabs .nav-link').filter({hasText:'人工录入与确认'}).evaluate(el=>el.click());
 await page.screenshot({path:'docs/pcq-manual-entry-tab-debug.png',fullPage:true});
 for(const name of ['scenario_edit_section','materials','operations','investments','source_section','pricing_details','estimate_details'])assert.equal(await page.locator(`[data-fieldname="${name}"]`).evaluate(el=>el.offsetParent!==null),true,name);
 await page.screenshot({path:'docs/pcq-manual-entry-tab.png',fullPage:true});assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,tabs,manualSections:['批量与最终报价','材料','制造工时','项目投入','产品与来源设置','定价参数','估算确认'],errors},null,2));
}finally{await browser.close();}
