// Real UI captures: open unsaved forms only; never save or submit business records.
import { chromium } from '../../development/erpnext.official/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(root, 'images');
fs.mkdirSync(out, { recursive: true });
const base = process.env.MANUAL_BASE_URL || 'http://127.0.0.1:8300';
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || '/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome', args:['--no-sandbox']});
const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const captures = [
  ['sales-order','Sales Order','销售订单：先填主信息，再核对产品明细',['customer','delivery_date','items']],
  ['purchase-order','Purchase Order','采购订单：核对供应商、交期和本次订购明细',['supplier','schedule_date','items']],
  ['receiving-notice','Purchase Receiving Notice','收料通知：登记实际到货，保存提交前核对来源',['supplier','items']],
  ['quality-inspection','Quality Inspection','质量检验：先选检验类型与来源，再填写检验结果',['inspection_type','reference_type','custom_work_order']],
  ['stock-entry','Stock Entry','库存凭证：先核对实际业务方向和原因',['stock_entry_type','purpose','custom_stock_direction','custom_stock_reason','items']],
  ['work-order','Work Order','生产工单：核对产品、BOM 和计划产量',['production_item','bom_no','qty']],
  ['project','Project','项目：明确项目名称、负责人及计划时间',['project_name','expected_start_date','expected_end_date']],
  ['cost-quotation','Product Cost Quotation','产品成本报价：核对产品来源，再维护批量和报价条件',['item_code','bom_no','customer']],
  ['sample-loan-out','Sample Loan Out','样品借出：按实物序列号逐项核对借出明细',['items']],
  ['purchase-follow-up','Purchase Follow Up','采购对账：先填供应商和期间，再加载采购数据',['supplier','from_date','to_date']],
  ['reconciliation','China Reconciliation Statement','对账单：先确定对账类型、对象和依据',['statement_type','party','statement_basis']],
  ['payment-entry','Payment Entry','收付款：核对方向、往来对象及账户',['payment_type','party_type','party']],
];
const results=[];
try {
  await page.goto(base+'/login');
  await page.locator('#login_email').fill(process.env.TEST_USER || 'Administrator');
  await page.locator('#login_password').fill(process.env.TEST_PASSWORD || 'admin');
  await page.locator('button.btn-login').click();
  await page.waitForURL(/\/(app|desk)/);
  for (const [file,doctype,title,fields] of captures) {
    try {
      await page.goto(base+'/app/'+doctype.toLowerCase().replaceAll(' ','-')+'/new-'+doctype.toLowerCase().replaceAll(' ','-'));
      await page.waitForFunction(dt=>window.cur_frm?.doctype===dt && !window.frappe?.request?.ajax_count,doctype,{timeout:45000});
      await page.locator('.page-head').first().waitFor({state:'visible'});
      await page.evaluate(({title,fields})=>{
        document.querySelectorAll('.manual-callout,.manual-caption').forEach(e=>e.remove());
        // Redact actual default company/account identity, without replacing business fields with mock data.
        for (const field of ['company','owner','modified_by','inspected_by','verified_by','loaned_by']) {
          document.querySelectorAll(`[data-fieldname="${field}"] input`).forEach(e=>{e.style.color='transparent';e.style.textShadow='none';e.style.background='#dbe3eb';});
        }
        document.querySelectorAll('.navbar .avatar,.navbar .avatar-frame,.navbar .dropdown-navbar-user').forEach(e=>e.style.visibility='hidden');
        let n=0;
        for(const field of fields){
          const wrappers=[...document.querySelectorAll(`[data-fieldname="${field}"]`)];
          const el=wrappers.find(e=>e.getBoundingClientRect().width>0 && e.getBoundingClientRect().top<880);
          if(!el)continue;
          el.style.outline='2px solid #e17624';el.style.outlineOffset='3px';
          const badge=document.createElement('span');badge.className='manual-callout';badge.textContent=String(++n);
          Object.assign(badge.style,{position:'absolute',left:'-12px',top:'-10px',background:'#c65c0c',color:'white',borderRadius:'50%',width:'24px',height:'24px',textAlign:'center',font:'bold 15px/24px sans-serif',zIndex:100});
          el.style.position='relative';el.appendChild(badge);
        }
        const cap=document.createElement('div');cap.className='manual-caption';cap.textContent='操作指引｜'+title+'　（新建未保存页面；橙框为讲解标注）';
        Object.assign(cap.style,{position:'fixed',bottom:'0',left:'0',right:'0',padding:'12px 24px',background:'#153c57',color:'white',font:'16px/1.6 sans-serif',zIndex:99999});document.body.appendChild(cap);
        window.scrollTo(0,0);
      },{title,fields});
      await page.screenshot({path:path.join(out,file+'.png')});
      results.push({file:file+'.png',doctype,status:'captured',mode:'new unsaved form',url:new URL(page.url()).pathname});
      console.log('Captured '+file);
    } catch(error) {results.push({file,doctype,status:'failed',error:error.message});console.log('FAILED '+file+': '+error.message);}
  }
} finally {
  fs.writeFileSync(path.join(out,'capture-record.json'),JSON.stringify({date:'2026-10-29',viewport:{width:1440,height:1000},businessWrites:false,results},null,2));
  await browser.close();
}
if(results.some(r=>r.status!=='captured'))process.exitCode=1;
