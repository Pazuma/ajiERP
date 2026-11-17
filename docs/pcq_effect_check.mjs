import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from '../development/erpnext.official/node_modules/playwright/index.mjs';
const browser = await chromium.launch({headless:true, executablePath:'/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args:['--no-sandbox']});
const page = await browser.newPage({viewport:{width:1540,height:1050}});
const results=[];
try {
 await page.goto('http://127.0.0.1:8300/login');
 await page.locator('#login_email').fill('Administrator');
 await page.locator('#login_password').fill('admin');
 await page.locator('.btn-login').click();
 await page.waitForURL(/\/(app|desk)/);
 await page.goto('http://127.0.0.1:8300/app/product-cost-quotation/PCQ-2026-00106',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.cur_frm?.doc?.name==='PCQ-2026-00106');
 await page.locator('.pcq-matrix:visible').first().waitFor();
 const state=await page.evaluate(()=>({name:cur_frm.doc.name,quantities:cur_frm.doc.scenarios.map(r=>r.quantity),completeness:cur_frm.doc.scenarios.map(r=>r.completeness),modified:cur_frm.doc.modified}));
 assert.deepEqual(state.quantities,[50,100,200,500]);
 results.push({check:'真实单据四档核算展示',state});
 await page.screenshot({path:new URL('./pcq-current-effect.png',import.meta.url).pathname,fullPage:true});
 results.push({check:'当前未完成核算，无成本明细链接',count:await page.locator('.pcq-detail').count()});
 await page.getByRole('button',{name:'读取来源 / 刷新预览',exact:true}).click();
 await page.getByRole('dialog').getByText('核对来源变更',{exact:true}).waitFor();
 results.push({check:'来源刷新预览（未应用）',passed:true,text:await page.locator('.modal:visible').innerText()});
 for(const audience of ['internal','customer']) {
   const r=await page.request.get(`http://127.0.0.1:8300/api/method/client_akivision.api.product_cost_quotation.export_cost_quotation?name=PCQ-2026-00106&audience=${audience}`);
   const b=await r.body();
   results.push({check:`${audience}导出`,status:r.status(),xlsx:b.subarray(0,2).toString()==='PK',message:b.subarray(0,2).toString()==='PK'?'':b.toString().slice(0,1500)});
 }
 console.log(JSON.stringify(results,null,2));
 await fs.writeFile(new URL('./pcq-effect-check-result.json',import.meta.url),JSON.stringify(results,null,2));
} finally {await browser.close();}
