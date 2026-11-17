frappe.query_reports["China Cost Summary"] = {
 filters: [
  {fieldname:"company", label:__("Company"), fieldtype:"Link", options:"Company", reqd:1, default:frappe.defaults.get_user_default("Company")},
  {fieldname:"from_date", label:"开票开始日期", fieldtype:"Date", reqd:1, default:frappe.datetime.year_start()},
  {fieldname:"to_date", label:"开票截止日期", fieldtype:"Date", reqd:1, default:frappe.datetime.get_today()},
  {fieldname:"production_from_date", label:"制造入库开始日期", fieldtype:"Date", reqd:1, default:frappe.datetime.year_start()},
  {fieldname:"production_to_date", label:"制造入库截止日期", fieldtype:"Date", reqd:1, default:frappe.datetime.get_today()},
  {fieldname:"view", label:"核算视图", fieldtype:"Select", options:"订单成本与毛利\n工单成本\n待核算项", default:"订单成本与毛利"},
  {fieldname:"sales_order", label:"销售订单", fieldtype:"Link", options:"Sales Order"},
  {fieldname:"work_order", label:"生产工单", fieldtype:"Link", options:"Work Order"},
 ],
 formatter(value, row, column, data, default_formatter) {
  if (column.fieldname === "source" && value) {
   return String(value).split(", ").map(name => {
    const doctype = data.work_order ? "Stock Entry" : (name === data.invoice ? "Sales Invoice" : "Stock Ledger Entry");
    return frappe.utils.get_form_link(doctype, name, true, frappe.utils.escape_html(name));
   }).join(", ");
  }
  if (["sales_cost", "profit", "margin", "production_cost", "unit_cost"].includes(column.fieldname) && data[column.fieldname] == null) return "";
  const formatted = default_formatter(value, row, column, data);
  if (column.fieldname !== "status" || !value) return formatted;
  const color = value === "已匹配" ? "green" : "orange";
  return `<span class="indicator-pill ${color}"><span class="ellipsis">${frappe.utils.escape_html(value)}</span></span>`;
 },
};
