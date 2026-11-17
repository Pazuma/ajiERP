frappe.pages["sales-commission-orders"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({parent: wrapper, title: "销售提成单", single_column: true});
	const api = "china_finance.services.sales_commission_order_dialog.";
	const esc = frappe.utils.escape_html;
	const fields = {};
	let start = 0, generation = 0;
	const body = $('<div class="p-3"></div>').appendTo(page.main);
	for (const def of [
		{fieldname:"company", label:"公司", fieldtype:"Link", options:"Company", default:frappe.defaults.get_user_default("Company")},
		{fieldname:"sales_order", label:"销售订单", fieldtype:"Link", options:"Sales Order"},
		{fieldname:"customer", label:"客户", fieldtype:"Link", options:"Customer"},
		{fieldname:"sales_person", label:"业务人员", fieldtype:"Link", options:"Sales Person", hidden:!frappe.user.has_role(["销售总监", "Sales Commission Manager", "System Manager"])},
		{fieldname:"from_date", label:"开始日期", fieldtype:"Date"},
		{fieldname:"to_date", label:"结束日期", fieldtype:"Date"},
		{fieldname:"status", label:"提成状态", fieldtype:"Select", options:"\n未设置\n草稿\n已确认\n待复核\n已作废\n受限"},
	]) fields[def.fieldname] = page.add_field({...def, change:()=>{start=0; load();}});
	async function call(method, args) {return (await frappe.call({method:api+method, args})).message;}
	async function load() {
		if (!fields.company?.get_value()) {body.text("请先选择公司"); return;}
		const seq = ++generation;
		const filters = Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,v.get_value()]));
		const data = await call("list_commission_orders", {filters, start, page_length:20});
		if (seq !== generation) return;
		body.html(`<div class="table-responsive"><table class="table table-hover"><thead><tr><th>销售订单</th><th>客户</th><th>日期</th><th>业务人员</th><th>状态</th><th>提成金额</th><th>操作</th></tr></thead><tbody>${data.rows.map(r=>`<tr><td><button class="btn btn-link p-0 commission-open" data-order="${esc(r.sales_order)}">${esc(r.sales_order)}</button></td><td>${esc(r.customer)}</td><td>${esc(r.transaction_date)}</td><td>${esc(r.sales_people)}</td><td>${esc(r.status)}</td><td>${r.commission_total == null ? "—" : esc(r.commission_total)}</td><td><button class="btn btn-xs btn-default commission-open" data-order="${esc(r.sales_order)}">${data.can_manage ? "设置 / 查看" : "查看"}</button></td></tr>`).join("")}</tbody></table></div><p>${data.total ? `共 ${data.total} 条` : "暂无符合条件的订单或本人提成"}</p><button class="btn btn-default prev">上一页</button> <button class="btn btn-default next">下一页</button>`);
		body.find(".commission-open").on("click", e=>open($(e.currentTarget).attr("data-order")));
		body.find(".prev").prop("disabled", start===0).on("click",()=>{start=Math.max(0,start-20);load();});
		body.find(".next").prop("disabled", start+20>=data.total).on("click",()=>{start+=20;load();});
	}
	async function open(order) {
		const data = await call("get_order_commission_dialog", {sales_order:order});
		const summary = data.order_summary;
		const value = v=>esc(v == null || v === "" ? "—" : String(v));
		const money = v=>v == null ? "—" : value(format_currency(v, summary.currency));
		const description = v=>value(window.strip_html(v || ""));
		let editing = data.editable && ["未设置","草稿"].includes(data.status), dirty=false, busy=false, closing=false;
		const dialogFields = [
			{fieldname:"heading",fieldtype:"HTML",options:`<p>${esc(order)} · ${esc(data.customer)} · ${esc(data.status)}</p><a href="/app/sales-order/${encodeURIComponent(order)}" target="_blank" rel="noopener">查看销售订单</a>`},
			{fieldname:"order_summary",fieldtype:"HTML",options:`
				<div class="my-3"><h5>订单概览（只读）</h5>
				<p>订单日期：${value(summary.transaction_date)}　业务负责人：${value(summary.primary_sales_person || "未关联业务人员")}</p>
				<p>订单未税金额：${money(summary.net_total)}　税额：${money(summary.total_taxes_and_charges)}　订单含税总额：${money(summary.grand_total)}　币种：${value(summary.currency)}</p>
				${summary.currency !== data.company_currency ? `<p>订单本位币未税金额：${value(format_currency(summary.base_net_total, data.company_currency))}　订单本位币含税总额：${value(format_currency(summary.base_grand_total, data.company_currency))}</p>` : ""}
				<p class="text-muted">计提基数及提成金额使用本位币 ${value(data.company_currency)}，按所选计提依据计算。</p></div>
				<details open><summary>订单商品明细（只读，共 ${summary.items.length} 行）</summary>
				<div class="table-responsive" style="max-height:300px;overflow:auto"><table class="table table-bordered"><thead><tr><th>产品编码</th><th>产品名称</th><th>规格 / 描述</th><th>数量</th><th>单位</th><th>单价</th><th>金额</th></tr></thead>
				<tbody>${summary.items.map(r=>`<tr><td>${value(r.item_code)}</td><td>${value(r.item_name)}</td><td style="white-space:pre-wrap">${description(r.description)}</td><td>${value(r.qty)}</td><td>${value(r.uom)}</td><td>${money(r.rate)}</td><td>${money(r.amount)}</td></tr>`).join("")}</tbody></table></div></details><hr>`},
		];
		if (data.personal) {
			dialogFields.push({fieldname:"result",fieldtype:"HTML",options:data.results.map(r=>`<p>本人提成：${esc(r.commission_amount)}；可再发放：${esc(r.available_amount)}；净发放：${esc(r.paid_amount)}；待追回：${r.recoverable_amount == null ? "待复核" : esc(r.recoverable_amount)}</p>`).join("")});
		} else {
			for (const def of [
				{fieldname:"basis_type",label:"计提依据",fieldtype:"Select",options:"订单未税金额\n已开票未税金额\n实际回款金额\n财务确认毛利\n手工指定基数"},
				{fieldname:"release_condition",label:"发放条件",fieldtype:"Select",options:"确认后可发放\n全额回款后可发放\n随回款比例发放"},
				{fieldname:"receipt_tax_mode",label:"回款口径",fieldtype:"Select",options:"含税实收\n折算未税回款"},
				{fieldname:"manual_basis",label:"手工基数（本位币）",fieldtype:"Currency",depends_on:"eval:doc.basis_type === '手工指定基数'"},
				{fieldname:"manual_reason",label:"手工原因",fieldtype:"Small Text",depends_on:"eval:doc.basis_type === '手工指定基数'"},
				{fieldname:"revision_reason",label:"修订原因",fieldtype:"Small Text"},
			]) dialogFields.push({...def,default:data[def.fieldname],read_only:!editing});
			dialogFields.push({fieldname:"sales_people",label:"人员提成分配",fieldtype:"Table",read_only:!editing,in_place_edit:true,data:data.sales_people,fields:[
				{fieldname:"sales_person",label:"业务人员",fieldtype:"Link",options:"Sales Person",in_list_view:1,reqd:1},
				{fieldname:"commission_rate",label:"比例（%）",fieldtype:"Percent",in_list_view:1},
				{fieldname:"remark",label:"备注",fieldtype:"Data",in_list_view:1},
			]});
			dialogFields.push({fieldname:"preview",fieldtype:"HTML"});
		}
		const d = new frappe.ui.Dialog({title:"订单提成分配",size:"extra-large",fields:dialogFields});
		const payload = ()=>{
			const v=d.get_values(); if (!v) throw new Error("请填写必填字段");
			return {sales_order:order,name:data.name || null,modified:data.modified || null,...Object.fromEntries(["basis_type","release_condition","receipt_tax_mode","manual_basis","manual_reason","revision_reason"].map(k=>[k,v[k]])),sales_people:(v.sales_people || []).map(r=>({sales_person:r.sales_person,commission_rate:r.commission_rate,remark:r.remark}))};
		};
		async function run(fn) {if(busy)return;busy=true;d.get_primary_btn().prop("disabled",true);try{await fn();}finally{busy=false;d.get_primary_btn().prop("disabled",false);}}
		async function reopen() {dirty=false;closing=true;d.hide();await load();await open(order);}
		if (!data.personal) {
			const preview = r=>d.fields_dict.preview.$wrapper.html(r.source_ready ? `<p>计提基数：${esc(r.basis_amount)} ${esc(data.company_currency)}；提成合计：${esc(r.commission_total)}</p>${(r.sales_people || []).map(p=>`<p>${esc(p.sales_person)}：${esc(p.commission_amount)}</p>`).join("")}` : `<p class="text-warning">${esc(r.source_message || "来源待核对")}</p>`);
			preview(data);
			if (editing) {
				d.set_primary_action("保存草稿",()=>run(async()=>{await call("save_order_commission_dialog",{payload:payload()});await reopen();}));
				d.add_custom_action("刷新试算",()=>run(async()=>{const p=payload();const signature=JSON.stringify(p);const r=await call("preview_order_commission",{payload:p});if(signature===JSON.stringify(payload()))preview(r);}));
				if(data.name) d.add_custom_action("确认提成",()=>run(async()=>{
					if(dirty){frappe.msgprint("请先保存草稿再确认");return;}
					frappe.confirm("确认后调整需创建修订，是否继续？",()=>run(async()=>{await frappe.call({method:"china_finance.services.sales_commission.confirm_commission",args:{name:data.name,modified:data.modified}});await reopen();}));
				}));
			} else if(data.editable) d.set_primary_action("调整提成",()=>{
				for(const key of ["basis_type","release_condition","receipt_tax_mode","manual_basis","manual_reason","revision_reason","sales_people"]) d.set_df_property(key,"read_only",0);
				d.set_df_property("revision_reason","reqd",1);dirty=true;editing=true;
				d.set_primary_action("保存修订草稿",()=>run(async()=>{await call("save_order_commission_dialog",{payload:payload()});await reopen();}));
			});
		}
		d.$wrapper.on("hide.bs.modal",e=>{if(closing)return;if(busy){e.preventDefault();return;}if(dirty){e.preventDefault();frappe.confirm("放弃未保存的修改？",()=>{dirty=false;d.hide();});}});
		d.show();
		d.$wrapper.on("change input", "input,textarea,select",()=>{if(editing)dirty=true;});
	}
	page.set_primary_action("刷新",()=>load());
	load();
};
