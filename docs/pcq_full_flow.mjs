import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from '../development/erpnext.official/node_modules/playwright/index.mjs';
const browser=await chromium.launch({headless:true,executablePath:'/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1540,height:1050}});
const state=JSON.parse(await fs.readFile(new URL('./pcq-full-flow-result.json',import.meta.url),'utf8').catch(()=> '{}'));delete state.error;
page.on('response',async r=>{if(r.status()>=400&&r.url().includes('/api/'))console.log((await r.text()).slice(0,9000));});
const output=new URL('./pcq-full-flow-result.json',import.meta.url);
async function persist(){await fs.writeFile(output,JSON.stringify(state,null,2));}
async function submitForm(){
 if(await page.evaluate(()=>cur_frm.doc.docstatus===1))return;
 await page.evaluate(()=>{cur_frm.savesubmit();});
 await page.locator('.modal:visible .btn-primary').click();
 await page.waitForFunction(()=>cur_frm.doc.docstatus===1,{},{timeout:30000});
}
async function create(key,doctype,values,children={},submit=false){
 if(state[key]){
  await page.evaluate(({doctype,name})=>{frappe.set_route('Form',doctype,name);},{doctype,name:state[key]});
  await page.waitForFunction(name=>window.cur_frm?.doc?.name===name,state[key]);
  if(submit)await submitForm();return state[key];
 }
 const filters=doctype==='Item'?{item_code:values.item_code}:doctype==='Project'?{project_name:values.project_name}:doctype==='Item Supplier Pricing Rule'?{item_code:values.item_code}:null;
 if(filters){const found=await page.evaluate(async({doctype,filters})=>(await frappe.db.get_list(doctype,{filters,fields:['name'],limit:1}))[0]?.name,{doctype,filters});if(found){state[key]=found;await persist();return found;}}
 await page.evaluate(async({doctype,values,children})=>{
  await frappe.model.with_doctype(doctype); const doc=frappe.model.get_new_doc(doctype);
  frappe.set_route('Form',doctype,doc.name);
 },{doctype,values,children});
 await page.waitForFunction(dt=>window.cur_frm?.doc?.doctype===dt&&cur_frm.is_new(),doctype);
 await page.evaluate(async({values,children})=>{
  await cur_frm.set_value(values);
  for(const [key,rows] of Object.entries(children)){cur_frm.clear_table(key);for(const row of rows)cur_frm.add_child(key,row);}
  if(cur_frm.doc.doctype==='Product Cost Quotation'&&!cur_frm.doc.scenarios?.some(r=>r.quantity)){cur_frm.clear_table('scenarios');for(const quantity of [50,100,200,500])cur_frm.add_child('scenarios',{quantity,show_in_customer_quote:quantity>=200?1:0});}
  cur_frm.dirty();cur_frm.refresh_fields();
  if(cur_frm.doctype==='BOM'){
   for(const f of frappe.meta.get_docfields('BOM'))if(['Float','Currency','Percent','Int','Check'].includes(f.fieldtype)&&cur_frm.doc[f.fieldname]!==undefined)cur_frm.doc[f.fieldname]=Number(cur_frm.doc[f.fieldname]||0);
  }
  cur_frm.save();
 },{values,children});
 await page.waitForFunction(dt=>window.cur_frm?.doc?.doctype===dt&&!cur_frm.is_new()&&!cur_frm.is_dirty(),doctype,{timeout:30000});
 state[key]=await page.evaluate(()=>cur_frm.doc.name);await persist();
 if(submit)await submitForm();
 return state[key];
}
try{
 await page.goto('http://127.0.0.1:8300/login');await page.locator('#login_email').fill('Administrator');await page.locator('#login_password').fill('admin');await page.locator('.btn-login').click();await page.waitForURL(/\/(app|desk)/);
 await page.goto('http://127.0.0.1:8300/app/product-cost-quotation',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.frappe?.boot);
 const company='阿基视觉（东莞）',tag='PCQ-UAT-1022';
 const raw=await create('raw','Item',{item_code:tag+'-RAW',item_name:'成本报价验收-原料',item_group:'五金',stock_uom:'Nos',is_stock_item:1,valuation_rate:15});
 const fg=await create('product','Item',{item_code:tag+'-FG',item_name:'成本报价验收-成品',item_group:'五金',stock_uom:'Nos',is_stock_item:1});
 const rule=await create('rule','Item Supplier Pricing Rule',{item_code:raw,supplier:'供应商2',company,rule_type:'Fixed Rate',uom:'Nos',currency:'CNY',valid_from:'2026-10-01',valid_upto:'2027-10-31',rule_parameters:'{"rate":15}',remarks:'成本报价人工验收测试数据，未税15元/件'});
 await page.evaluate(name=>frappe.set_route('Form','Item',name),raw);await page.waitForFunction(name=>cur_frm.doc.name===name,raw);
 await page.evaluate(async rule=>{if(!cur_frm.doc.supplier_items?.some(r=>r.custom_active_pricing_rule===rule)){cur_frm.add_child('supplier_items',{supplier:'供应商2',custom_active_pricing_rule:rule});cur_frm.dirty();cur_frm.refresh_fields();cur_frm.save();}},rule);
 await page.waitForFunction(()=>!cur_frm.is_dirty()&&!frappe.request.ajax_count);
 const project=await create('project','Project',{project_name:tag+'-成本报价验收',company,expected_start_date:'2026-10-22',expected_end_date:'2026-11-22'}, {custom_project_cost_details:[{cost_type:'测试费',expense_description:'成本报价验收-样机测试投入',amount:2000,cost_date:'2026-10-22',version:'UAT'}],custom_project_budget_details:[{expense_category:'直接投入费',amount:3000,calculation_basis:'测试预算，仅作参考不重复计成本',remarks:'成本报价验收'}]});
 const bom=await create('bom','BOM',{item:fg,company,quantity:1,currency:'CNY',is_active:1,is_default:1},{items:[{item_code:raw,qty:2,uom:'Nos',stock_uom:'Nos',conversion_factor:1,rate:15}]},true);
 const wo=await create('work_order','Work Order',{company,production_item:fg,bom_no:bom,qty:10,source_warehouse:'仓库 - T',wip_warehouse:'进行中 - T',fg_warehouse:'成品 - T',skip_transfer:1,from_wip_warehouse:0,planned_start_date:'2026-10-22 08:00:00',custom_actual_labor_hours:3,custom_labor_hourly_rate:60}, {},true);
 await create('receipt','Stock Reconciliation',{company,purpose:'Opening Stock'},{items:[{item_code:raw,warehouse:'仓库 - T',qty:20,valuation_rate:15}]},true);
 const entry=state.manufacture?{items:[]}:await page.evaluate(async wo=>(await frappe.call({method:'erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry',args:{work_order_id:wo,purpose:'Manufacture',qty:10}})).message,wo);
 await create('manufacture','Stock Entry',{company,custom_stock_direction:'入库',custom_stock_reason:'生产入库',stock_entry_type:'生产制造',work_order:wo,bom_no:bom,fg_completed_qty:10,from_bom:1,remarks:'成本报价验收测试：10台完工，耗用20件测试原料'}, {items:entry.items.map(r=>({...r,name:undefined,parent:undefined,parenttype:undefined,parentfield:undefined}))},true);
 const quotation=await create('quotation','Product Cost Quotation',{company,item_code:fg,product_name:'成本报价完整流程验收',bom_no:bom,project,reference_work_order:wo,currency:'CNY',exchange_rate:1,tax_rate:13,customer:'客户B',contact:'小曹-客户B',contact_phone:'111111',sales_contact:'测试业务员',sales_phone:'13800000000',valid_until:'2026-11-22',minimum_sales_qty:200,pricing_method:'Target Margin',target_margin:40,terms:'仅供人工验收测试；预付30%，发货前付清；15个工作日交货。'});
 await page.getByRole('button',{name:'读取来源 / 刷新预览',exact:true}).click();await page.getByRole('dialog').getByText('核对来源变更',{exact:true}).waitFor();await page.getByRole('button',{name:'应用选中分组',exact:true}).click();
 await page.getByRole('dialog').filter({hasText:'核对来源变更'}).waitFor({state:'hidden'});
 await page.waitForFunction(()=>!frappe.request.ajax_count);
 await page.evaluate(async()=>{await cur_frm.reload_doc();});
 await page.evaluate(async()=>{
  const reason='成本报价完整流程人工验收测试数据；未税采购价15元/件，税率13%；制造费率含人工；项目投入全部归本产品，按500台摊销。';
  for(const r of cur_frm.doc.materials)Object.assign(r,{supplier:'供应商2',pricing_rule:'ISPR-00008',price_currency:'CNY',tax_basis:'Exclusive',purchase_tax_rate:13});
  cur_frm.clear_table('operations');
  cur_frm.add_child('operations',{operation:'验收-组装检验',charging_basis:'Per Unit',standard_hours:0.3,hourly_rate:60,included_cost_scope:'人工',manual_reason:reason});
  for(const r of cur_frm.doc.investments)Object.assign(r,{allocation_percent:100,remaining_estimate:r.actual_amount?1000:0,amortization_qty:500,recovery_method:'Amortize',manual_reason:reason});
  for(const r of cur_frm.doc.scenarios)r.show_in_customer_quote=r.quantity>=200?1:0;
  await cur_frm.set_value({estimate_acknowledged:1,estimate_reason:reason});cur_frm.dirty();cur_frm.refresh_fields();cur_frm.save();
 });
 await page.waitForFunction(()=>!cur_frm.is_dirty()&&!frappe.request.ajax_count);
 state.result=await page.evaluate(()=>({actual:JSON.parse(cur_frm.doc.actual_reference_json),scenarios:cur_frm.doc.scenarios.map(r=>({quantity:r.quantity,cost:r.full_unit_cost,price:r.final_tax_inclusive_price,completeness:r.completeness}))}));await persist();
 assert.equal(state.result.actual.produced_qty,10);assert.equal(state.result.actual.actual_material_reference,300);assert.equal(state.result.actual.actual_labor_hours,3);assert.ok(state.result.scenarios.every(r=>r.completeness!=='Incomplete'));
 await submitForm();state.submitted=await page.evaluate(()=>cur_frm.doc.docstatus);assert.equal(state.submitted,1);await persist();
 for(const audience of ['internal','customer']){const r=await page.request.get(`http://127.0.0.1:8300/api/method/client_akivision.api.product_cost_quotation.export_cost_quotation?name=${quotation}&audience=${audience}`);assert.equal(r.status(),200);const b=await r.body();assert.equal(b.subarray(0,2).toString(),'PK');await fs.writeFile(new URL(`./pcq-full-${audience}.xlsx`,import.meta.url),b);}
 await page.getByRole('tab',{name:'成本核算',exact:true}).click();await page.screenshot({path:new URL('./pcq-full-flow.png',import.meta.url).pathname,fullPage:true});state.passed=true;await persist();console.log(JSON.stringify(state,null,2));
}catch(e){state.error=e.message;await persist();await page.screenshot({path:new URL('./pcq-full-failure.png',import.meta.url).pathname,fullPage:true});throw e;}finally{await browser.close();}
