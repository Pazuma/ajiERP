import frappe

from .erp_queries import query_recent_documents_by_name


# =========================================================
# 🛠️ 极其强大的本地业务工具箱 (十五大金刚 - 终极安全与权限防线版)
# =========================================================

# --- 销售模块 ---
def get_recent_sales_orders(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_sales_orders", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}

def get_recent_sales_invoices(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_sales_invoices", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}


# --- 库存与预警模块 ---
def get_recent_purchase_receipts(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_purchase_receipts", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}

def get_recent_delivery_notes(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_delivery_notes", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}

def get_low_stock_warnings(limit=10, threshold=10):
    try:
        req_limit = int(limit) if limit else 10
        limit = min(req_limit, 50)
        threshold = float(threshold) if threshold else 10.0

        bins = frappe.db.sql("""
            SELECT item_code, warehouse, actual_qty
            FROM `tabBin`
            WHERE actual_qty <= %s
            ORDER BY actual_qty ASC
            LIMIT %s
        """, (threshold, limit), as_dict=True)

        if not bins:
            return {"text": f"报告老板：目前系统内各大仓库没有发现库存小于或等于 {threshold} 的商品，库存状况极其健康！", "data": []}

        result_str = f"⚠️ **极其重要的低库存预警**（实际库存 <= {threshold}，受性能保护最高展示 {limit} 条）：\n"
        warning_data = []
        for b in bins:
            result_str += f"- 商品编码: [{b.item_code}](/app/item/{b.item_code}), 仓库: {b.warehouse}, 当前实际库存: **{b.actual_qty}**\n"
            warning_data.append({"商品编码": b.item_code, "所在仓库": b.warehouse, "实际库存量": float(b.actual_qty), "预警警戒线": threshold})
            
        return {"text": result_str, "data": warning_data}
    except Exception as e: return {"text": f"执行低库存预警扫描失败：{str(e)}", "data": []}

# --- 采购模块 ---
def get_recent_supplier_quotations(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_supplier_quotations", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}

def get_recent_purchase_orders(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_purchase_orders", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}

def get_recent_purchase_invoices(limit=5, start_date=None, end_date=None):
    try:
        return query_recent_documents_by_name("get_recent_purchase_invoices", limit, start_date, end_date)
    except Exception as e:
        return {"text": f"查询失败：{str(e)}", "data": []}


# --- 财务及分析模块 ---
def generate_sales_monthly_report(target_month=None):
    try:
        if not target_month:
            target_month = frappe.utils.nowdate()[:7] 
            
        target_month_like = f"{target_month}%"

        overall_stats = frappe.db.sql("""
            SELECT COUNT(name) as total_orders, SUM(grand_total) as total_revenue
            FROM `tabSales Order`
            WHERE transaction_date LIKE %s AND docstatus < 2
        """, (target_month_like,), as_dict=True)[0]

        total_orders = overall_stats.get('total_orders') or 0
        total_revenue = overall_stats.get('total_revenue') or 0.0

        if total_orders == 0:
            return {"text": f"报告老板：经过极其仔细的盘点，系统在 {target_month} 月份没有产生任何销售订单数据。", "data": []}

        top_customers = frappe.db.sql("""
            SELECT customer, SUM(grand_total) as revenue, COUNT(name) as order_count
            FROM `tabSales Order`
            WHERE transaction_date LIKE %s AND docstatus < 2
            GROUP BY customer
            ORDER BY revenue DESC
            LIMIT 5
        """, (target_month_like,), as_dict=True)

        result_str = f"这是 {target_month} 月份的极其详尽的销售业绩汇总数据：\n\n"
        result_str += f"- **总订单数**: {total_orders} 笔\n"
        result_str += f"- **总销售额**: ￥{total_revenue:,.2f}\n\n"
        
        result_str += "👑 **Top 5 客户贡献榜**：\n"
        report_data = []
        for idx, c in enumerate(top_customers):
            result_str += f"  {idx+1}. 客户: **{c.customer}** - 订单: {c.order_count}笔, 贡献金额: ￥{c.revenue:,.2f}\n"
            report_data.append({
                "统计月份": target_month, "排名": idx + 1, "大客户名称": c.customer,
                "下单总笔数": c.order_count, "总贡献金额(元)": float(c.revenue)
            })

        result_str += "\n老板，请根据以上极其精准的数据，写一份极其专业、有商业洞察的销售月报总结，并用漂亮的 Markdown 结构（如加粗、表格）展现出来！"
        return {"text": result_str, "data": report_data}
    except Exception as e: return {"text": f"执行销售月报聚合分析失败：{str(e)}", "data": []}

def get_overdue_sales_invoices(limit=10):
    try:
        req_limit = int(limit) if limit else 10
        limit = min(req_limit, 50)
        
        overdue_invoices = frappe.db.sql("""
            SELECT name, customer, posting_date, due_date, grand_total, outstanding_amount, DATEDIFF(CURDATE(), due_date) as overdue_days
            FROM `tabSales Invoice`
            WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < CURDATE()
            ORDER BY overdue_days DESC, outstanding_amount DESC
            LIMIT %s
        """, (limit,), as_dict=True)

        if not overdue_invoices:
            return {"text": "🎉 报告老板：系统内极其干净！没有任何逾期未收的销售账款，现金流极其健康！", "data": []}

        total_overdue = sum([float(i.outstanding_amount) for i in overdue_invoices])

        result_str = f"🚨 **极其紧急的催款雷达警告！**\n"
        result_str += f"以下是当前系统内拖欠时间最长的账款单据（防爆破最高展示 {limit} 笔），请务必尽快安排财务催收：\n\n"
        
        report_data = []
        for i in overdue_invoices:
            result_str += f"- 客户: **{i.customer}** | 发票: [{i.name}](/app/sales-invoice/{i.name}) | 逾期天数: **{i.overdue_days}天** | 未收金额: **￥{i.outstanding_amount:,.2f}**\n"
            report_data.append({
                "发票编号": i.name, "大客户名称": i.customer, "开票日期": str(i.posting_date),
                "最晚收款日": str(i.due_date), "发票总金额(元)": float(i.grand_total),
                "拖欠未付金额(元)": float(i.outstanding_amount), "已逾期天数": int(i.overdue_days)
            })

        result_str += f"\n💰 **总计预警待收金额**: **￥{total_overdue:,.2f}**\n"
        result_str += "\n老板，我已经为您整理了极度详细的 Excel 催款清单，请直接点击下方按钮导出，以便发送给销售或财务部门进行精准催收！"
        
        return {"text": result_str, "data": report_data}
    except Exception as e: return {"text": f"执行智能催款雷达扫描失败：{str(e)}", "data": []}

def get_financial_health_summary():
    try:
        gl_summary = frappe.db.sql("""
            SELECT a.root_type, SUM(gle.debit) as total_debit, SUM(gle.credit) as total_credit
            FROM `tabGL Entry` gle
            JOIN `tabAccount` a ON gle.account = a.name
            WHERE gle.is_cancelled = 0
            GROUP BY a.root_type
        """, as_dict=True)

        assets, liabilities, income, expense = 0.0, 0.0, 0.0, 0.0

        for row in gl_summary:
            if row.root_type == 'Asset':
                assets += float(row.total_debit or 0) - float(row.total_credit or 0)
            elif row.root_type == 'Liability':
                liabilities += float(row.total_credit or 0) - float(row.total_debit or 0)
            elif row.root_type == 'Income':
                income += float(row.total_credit or 0) - float(row.total_debit or 0)
            elif row.root_type == 'Expense':
                expense += float(row.total_debit or 0) - float(row.total_credit or 0)

        net_profit = income - expense

        result_str = "🏥 **企业极其核心的财务体检简报**：\n\n"
        result_str += f"- **总资产 (Assets)**: ￥{assets:,.2f}\n"
        result_str += f"- **总负债 (Liabilities)**: ￥{liabilities:,.2f}\n"
        result_str += f"- **累计收入 (Income)**: ￥{income:,.2f}\n"
        result_str += f"- **累计支出 (Expense)**: ￥{expense:,.2f}\n"
        result_str += f"- **当前账面净利润 (Net Profit)**: **￥{net_profit:,.2f}**\n\n"

        if net_profit < 0:
            result_str += "⚠️ **极其严肃的洞察警报**：老板，咱们目前的账面净利润处于**亏损状态**！请密切关注现金流储备，并核查近期大额支出科目！\n"
        elif net_profit > 0 and assets > liabilities:
            result_str += "✅ **极其振奋的洞察报告**：老板，公司目前的资产负债极其健康，账面实现**盈利**！请继续保持极其凶猛的增长势头！\n"
        else:
            result_str += "💡 **架构师洞察**：老板，目前利润为正，但请同步关注资产负债率，确保资金链极其充沛。\n"

        report_data = [{
            "体检日期": str(frappe.utils.today()),
            "总资产(元)": assets, "总负债(元)": liabilities,
            "总计收入(元)": income, "总计支出(元)": expense, "净利润(元)": net_profit
        }]

        return {"text": result_str, "data": report_data}
    except Exception as e: return {"text": f"执行财务体检失败：{str(e)}", "data": []}

def get_cost_center_expenses(cost_center=None, target_month=None, limit=10):
    try:
        req_limit = int(limit) if limit else 10
        limit = min(req_limit, 50)
        
        conditions = ["a.root_type = 'Expense'", "gle.is_cancelled = 0"]
        values = []

        if target_month:
            conditions.append("gle.posting_date LIKE %s")
            values.append(f"{target_month}%")
        
        if cost_center:
            conditions.append("gle.cost_center LIKE %s")
            values.append(f"%{cost_center}%")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT gle.account, gle.cost_center, SUM(gle.debit - gle.credit) as net_expense
            FROM `tabGL Entry` gle
            JOIN `tabAccount` a ON gle.account = a.name
            WHERE {where_clause}
            GROUP BY gle.account, gle.cost_center
            HAVING net_expense > 0
            ORDER BY net_expense DESC
            LIMIT %s
        """
        values.append(limit)

        expenses = frappe.db.sql(query, tuple(values), as_dict=True)

        if not expenses:
            return {"text": f"🎉 报告老板：在指定条件（月份：{target_month or '全部'}，成本中心：{cost_center or '全部'}）下没有发现任何支出记录！", "data": []}

        total_expense = sum([float(e.net_expense) for e in expenses])

        result_str = f"💸 **极其清晰的成本“烧钱”追踪明细**（月份：{target_month or '全部'} | 成本中心：{cost_center or '全部'} | 防爆破展示前 {limit} 项）：\n\n"
        
        report_data = []
        for e in expenses:
            result_str += f"- 科目: **{e.account}** | 成本中心: {e.cost_center} | 净支出: **￥{e.net_expense:,.2f}**\n"
            report_data.append({
                "统计月份": target_month or "全部",
                "成本中心": e.cost_center or "未指定",
                "支出科目": e.account,
                "净支出金额(元)": float(e.net_expense)
            })

        result_str += f"\n🔥 **总计排查出上述科目的总支出**: **￥{total_expense:,.2f}**\n"
        result_str += "\n老板，我已经为您揪出了极其具体的花销科目！请结合上述数据，为各部门下达极其严格的成本管控指令！"
        
        return {"text": result_str, "data": report_data}
    except Exception as e: return {"text": f"执行成本追踪扫描失败：{str(e)}", "data": []}

def get_asset_inventory_snapshot():
    try:
        valid_columns = frappe.db.get_table_columns("Asset")
        
        value_field = "0" 
        for field in ["gross_purchase_amount", "gross_purchase_cost", "purchase_amount", "value_after_depreciation"]:
            if field in valid_columns:
                value_field = field
                break

        department_field = "department" if "department" in valid_columns else "''"
        location_field = "location" if "location" in valid_columns else "''"
        asset_name_field = "asset_name" if "asset_name" in valid_columns else "item_code"

        query = f"""
            SELECT 
                name, 
                item_code, 
                {asset_name_field} as asset_name, 
                status, 
                {value_field} as asset_value, 
                {department_field} as department, 
                {location_field} as location
            FROM `tabAsset`
            WHERE docstatus < 2
            ORDER BY asset_value DESC
        """
        assets = frappe.db.sql(query, as_dict=True)

        if not assets:
            return {"text": "报告老板：经过极其仔细的搜寻，系统内目前没有任何固定资产记录！公司处于“极简轻资产”状态，建议抓紧购置！", "data": []}

        total_value = sum([float(a.asset_value or 0) for a in assets])
        
        status_count = {}
        for a in assets:
            st = a.status or "状态未知"
            status_count[st] = status_count.get(st, 0) + 1

        result_str = f"🏢 **企业全局固定资产“硬家底”盘点快照**：\n\n"
        result_str += f"- **登记资产总数**: {len(assets)} 件\n"
        result_str += f"- **资产采购总原值**: **￥{total_value:,.2f}**\n\n"
        
        result_str += "📊 **资产状态分布**：\n"
        for st, count in status_count.items():
            result_str += f"- {st}: **{count}** 件\n"

        result_str += "\n💎 **核心高价值资产清单 (Top 10)**：\n"
        report_data = []
        for idx, a in enumerate(assets):
            if idx < 10:
                result_str += f"  {idx+1}. 资产: **{a.asset_name or a.item_code}** | 编号: [{a.name}](/app/asset/{a.name}) | 状态: {a.status} | 原值: ￥{float(a.asset_value or 0):,.2f}\n"
            
            report_data.append({
                "资产编号": a.name,
                "资产名称": a.asset_name or a.item_code,
                "当前状态": a.status,
                "所属部门": a.department or "未分配",
                "存放位置": a.location or "未分配",
                "价值(元)": float(a.asset_value or 0)
            })

        result_str += "\n老板，以上是咱们公司极其珍贵的核心家底！完整资产明细表已为您准备好，请直接点击下方按钮导出查阅！"
        
        return {"text": result_str, "data": report_data}
    except Exception as e: 
        return {"text": f"执行资产盘点雷达扫描失败：{str(e)}", "data": []}

def get_top_valuable_assets(limit=5):
    try:
        req_limit = int(limit) if limit else 5
        limit = min(req_limit, 50)
        
        valid_columns = frappe.db.get_table_columns("Asset")
        
        orig_field = "0"
        for field in ["gross_purchase_amount", "gross_purchase_cost", "purchase_amount"]:
            if field in valid_columns:
                orig_field = field
                break
                
        net_field = orig_field
        for field in ["value_after_depreciation", "net_value"]:
            if field in valid_columns:
                net_field = field
                break
                
        asset_name_field = "asset_name" if "asset_name" in valid_columns else "item_code"

        query = f"""
            SELECT 
                name, 
                {asset_name_field} as asset_name, 
                status, 
                {orig_field} as original_value, 
                {net_field} as net_value
            FROM `tabAsset`
            WHERE docstatus < 2
            ORDER BY net_value DESC
            LIMIT %s
        """
        assets = frappe.db.sql(query, (limit,), as_dict=True)

        if not assets:
            return {"text": "报告老板：系统内暂无任何有效资产数据，无法进行净值排行透视！", "data": []}

        result_str = f"📉 **固定资产“缩水”透视与净值排行榜 (防爆破最高展示 Top {limit})**：\n\n"
        
        report_data = []
        for idx, a in enumerate(assets):
            orig_val = float(a.original_value or 0)
            net_val = float(a.net_value or 0)
            
            shrink_rate = ((orig_val - net_val) / orig_val * 100) if orig_val > 0 else 0

            result_str += f"{idx+1}. **{a.asset_name or '未知资产'}** | 编号: [{a.name}](/app/asset/{a.name})\n"
            result_str += f"   - 采购原值: ￥{orig_val:,.2f} | **当前净值: ￥{net_val:,.2f}** | 已贬值: {shrink_rate:.1f}%\n\n"
            
            report_data.append({
                "资产编号": a.name,
                "资产名称": a.asset_name or '未知资产',
                "当前状态": a.status,
                "采购原值(元)": orig_val,
                "当前净值(元)": net_val,
                "贬值率(%)": round(shrink_rate, 2)
            })

        result_str += "老板，以上是目前公司账面上最值钱的家当！如需核对具体折旧明细，请导出 Excel 查阅。"
        return {"text": result_str, "data": report_data}
    except Exception as e: 
        return {"text": f"执行资产净值透视失败：{str(e)}", "data": []}

def get_employee_assets(employee_name=None):
    try:
        if not employee_name:
            return {"text": "报告老板：请告诉我具体要查询哪位员工的名字，我好去系统里帮您精准狙击！", "data": []}

        valid_columns = frappe.db.get_table_columns("Asset")
        
        custodian_field = "custodian" if "custodian" in valid_columns else ("employee" if "employee" in valid_columns else None)
        asset_name_field = "asset_name" if "asset_name" in valid_columns else "item_code"
        
        value_field = "0"
        for field in ["gross_purchase_amount", "gross_purchase_cost", "purchase_amount"]:
            if field in valid_columns:
                value_field = field
                break

        if not custodian_field:
            return {"text": "⚠️ 数据库字段不兼容：当前 ERPNext 版本资产表中没有找到『保管人/员工』相关字段，无法执行离职交接核查！", "data": []}

        query = f"""
            SELECT 
                name, 
                item_code, 
                {asset_name_field} as asset_name, 
                status, 
                {value_field} as asset_value,
                {custodian_field} as custodian
            FROM `tabAsset`
            WHERE docstatus < 2 AND {custodian_field} LIKE %s
        """
        assets = frappe.db.sql(query, (f"%{employee_name}%",), as_dict=True)

        if not assets:
            return {"text": f"🎉 报告老板：经过系统彻查，员工 **{employee_name}** 名下目前没有挂载任何公司固定资产，可以放心办理离职交接！", "data": []}

        total_value = sum([float(a.asset_value or 0) for a in assets])

        result_str = f"🏃‍♂️ **员工【{employee_name}】名下资产防流失追踪报告**：\n\n"
        result_str += f"⚠️ **极其严肃的警告**：查出该员工名下挂有 **{len(assets)}** 件未归还/正在使用的公司资产，总原值约 **￥{total_value:,.2f}**，请务必在离职前追回！\n\n"
        result_str += "📦 **应收回设备清单**：\n"
        
        report_data = []
        for idx, a in enumerate(assets):
            result_str += f"  {idx+1}. 资产名称: **{a.asset_name or a.item_code}** | 编号: [{a.name}](/app/asset/{a.name}) | 状态: {a.status}\n"
            
            report_data.append({
                "被查员工": employee_name,
                "资产编号": a.name,
                "资产名称": a.asset_name or a.item_code,
                "当前状态": a.status,
                "系统登记者": a.custodian,
                "采购原值(元)": float(a.asset_value or 0)
            })

        result_str += "\n老板，为了防止公司财产流失，我已经为您一键生成了极其标准的《离职资产交接单》，请直接点击下方按钮导出，火速发给 HR 和行政部门！"
        
        return {"text": result_str, "data": report_data}
    except Exception as e: 
        return {"text": f"执行员工资产追踪雷达扫描失败：{str(e)}", "data": []}
