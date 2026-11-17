(() => {
    const api = "client_akivision.api.product_cost_quotation.";
    const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
    const display = (value, currency) => format_currency(value || 0, currency);
    frappe.ui.form.on("Product Cost Material", {
        async item_code(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            if (!row.item_code) return;
            const {message} = await frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom", "item_group"]);
            await frappe.model.set_value(cdt, cdn, {description: message.item_name, category: message.item_group,
                stock_uom: message.stock_uom, purchase_uom: message.stock_uom, conversion_factor: 1,
                price_currency: frm.doc.currency, price_exchange_rate: 1});
        },
        async pricing_rule(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            if (!row.item_code || !row.pricing_rule) return;
            const {message} = await frappe.call({method: api + "get_material_pricing_options", args: {item_code: row.item_code}});
            const rule = message.rules[row.pricing_rule];
            if (!rule) return frappe.msgprint(__("所选规则不可读取或未关联当前物料供应商"));
            let conversion = 1;
            if (rule.uom !== row.stock_uom) {
                const {message: item} = await frappe.call({method: "frappe.client.get", args: {doctype: "Item", name: row.item_code}});
                conversion = item.uoms.find((u) => u.uom === rule.uom)?.conversion_factor || 0;
            }
            await frappe.model.set_value(cdt, cdn, {supplier: rule.supplier, price_currency: rule.currency,
                purchase_uom: rule.uom, minimum_order_qty: rule.minimum_order_qty, conversion_factor: conversion,
                price_exchange_rate: rule.currency === frm.doc.currency ? 1 : 0, price_basis: "Supplier Rule"});
        },
        price_basis(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            if (row.price_basis === "Manual" && !row.price_currency) {
                frappe.model.set_value(cdt, cdn, {price_currency: frm.doc.currency, price_exchange_rate: 1});
            }
        },
    });
    frappe.ui.form.on("Product Cost Quotation", {
        setup(frm) {
            frm.$wrapper.on("dirty.pcq-summary", () => render(frm));
            frm.set_query("bom_no", () => ({filters: {item: frm.doc.item_code || "", is_active: 1}}));
            frm.set_query("reference_work_order", () => ({filters: {production_item: frm.doc.item_code || "", company: frm.doc.company}}));
            frm.set_query("pricing_rule", "materials", (doc, cdt, cdn) => ({filters: {item_code: locals[cdt][cdn].item_code || "", supplier: locals[cdt][cdn].supplier || "", disabled: 0}}));
        },
        onload(frm) {
            if (frm.__pcq_last_item_code === undefined) frm.__pcq_last_item_code = frm.doc.item_code || "";
            if (frm.is_new() && !(frm.doc.scenarios || []).some((row) => row.quantity)) {
                frm.clear_table("scenarios");
                [50, 100, 200, 500].forEach((quantity) => frm.add_child("scenarios", {quantity}));
                frm.refresh_field("scenarios");
            }
            if (frm.is_new() && !frm.doc.company) {
                const company = frappe.defaults.get_user_default("Company");
                if (company) frm.set_value("company", company);
            }
        },
        refresh(frm) {
            pricing_visibility(frm);
            render(frm);
            render_quote(frm);
            render_actual(frm);
            exchange_buttons(frm);
            if (frm.doc.docstatus === 0) {
                frm.add_custom_button(__("读取来源 / 刷新预览"), () => refresh_sources(frm));
                frm.add_custom_button(__("保存并核算"), async () => {
                    await frm.save();
                    frappe.show_alert({message: __("已按当前来源完成服务端核算"), indicator: "green"});
                });
                if (frm.doc.reference_work_order && !frm.is_new()) {
                    frm.add_custom_button(__("采用工单参考工时"), () => adopt_actual_hours(frm));
                }
            }
            if (frm.doc.docstatus === 1 && frm.doc.item_code
                && ["System Manager", "Accounts Manager"].some((role) => frappe.user.has_role(role))) {
                frm.add_custom_button(__("设为产品默认成本报价"), async () => {
                    const {message} = await frappe.call({
                        method: "client_akivision.api.product_cost_quotation.set_default_product_quote",
                        args: {name: frm.doc.name}, freeze: true,
                    });
                    frappe.show_alert({message: __("已将 {0} 设为产品 {1} 的默认成本报价", [message.quotation, message.item_code]), indicator: "green"});
                }, __("产品成本报价"));
            }
            if (!frm.is_new()) {
                frm.add_custom_button(__("复制为新版本"), async () => {
                    if (frm.is_dirty()) {
                        frappe.msgprint(__("请先保存当前修改"));
                        return;
                    }
                    const copied = frappe.model.copy_doc(frm.doc);
                    copied.docstatus = 0;
                    copied.previous_version = frm.doc.name;
                    copied.amended_from = null;
                    copied.estimate_acknowledged = 0;
                    copied.snapshot_hash = "";
                    frappe.set_route("Form", copied.doctype, copied.name);
                });
                if (frm.doc.docstatus !== 2) {
                    [["内部完整核算表", "internal"], ["客户报价单", "customer"]].forEach(([label, audience]) => {
                        frm.add_custom_button(__(label), () => {
                            if (frm.is_dirty()) return frappe.msgprint(__("请先保存后导出"));
                            window.open(`/api/method/${api}export_cost_quotation?name=${encodeURIComponent(frm.doc.name)}&audience=${audience}`, "_blank");
                        }, __("导出"));
                    });
                }
            }
            frm.set_intro(frm.doc.docstatus === 1
                ? __("已确认：成本与报价已保存为快照。来源变化请复制新版本后主动刷新。")
                : __("草稿：保存后核算。缺价与未确认口径会标记为不完整；读取来源不会回写原单据。"), "blue");
        },
        pricing_method: pricing_visibility,
        async item_code(frm) {
            const selectedItem = frm.doc.item_code;
            const previousItem = frm.__pcq_last_item_code || "";
            const requestId = (frm.__pcq_item_context_request || 0) + 1;
            frm.__pcq_item_context_request = requestId;
            frm.__pcq_last_item_code = selectedItem || "";
            if (!selectedItem) return;

            const {message} = await frappe.call({method: api + "get_source_context", args: {source_type: "Item", source_name: selectedItem}});
            // Link-field events are not serialized: ignore responses for products
            // that the user has already replaced with a newer selection.
            if (requestId !== frm.__pcq_item_context_request || frm.doc.item_code !== selectedItem) return;
            await frm.set_value({product_name: message.product_name, bom_no: message.bom_no || ""});

            const changedProduct = previousItem && previousItem !== selectedItem;
            const hasOldBomRows = [...(frm.doc.materials || []), ...(frm.doc.operations || [])]
                .some((row) => /^BOM(?:OP)?:/.test(row.source_key || ""));
            if (changedProduct && !frm.is_new() && hasOldBomRows) {
                frm.__pcq_pending_product_refresh = true;
                render(frm);
                frm.set_intro(__("产品已更换，当前风险提示仍基于旧来源明细。请在来源对比中核对并应用材料/工时；无来源键的手工行会保留。"), "orange");
                frappe.confirm(
                    __("产品已从 {0} 更换为 {1}。当前风险提示仍可能显示旧产品的材料/工时。现在保存草稿并打开来源对比吗？对比中会预选材料和工时；只有点击“应用选中分组”后才会替换，未选择的手工行不会被删除。", [previousItem, selectedItem]),
                    () => refresh_sources(frm, ["materials", "operations"], true)
                );
            }
        },
        async customer(frm) {
            const customer = frm.doc.customer;
            await frm.set_value({contact: "", contact_phone: ""});
            if (!customer) return;

            const {message: customer_data} = await frappe.db.get_value(
                "Customer", customer, ["customer_primary_contact", "mobile_no"]
            );
            let contact_name = customer_data?.customer_primary_contact;
            if (!contact_name) {
                const {message: contacts} = await frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Contact",
                        fields: ["name"],
                        filters: [
                            ["Dynamic Link", "link_doctype", "=", "Customer"],
                            ["Dynamic Link", "link_name", "=", customer],
                        ],
                        limit_page_length: 2,
                    },
                });
                if (contacts?.length === 1) contact_name = contacts[0].name;
            }
            if (!contact_name) {
                if (customer_data?.mobile_no) await frm.set_value("contact_phone", customer_data.mobile_no);
                return;
            }

            const {message: contact_data} = await frappe.db.get_value(
                "Contact", contact_name, ["mobile_no", "phone"]
            );
            await frm.set_value({
                contact: contact_name,
                contact_phone: contact_data?.mobile_no || contact_data?.phone || customer_data.mobile_no || "",
            });
        },
        async company(frm) {
            if (!frm.doc.company || !frm.is_new()) return;
            const {message} = await frappe.db.get_value("Company", frm.doc.company, "default_currency");
            if (message?.default_currency) await frm.set_value({currency: message.default_currency, exchange_rate: 1});
        },
    });

    function pricing_visibility(frm) {
        frm.toggle_display("target_margin", frm.doc.pricing_method === "Target Margin");
        frm.toggle_display("cost_ratio", frm.doc.pricing_method === "Cost Ratio");
    }

    frappe.ui.form.on("Product Cost Scenario", {
        show_in_customer_quote: render_quote,
        quantity: render_quote,
        final_tax_inclusive_price: render_quote,
        scenarios_remove: render_quote,
    });

    function render_quote(frm) {
        const rows = frm.doc.scenarios || [];
        frm.fields_dict.quote_preview.$wrapper.html(`<h5>对客报价阶梯</h5><div class="pcq-matrix"><table class="table table-bordered"><thead><tr><th>客户展示</th><th>批量</th><th>最终含税单价</th></tr></thead><tbody>${rows.map(row => `<tr><td><input type="checkbox" data-quote-row="${esc(row.name)}" ${row.show_in_customer_quote ? "checked" : ""} ${frm.doc.docstatus !== 0 ? "disabled" : ""}></td><td>${esc(row.quantity)}</td><td>${display(row.final_tax_inclusive_price, frm.doc.currency)}</td></tr>`).join("")}</tbody></table></div><p class="text-muted">批量和最终报价在成本核算页维护；勾选控制客户文件展示，不影响内部成本。</p>`);
        frm.fields_dict.quote_preview.$wrapper.find("input").on("change", function () {
            frappe.model.set_value("Product Cost Scenario", this.dataset.quoteRow, "show_in_customer_quote", this.checked ? 1 : 0);
        });
    }

    function exchange_buttons(frm) {
        if (frm.is_new()) return;
        const exchange = "client_akivision.api.product_cost_quotation_import.";
        const download = (method, extra = "") => {
            if (frm.is_dirty()) return frappe.msgprint("请先保存后操作");
            window.open(`/api/method/${exchange}${method}?name=${encodeURIComponent(frm.doc.name)}${extra}`, "_blank");
        };
        frm.add_custom_button("可回导数据包", () => download("export_import_data"), "导出");
        if (frm.doc.docstatus !== 0) return;
        for (const [kind, label] of [["customer", "客户报价"], ["internal", "内部核算"]]) {
            frm.add_custom_button(`下载${label}导入模板`, () => download("download_import_template", `&template_type=${kind}`), "导入");
        }
        frm.add_custom_button("上传并预览Excel", () => {
            if (frm.is_dirty()) return frappe.msgprint("请先保存后导入");
            new frappe.ui.FileUploader({is_private: 1, restrictions: {allowed_file_types: [".xlsx"], max_file_size: 5 * 1024 * 1024},
                on_success: async file => {
                    const modified = frm.doc.modified;
                    const {message: preview} = await frappe.call({method: exchange + "preview_import", type: "POST", args: {name: frm.doc.name, file_url: file.file_url, expected_modified: modified}, freeze: true});
                    const labels = {main: "报价及参数", scenarios: "阶梯", materials: "手工材料", operations: "手工工时", investments: "手工投入"};
                    const groups = [...new Set(preview.changes.map(c => c.group))];
                    const dialog = new frappe.ui.Dialog({title: "导入差异预览", size: "extra-large", fields: [
                        {fieldname: "summary", fieldtype: "HTML"},
                        ...groups.map(group => ({fieldname: group, label: labels[group], fieldtype: "Check", default: 1}))],
                        primary_action_label: "确认应用选中分组", primary_action: async values => {
                            if (preview.errors.length) return frappe.msgprint("请修正文件错误后重新预览");
                            await frappe.call({method: exchange + "apply_import", type: "POST", args: {name: frm.doc.name, preview_id: preview.preview_id, expected_modified: modified, selected_groups: groups.filter(g => values[g])}, freeze: true});
                            dialog.hide(); await frm.reload_doc(); frappe.show_alert("导入完成，已重新核算");
                        }});
                    dialog.fields_dict.summary.$wrapper.html(`<p>只更新明确提供的值，不删除原行；来源行不可覆盖。新增无ID行请核对，重复上传可能重复追加。</p>${preview.errors.map(e => `<p class="text-danger">${esc(e)}</p>`).join("")}<table class="table table-bordered"><tr><th>分组/行</th><th>字段</th><th>当前值</th><th>导入值</th></tr>${preview.changes.map(c => Object.entries(c.values).map(([key,value]) => `<tr><td>${esc(labels[c.group])}/${esc(c.line)}</td><td>${esc(key)}</td><td>${esc(c.before[key])}</td><td>${esc(value)}</td></tr>`).join("")).join("")}</table>`);
                    dialog.show();
                    if (preview.errors.length || !groups.length) dialog.get_primary_btn().prop("disabled", true);
                }});
        }, "导入");
    }

    async function refresh_sources(frm, defaultSelectedGroups = [], productChanged = false) {
        if (frm.is_dirty() || frm.is_new()) await frm.save();
        const {message: preview} = await frappe.call({method: api + "preview_source_refresh", args: {name: frm.doc.name}, freeze: true});
        const names = {materials: "材料及供应商价格", operations: "制造工时", investments: "项目投入"};
        const groupByName = Object.fromEntries(preview.groups.map((group) => [group.fieldname, group]));
        const materialChangeCount = (preview.diffs?.materials || []).length;
        const selectionNotice = productChanged
            ? `<div class="alert alert-danger"><strong>${esc("预览不会自动替换明细。")}</strong> ${esc(`当前材料明细：${groupByName.materials?.old_count || 0} 行；新产品来源：${groupByName.materials?.new_count || 0} 行；识别到 ${materialChangeCount} 项来源变更。请保留“材料及供应商价格”勾选，并点击下方“应用选中分组”，旧来源材料才会被替换。无来源键的手工行会保留。`)}</div>`
            : `<div class="alert alert-info">${esc("此处仅预览来源差异；存在差异的分组会自动勾选。检查勾选项后点击“应用选中分组”才会写入；未选分组保持不变，无来源键的手工行会保留。")}</div>`;
        const dialog = new frappe.ui.Dialog({
            title: __("核对来源变更"), size: "large",
            fields: [
                {fieldname: "summary", fieldtype: "HTML"},
                ...preview.groups.map((group) => ({fieldname: group.fieldname, fieldtype: "Check", label: `${names[group.fieldname]}：现有${group.old_count}行 → 来源${group.new_count}行`, default: defaultSelectedGroups.includes(group.fieldname) || group.has_changes || group.old_count === 0 ? 1 : 0})),
            ],
            primary_action_label: __("应用选中分组"),
            async primary_action(values) {
                const selected_changes = preview.groups.filter((g) => values[g.fieldname]).map((g) => g.fieldname);
                if (!selected_changes.length) return frappe.msgprint(__("请至少选择一个分组"));
                if (productChanged && !selected_changes.includes("materials")) {
                    return frappe.msgprint(__("产品已更换，必须勾选“材料及供应商价格”才能移除旧产品来源材料。"));
                }
                const result = await frappe.call({method: api + "apply_source_refresh", args: {name: frm.doc.name, expected_modified: preview.modified, selected_changes}, freeze: true});
                dialog.hide();
                frm.__pcq_pending_product_refresh = false;
                await frm.reload_doc();
                frappe.show_alert({message: __("来源明细已应用：材料 {0} 行，工时 {1} 行，投入 {2} 行。无来源键的手工行已保留。", [result.message.counts.materials, result.message.counts.operations, result.message.counts.investments]), indicator: "green"}, 8);
            },
        });
        const sourceRows = ["materials", "operations", "investments"].map((key) => {
            const rows = preview.source[key] || [];
            const labels = {item_code: "物料", description: "名称", qty_per_unit: "单台用量", supplier: "供应商", pricing_rule: "价格规则", operation: "工序", charging_basis: "计费方式", standard_hours: "标准小时", hourly_rate: "小时费率", project: "项目", expense_type: "投入", actual_amount: "已发生", budget_reference: "预算参考", allocation_percent: "分摊比例(%)"};
            const keys = Object.keys(labels).filter((field) => rows.some((row) => row[field] !== undefined));
            return `<details><summary>${esc(names[key])}（${rows.length}行）</summary><div class="table-responsive"><table class="table table-bordered"><thead><tr>${keys.map((field) => `<th>${esc(labels[field])}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${keys.map((field) => `<td>${esc(__(String(row[field] ?? "")))}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
        }).join("");
        const differences = Object.entries(preview.diffs || {}).map(([key, rows]) => {
            const doctype = frm.fields_dict[key].df.options;
            return `<h6>${esc(names[key])}变更</h6><ul>${rows.map((row) => `<li>${esc(row.action)} ${esc(row.source_key)}${row.changes.map((change) => `<div>${esc(__(frappe.meta.get_docfield(doctype, change.fieldname)?.label || change.fieldname))}：${esc(change.before ?? "空")} → ${esc(change.after ?? "空")}</div>`).join("")}</li>`).join("") || "<li>无来源变更</li>"}</ul>`;
        }).join("");
        dialog.fields_dict.summary.$wrapper.html(`${selectionNotice}<p class="text-warning">${esc(preview.warning)}</p><p style="white-space:pre-wrap">${esc(preview.source.source_warnings)}</p>${differences}${sourceRows}`);
        dialog.show();
        // Dialog Check fields can ignore `default` when their initial value is
        // empty. Set values after rendering so the product-change selection is
        // visible and included in primary_action(values).
        const initialValues = Object.fromEntries(preview.groups.map((group) => [
            group.fieldname,
            defaultSelectedGroups.includes(group.fieldname) || group.has_changes || group.old_count === 0 ? 1 : 0,
        ]));
        await dialog.set_values(initialValues);
    }

    function render(frm) {
        const rows = frm.doc.scenarios || [];
        const context = JSON.parse(frm.doc.source_context_json || "{}");
        const stale = Object.entries(context).some(([group, origin]) => ["materials", "operations"].includes(group) && (frm.doc[group] || []).some(r => r.source_key) && (origin[0] !== (frm.doc.item_code || null) || origin[1] !== (frm.doc.bom_no || null)));
        if (stale) frm.__pcq_pending_product_refresh = true;
        const metrics = [["单台材料成本", "material_unit_cost"], ["单台制造费用", "manufacturing_unit_cost"], ["单台研发分摊", "investment_unit_cost"], ["单台完整成本", "full_unit_cost"], ["建议含税价（不含研发）", "suggested_price_without_rd"], ["建议含税价（含研发）", "suggested_price_with_rd"], ["最终含税报价", "final_tax_inclusive_price"], ["回本数量", "payback_qty"]];
        const details = rows.map(row => JSON.parse(row.detail_snapshot_json || "{}"));
        const categories = [...new Set(details.flatMap(d => (d.materials || []).map(m => m.category || "其他材料")))];
        const categoryRows = categories.map(category => `<tr><th>材料 · ${esc(category)}</th>${rows.map((row, i) => `<td>${display((details[i].materials || []).filter(m => (m.category || "其他材料") === category).reduce((s,m) => s + m.charged_cost, 0) / (row.quantity || 1), frm.doc.currency)}</td>`).join("")}</tr>`).join("");
        const lossRow = `<tr><th>承担余量及损耗（材料内含）</th>${rows.map((row,i) => `<td>${display((details[i].materials || []).reduce((s,m) => s + m.charged_cost - m.consumed_cost, 0) / (row.quantity || 1), frm.doc.currency)}</td>`).join("")}</tr>`;
        const hoursRow = `<tr><th>制造工时（小时/台）</th>${rows.map((row,i) => `<td>${esc((details[i].operations || []).reduce((s,op,j) => s + op.hours / (frm.doc.operations[j]?.charging_basis === "Per Unit" ? 1 : (row.quantity || 1)), 0).toFixed(4))}</td>`).join("")}</tr>`;
        const content = categoryRows + lossRow + hoursRow + metrics.map(([label, key]) => `<tr><th>${esc(label)}</th>${rows.map((row) => `<td>${key === "payback_qty" ? esc(row[key] || "见风险提示") : display(row[key], frm.doc.currency)}</td>`).join("")}</tr>`).join("");
        const staleSourceNotice = frm.__pcq_pending_product_refresh
            ? `<p class="text-danger">${esc("产品已更换；以下风险提示仍按旧来源明细核算。请刷新并应用新产品来源后再确认。")}</p>` : "";
        const number = value => Number(value || 0).toLocaleString("zh-CN", {minimumFractionDigits: 2, maximumFractionDigits: 2});
        const selected = rows.find(row => row.name === frm.__pcq_selected_scenario) || rows.find(row => row.show_in_customer_quote) || rows[0];
        const pending = frm.is_dirty() || frm.is_new();
        const available = selected && !pending && !frm.__pcq_pending_product_refresh && selected.completeness !== "Incomplete";
        const money = value => available ? number(value) : "—";
        const core = [["单台完整成本", "full_unit_cost"], ["建议含税报价", "suggested_price_with_rd"], ["最终含税报价", "final_tax_inclusive_price"]];
        const matrix = body => `<div class="pcq-matrix pcq-core-matrix"><table class="table table-bordered"><thead><tr><th>产品批量</th>${rows.map(row => `<th>${esc(row.quantity)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
        const state = pending ? "有未保存修改，请保存并核算" : frm.__pcq_pending_product_refresh ? "来源待刷新" : !selected ? "请先添加批量" : selected.completeness === "Incomplete" ? "资料不完整，请补充成本明细" : selected.warnings || "资料完整";
        const card = (label, value) => `<div class="pcq-card"><span>${label}</span><strong>${value}</strong></div>`;
        const parts = [["材料", "material_unit_cost", "materials_tab"], ["制造", "manufacturing_unit_cost", "operations_tab"], ["研发分摊", "investment_unit_cost", "investments_tab"]];
        const wrapper = frm.fields_dict.scenario_matrix.$wrapper;
        wrapper.html(`${staleSourceNotice}<div class="pcq-overview"><div class="pcq-summary-toolbar"><span class="${available ? "text-success" : "text-warning"}">${esc(state)}${frm.doc.estimate_acknowledged && frm.doc.estimate_reason ? " · 已确认估算依据" : " · 待确认估算依据"}</span><label>参考批量 <select class="pcq-quantity" aria-label="参考批量">${rows.map(row => `<option value="${esc(row.name)}" ${row === selected ? "selected" : ""}>${esc(row.quantity)}</option>`).join("")}</select></label></div><p class="text-muted small">币种：${esc(frm.doc.currency || "未设置")} · 成本为未税口径，报价为含税口径 · 金额取自最近一次保存核算</p><div class="pcq-cards">${card("单台完整成本",money(selected?.full_unit_cost))}${card("最终含税报价",money(selected?.final_tax_inclusive_price))}${card("预计毛利率",available ? `${number(selected.gross_margin)}%` : "—")}${card("该批预计毛利",money(selected?.batch_gross_profit))}</div><div class="pcq-cost-parts">${parts.map(([label,key,target],i) => `<button type="button" class="pcq-cost-part pcq-part-${i}" data-section="${target}" style="flex-grow:${available ? Math.max(Number(selected[key]) || 0, 1) : 1}">${label} <strong>${money(selected?.[key])}</strong></button>`).join("")}</div><div class="pcq-detail-links">${[["材料采购", "materials_tab", "materials"], ["制造工时", "operations_tab", "operations"], ["研发投入", "investments_tab", "investments"], ["编辑批量与报价", "scenario_edit_section", "scenarios"]].map(([label,target,key]) => `<button type="button" class="btn btn-default btn-sm" data-section="${target}">${label}（${(frm.doc[key] || []).length}）</button>`).join(" ")}</div></div><h5>批量对比</h5>${matrix(core.map(([label,key]) => `<tr><th>${label}</th>${rows.map(row => `<td>${pending || row.completeness === "Incomplete" ? "—" : number(row[key])}</td>`).join("")}</tr>`).join("") + `<tr><th>客户展示</th>${rows.map(row => `<td>${row.show_in_customer_quote ? "是" : "否"}</td>`).join("")}</tr><tr><th>核算状态</th>${rows.map(row => `<td class="${row.completeness === "Incomplete" ? "text-danger" : ""}">${esc(pending ? "待保存核算" : row.warnings || (row.completeness === "Complete" ? "完整" : "估算"))}</td>`).join("")}</tr>`)}<details class="pcq-extra-metrics"><summary>展开详细指标（成本分类、工时、回本数量）</summary>${matrix(content)}</details>`);
        wrapper.find(".pcq-quantity").on("change", function () { frm.__pcq_selected_scenario = this.value; render(frm); });
        wrapper.find("[data-section]").on("click", function () {
            const section = frm.fields_dict[this.dataset.section];
            section?.collapse?.(false);
            (section?.wrapper || section?.$wrapper)?.get(0)?.scrollIntoView({behavior: "smooth", block: "start"});
        });
        ["materials", "operations", "investments", "scenarios"].forEach((key) => {
            const grid = frm.fields_dict[key].grid;
            grid.wrapper.off("click.pcq-detail").on("click.pcq-detail", ".pcq-detail", async function () {
                if (frm.is_dirty() || frm.is_new()) return frappe.msgprint(__("请先保存，以查看与快照一致的明细"));
                const child_row = $(this).attr("data-row");
                const {message} = await frappe.call({method: api + "get_line_detail", args: {name: frm.doc.name, child_row}});
                const dialog = new frappe.ui.Dialog({title: __("核算依据与来源详情"), size: "extra-large", fields: [{fieldname: "detail", fieldtype: "HTML"}]});
                dialog.fields_dict.detail.$wrapper.html(detail_html(message, frm.doc.currency));
                dialog.show();
            });
        });
        $(frm.wrapper).off("grid-row-render.pcq-detail").on("grid-row-render.pcq-detail", (event, grid_row) => {
            if (!grid_row.doc || !["Product Cost Material", "Product Cost Operation", "Product Cost Investment", "Product Cost Scenario"].includes(grid_row.doc.doctype)) return;
            const $row = $(grid_row.row);
            if ($row.find(".pcq-detail").length) return;
            $row.find(".grid-row-check").after(`<button type="button" class="btn btn-xs btn-default pcq-detail" data-row="${esc(grid_row.doc.name)}" title="查看核算详情">ⓘ</button>`);
        });
    }

    function detail_html(data, currency) {
        const row = data.row;
        const fields = frappe.meta.get_docfields(row.doctype).filter((field) => !["Section Break", "Column Break", "Tab Break", "HTML", "Code", "Long Text"].includes(field.fieldtype) && !field.hidden && row[field.fieldname] !== undefined);
        let html = `<table class="table table-bordered"><tbody>${fields.map((field) => `<tr><th>${esc(__(field.label))}</th><td>${esc(__(String(row[field.fieldname] ?? "")))}</td></tr>`).join("")}</tbody></table>`;
        const calculations = data.calculations || [];
        if (calculations.length) {
            html += `<h5>各产品批量的物料采购与承担成本</h5><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>产品批量</th><th>采购单位需求量</th><th>采购量</th><th>折算未税单价</th><th>承担成本</th><th>余量金额</th><th>价格依据</th></tr></thead><tbody>${calculations.map(({quantity, detail: d}) => `<tr><td>${esc(quantity)}</td><td>${esc(d.needed_qty)}</td><td>${esc(d.purchase_qty)}</td><td>${display(d.rate, currency)}</td><td>${display(d.charged_cost, currency)}</td><td>${display(d.surplus_cost, currency)}</td><td>${esc(d.error || d.pricing?.formula || d.pricing?.reason || "")}</td></tr>`).join("")}</tbody></table></div>`;
        }
        const refs = JSON.parse(row.source_refs || "[]");
        if (refs.length) html += `<h5>来源记录</h5><ul>${refs.map((ref) => `<li><a href="/app/${encodeURIComponent(frappe.router.slug(ref.doctype))}/${encodeURIComponent(ref.name)}" target="_blank" rel="noopener">${esc(__(ref.doctype))} / ${esc(ref.name)}</a>${ref.row ? ` · 明细 ${esc(ref.row)}` : ""}</li>`).join("")}</ul>`;
        if (row.detail_snapshot_json) {
            const snapshot = JSON.parse(row.detail_snapshot_json);
            html += `<h5>本批量材料承担成本</h5><table class="table table-bordered"><tbody>${(snapshot.materials || []).map((d) => `<tr><td>${esc(d.item_code)}</td><td>${d.error ? esc(d.error) : display(d.charged_cost, currency)}</td></tr>`).join("")}</tbody></table>`;
        }
        return html;
    }

    function render_actual(frm) {
        const field = frm.fields_dict.actual_reference_view;
        if (!field) return;
        const actual = JSON.parse(frm.doc.actual_reference_json || "{}");
        frm.fields_dict.actual_reference_header?.$wrapper.html(actual.work_order
            ? `<h5>历史工单：${esc(actual.work_order)}</h5><p class="text-warning pcq-reference-note">${esc(actual.note)}</p>`
            : '<p class="text-muted">未关联生产工单；预测核算不要求已有生产记录。</p>');
        if (!actual.work_order) return field.$wrapper.empty();
        const standard = (frm.doc.operations || []).reduce((sum, row) => sum + (row.charging_basis === "Per Unit" ? row.standard_hours || 0 : (actual.planned_qty > 0 ? (row.standard_hours || 0) / actual.planned_qty : 0)), 0);
        const actual_unit = actual.produced_qty > 0 && actual.actual_labor_hours > 0 ? actual.actual_labor_hours / actual.produced_qty : null;
        field.$wrapper.html(`<h6>历史工单数据</h6><table class="table table-bordered pcq-reference-table"><tbody>
            <tr><th>工单状态 / 完工数量</th><td>${esc(__(actual.status || ""))} / ${esc(actual.produced_qty || 0)}</td></tr>
            <tr><th>本单标准小时/台</th><td>${esc(standard.toFixed(4))}</td></tr>
            <tr><th>历史实际人工小时/台</th><td>${actual_unit === null ? "数据不足，暂不换算" : esc(actual_unit.toFixed(4))}</td></tr>
            <tr><th>历史实际耗用材料参考</th><td>${display(actual.actual_material_reference, actual.currency)}</td></tr>
            <tr><th title="不另加到工单作业成本">历史自定义人工参考</th><td>${display(actual.actual_labor_cost, actual.currency)}</td></tr>
            <tr><th>历史工单作业成本</th><td>${display(actual.actual_operating_cost, actual.currency)}</td></tr></tbody></table>`);
    }

    function adopt_actual_hours(frm) {
        const actual = JSON.parse(frm.doc.actual_reference_json || "{}");
        if (!(actual.produced_qty > 0) || !(actual.actual_labor_hours > 0)) {
            return frappe.msgprint(__("工单没有有效完工数量和实际人工小时，不能换算单台工时"));
        }
        frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("采用依据（将新增工序，请删除/调整重复标准人工）"), reqd: 1},
            {fieldname: "hourly_rate", fieldtype: "Float", label: __("本单小时费率"), reqd: 1}], async (values) => {
            frm.add_child("operations", {operation: "历史人工参考", charging_basis: "Per Unit", standard_hours: actual.actual_labor_hours / actual.produced_qty,
                hourly_rate: values.hourly_rate, included_cost_scope: "人工；已手工核对与现有工序不重复", manual_reason: values.reason,
                source_refs: JSON.stringify([{doctype: "Work Order", name: frm.doc.reference_work_order}])});
            frm.refresh_field("operations");
            frm.dirty();
        }, __("采用参考工时到本单"));
    }
})();
