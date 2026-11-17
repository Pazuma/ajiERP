import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";
const b=await chromium.launch({headless:true,executablePath:"/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",args:["--no-sandbox"]});
const p=await b.newPage();
await p.goto("http://127.0.0.1:8300/login",{waitUntil:"domcontentloaded"});
await p.locator("#login_email").fill("Administrator"); await p.locator("#login_password").fill("admin"); await p.locator("button.btn-login").click(); await p.waitForURL(/desk/);
const site=await p.evaluate(()=>({site:frappe.boot?.sitename,user:frappe.session?.user,host:location.host}));
const list=await p.evaluate(async()=>{const r=await fetch("/api/method/frappe.client.get_list",{method:"POST",headers:{"Content-Type":"application/json","X-Frappe-CSRF-Token":frappe.csrf_token},body:JSON.stringify({doctype:"Item",fields:["name","item_code","item_name","item_group","stock_uom","custom_product_status","creation","modified"],order_by:"modified desc",limit_page_length:100,limit_start:0})});return r.json();});
const exact=await p.evaluate(async()=>{const names=["1041","1044","1047","1051","1053","1054","1055","1042","1045","1049","1141","1468"]; const out=[]; for(const name of names){const r=await fetch("/api/method/frappe.client.get",{method:"POST",headers:{"Content-Type":"application/json","X-Frappe-CSRF-Token":frappe.csrf_token},body:JSON.stringify({doctype:"Item",name})});out.push({name,response:await r.json()});}return out;});
console.log(JSON.stringify({site,list:list.message||list,exact},null,2)); await b.close();
