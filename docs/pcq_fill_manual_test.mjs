import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from '../development/erpnext.official/node_modules/playwright/index.mjs';
const browser=await chromium.launch({headless:true,executablePath:'/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1540,height:1050}});
try {
 await page.goto('http://127.0.0.1:8300/login');
 await page.locator('#login_email').fill('Administrator');
 await page.locator('#login_password').fill('admin');
 await page.locator('.btn-login').click();
 await page.waitForURL(/\/(app|desk)/);
 await page.goto('http://127.0.0.1:8300/app/product-cost-quotation/PCQ-2026-00106',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.cur_frm?.doc?.name==='PCQ-2026-00106');
 const before=await page.evaluate(()=>JSON.parse(JSON.stringify(cur_frm.doc)));
 await fs.writeFile(new URL('./pcq-before-manual-test.json',import.meta.url),JSON.stringify(before,null,2));
 assert.equal(before.docstatus,0);
 await page.getByRole('button',{name:'读取来源 / 刷新预览',exact:true}).click();
 await page.getByRole('dialog').getByText('核对来源变更',{exact:true}).waitFor();
 await page.getByRole('button',{name:'应用选中分组',exact:true}).click();
 await page.waitForFunction(()=>cur_frm.doc.materials.every(r=>r.pricing_rule));
 await page.evaluate(async()=>{
   const reason='人工验收测试数据，按合理估算填写，非实际采购或财务凭证；正式使用前需业务复核。';
   for(const r of cur_frm.doc.materials) {
     await frappe.model.set_value(r.doctype,r.name,{tax_basis:'Exclusive',purchase_tax_rate:13,loss_method:'None',loss_rate:0});
   }
   const ops=[['测试-组装',0.2,60],['测试-检验包装',0.1,50]];
   for(const [operation,hours,rate] of ops) {
     let row=cur_frm.doc.operations.find(r=>r.operation===operation);
     if(!row) row=cur_frm.add_child('operations');
     Object.assign(row,{operation,charging_basis:'Per Unit',standard_hours:hours,hourly_rate:rate,included_cost_scope:'人工及常规制造费用，不含材料和研发',manual_reason:reason});
   }
   let inv=cur_frm.doc.investments.find(r=>r.expense_type==='测试-研发及样机投入');
   if(!inv) inv=cur_frm.add_child('investments');
   Object.assign(inv,{project:cur_frm.doc.project,expense_type:'测试-研发及样机投入',actual_amount:2000,budget_reference:3000,remaining_estimate:1000,allocation_percent:100,recovered_amount:0,separate_charge:0,recovery_method:'Amortize',amortization_qty:500,rd_markup_rate:0,manual_reason:reason});
   for(const row of cur_frm.doc.scenarios) row.show_in_customer_quote=row.quantity>=200?1:0;
   await cur_frm.set_value({sales_contact:'测试业务员',sales_phone:'13800000000',valid_until:'2026-10-24',terms:'【人工验收测试报价】人民币含税价，税率13%；起订量200台；预付30%，发货前付清余款；订单及预付款确认后15个工作日交货；运费另议。本报价仅供系统测试，非正式商业承诺。',estimate_acknowledged:1,estimate_reason:reason+' 两项采购价均按未税15元计，采购税率13%；材料沿用现有BOM及Yard计量，仅用于验收，正式使用前核对单位。组装0.2小时×60元，检验包装0.1小时×50元；研发已发生2000元、剩余1000元，全额归本产品，按500台摊销，无已回收及另收费。'});
   cur_frm.dirty(); cur_frm.refresh_fields(); await cur_frm.save();
 });
 await page.reload({waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.cur_frm?.doc?.name==='PCQ-2026-00106');
 const result=await page.evaluate(()=>({name:cur_frm.doc.name,docstatus:cur_frm.doc.docstatus,estimate_acknowledged:cur_frm.doc.estimate_acknowledged,materials:cur_frm.doc.materials.map(r=>({item:r.item_code,rule:r.pricing_rule,tax:r.tax_basis})),operations:cur_frm.doc.operations.length,investments:cur_frm.doc.investments.length,scenarios:cur_frm.doc.scenarios.map(r=>({quantity:r.quantity,cost:r.full_unit_cost,price:r.suggested_price_with_rd,final:r.final_tax_inclusive_price,completeness:r.completeness,warnings:r.warnings,customer:r.show_in_customer_quote}))}));
 assert.equal(result.docstatus,0);
 assert.ok(result.scenarios.every(r=>r.cost>0&&r.completeness!=='Incomplete'));
 await page.screenshot({path:new URL('./pcq-ready-for-manual-test.png',import.meta.url).pathname,fullPage:true});
 await fs.writeFile(new URL('./pcq-ready-for-manual-test.json',import.meta.url),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
