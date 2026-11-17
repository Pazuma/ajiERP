"""Deterministic quotation arithmetic. All amounts use the quotation currency."""
import json
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP


def number(value, label="数值"):
    try:
        result = Decimal(str(value if value not in (None, "") else 0))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label}必须为有效数字")
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label}必须为非负有限数字")
    return result


def rounded(value):
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def calculate(data, price_resolver):
    """Resolver returns {rate, ...evidence} for a row and purchase-UOM quantity."""
    tax = number(data.get("tax_rate"), "销售税率") / 100
    margin = number(data.get("target_margin"), "目标毛利率") / 100
    ratio = number(data.get("cost_ratio"), "成本占售价比例") / 100
    if margin >= 1 or ratio <= 0 or ratio > 1:
        raise ValueError("目标毛利率须小于100%，成本占售价比例须在0至100%之间")
    if not data.get("scenarios"):
        raise ValueError("请至少添加一个产品批量")
    results, quantities = [], set()
    for scenario in data["scenarios"]:
        quantity = number(scenario.get("quantity"), "产品批量")
        if not quantity or quantity in quantities:
            raise ValueError("产品批量须大于零且不能重复")
        quantities.add(quantity)
        warnings, missing, details = [], [], []
        material = procurement = surplus = Decimal(0)
        if not data.get("materials"):
            missing.append("未维护材料明细")
        for row in data.get("materials", []):
            label = row.get("item_code") or row.get("description") or "临时物料"
            needed = number(row.get("qty_per_unit"), label + "用量") * quantity
            conversion = number(row.get("conversion_factor"), "单位换算")
            if not needed or not conversion:
                missing.append(label + "：用量/单位换算缺失")
                continue
            loss = number(row.get("loss_rate"), "损耗率") / 100
            if loss >= 1:
                raise ValueError("损耗率须小于100%")
            if row.get("loss_method") == "Quantity":
                needed /= 1 - loss
            needed /= conversion
            multiple = number(row.get("pack_multiple") or 1, "包装倍数")
            ordered = max(needed, number(row.get("minimum_order_qty")))
            ordered = (ordered / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple
            try:
                evidence = price_resolver(row, ordered)
                rate = number(evidence.get("rate"), label + "单价")
                if not rate:
                    raise ValueError("未取得有效单价")
                fx = number(row.get("price_exchange_rate"), "价格汇率")
                if not fx:
                    raise ValueError("缺少价格汇率")
                rate *= fx
                if row.get("tax_basis") not in ("Inclusive", "Exclusive"):
                    raise ValueError("请确认采购价格含税/未税口径")
                if row.get("tax_basis") == "Inclusive":
                    if row.get("purchase_tax_rate") in (None, ""):
                        raise ValueError("含税采购价必须填写采购税率")
                    rate /= 1 + number(row.get("purchase_tax_rate")) / 100
            except ValueError as exc:
                missing.append(f"{label}：{exc}")
                details.append({"item_code": label, "error": str(exc), "row": row.get("name")})
                continue
            consumed, bought = needed * rate, ordered * rate
            charged = bought if row.get("surplus_policy") == "Charge Batch" else consumed
            if row.get("loss_method") == "Cost":
                charged *= 1 + loss
            material += charged
            procurement += bought
            surplus += bought - consumed
            details.append({"row": row.get("name"), "item_code": label,
                            "category": row.get("category") or "其他材料", "needed_qty": rounded(needed),
                            "purchase_qty": rounded(ordered), "rate": rounded(rate),
                            "consumed_cost": rounded(consumed), "procurement_cost": rounded(bought),
                            "charged_cost": rounded(charged), "surplus_cost": rounded(bought - consumed),
                            "pricing": evidence, "source_refs": row.get("source_refs")})
        manufacturing = Decimal(0)
        operations = []
        if not data.get("operations"):
            warnings.append("无制造工序；请确认不含制造费用的估算依据")
        for row in data.get("operations", []):
            overrides = row.get("tier_overrides_json") or "{}"
            try:
                overrides = json.loads(overrides) if isinstance(overrides, str) else overrides
                hours = number(overrides.get(format(quantity.normalize(), "f"), overrides.get(str(float(quantity)), row.get("standard_hours"))))
            except (ValueError, AttributeError, TypeError):
                raise ValueError("批量工时覆盖须为数量到小时的JSON对象")
            rate = number(row.get("hourly_rate"))
            if not hours or not rate or not row.get("included_cost_scope"):
                missing.append(f"{row.get('operation')}：缺少工时、费率或费率包含范围")
            cost = hours * rate * (quantity if row.get("charging_basis") == "Per Unit" else 1)
            manufacturing += cost
            operations.append({"operation": row.get("operation"), "hours": rounded(hours), "cost": rounded(cost)})
        investment_unit = rd_priced = remaining_total = Decimal(0)
        separate_total = Decimal(0)
        for row in data.get("investments", []):
            allocation = number(row.get("allocation_percent")) / 100
            if allocation > 1:
                raise ValueError("项目分摊比例不能超过100%")
            actual, future = number(row.get("actual_amount")), number(row.get("remaining_estimate"))
            if (actual or future) and not allocation:
                missing.append(f"{row.get('expense_type')}：请确认本产品分摊比例")
            remaining = max((actual + future) * allocation - number(row.get("recovered_amount")), Decimal(0))
            separate = number(row.get("separate_charge"))
            if row.get("recovery_method") == "Separate" and separate < remaining:
                missing.append(f"{row.get('expense_type')}：单独收费未覆盖待回收投入")
            separate_total += separate
            remaining = max(remaining - separate, Decimal(0))
            remaining_total += remaining
            if row.get("recovery_method") != "Separate":
                amortization = number(row.get("amortization_qty"))
                if remaining and not amortization:
                    missing.append(f"{row.get('expense_type')}：请填写研发回收数量")
                elif amortization:
                    unit = remaining / amortization
                    investment_unit += unit
                    rd_priced += unit * (1 + number(row.get("rd_markup_rate")) / 100)
        recurring = (material + manufacturing) / quantity
        full = recurring + investment_unit
        suggested = (full / (1 - margin) if data.get("pricing_method") == "Target Margin" else recurring / ratio + rd_priced) * (1 + tax)
        without = (recurring / (1 - margin) if data.get("pricing_method") == "Target Margin" else recurring / ratio) * (1 + tax)
        final = number(scenario.get("final_tax_inclusive_price"))
        if not scenario.get("price_override_reason") and final == number(scenario.get("suggested_price_with_rd")):
            final = Decimal(0)  # previously calculated automatic price follows changed costs
        final = final or suggested
        if abs(final - suggested) > Decimal("0.00001") and not scenario.get("price_override_reason"):
            missing.append("调整最终报价须填写依据")
        net = final / (1 + tax)
        contribution = net - recurring
        payback = (remaining_total / contribution).to_integral_value(rounding=ROUND_CEILING) if contribution > 0 else Decimal(0)
        if contribution <= 0:
            warnings.append("单位贡献不为正，无法回本")
        if quantity < number(data.get("minimum_sales_qty")):
            warnings.append("低于建议接单MOQ")
        if any(r.get("price_basis") == "Manual" for r in data.get("materials", [])):
            warnings.append("含手工价格估算")
        results.append({"quantity": rounded(quantity), "material_unit_cost": rounded(material / quantity),
                        "manufacturing_unit_cost": rounded(manufacturing / quantity),
                        "investment_unit_cost": rounded(investment_unit), "full_unit_cost": rounded(full),
                        "suggested_price_with_rd": rounded(suggested), "suggested_price_without_rd": rounded(without),
                        "final_tax_inclusive_price": rounded(final), "gross_margin": rounded((net - full) / net * 100) if net else 0,
                        "batch_gross_profit": rounded((net - full) * quantity), "payback_qty": rounded(payback),
                        "procurement_total": rounded(procurement), "surplus_total": rounded(surplus),
                        "completeness": "Incomplete" if missing else ("Estimated" if warnings else "Complete"),
                        "warnings": "；".join(missing + warnings), "missing": missing,
                        "detail_snapshot_json": json.dumps({"materials": details, "operations": operations,
                                                             "separate_charge": rounded(separate_total)}, ensure_ascii=False, default=str)})
    return results
