import frappe
import requests
import json
import re

from .i18n.translations import translate_headers
from .prompts.system import build_system_prompt, language_label
from .tools.registry import (
    dispatch_tool,
    get_tools,
    is_restricted_tool,
    is_valid_tool,
    tool_file_prefix,
)
from .voucher_generator import generate_financial_vouchers

from .tools.business_tools import (
    generate_sales_monthly_report,
    get_asset_inventory_snapshot,
    get_cost_center_expenses,
    get_employee_assets,
    get_financial_health_summary,
    get_low_stock_warnings,
    get_overdue_sales_invoices,
    get_recent_delivery_notes,
    get_recent_purchase_invoices,
    get_recent_purchase_orders,
    get_recent_purchase_receipts,
    get_recent_sales_invoices,
    get_recent_sales_orders,
    get_recent_supplier_quotations,
    get_top_valuable_assets,
)
from .model_client import (
    ai_chat_timeout,
    ai_tool_summary_timeout,
    build_ai_error_reply,
    build_financial_voucher_ai_classifier,
    build_financial_voucher_header_classifier,
    build_local_greeting_reply,
    extract_financial_voucher_file_url,
    get_ai_assistant_settings,
    get_ai_provider_config,
    get_ai_setting,
    get_public_ai_engine_config,
    is_simple_greeting,
    should_attach_erp_tools,
)
@frappe.whitelist()
def generate_financial_voucher_report(file_url, platform="qwen", model_id=None):
    user_roles = frappe.get_roles(frappe.session.user)
    is_boss = frappe.session.user == "Administrator" or "Administrator" in user_roles or "System Manager" in user_roles or "Accounts Manager" in user_roles
    if not is_boss:
        frappe.throw("当前账号无权生成财务凭证报表。")

    provider = get_ai_provider_config(platform)
    selected_model = provider.get("model") or model_id or provider.get("default_model")
    ai_classifier = build_financial_voucher_ai_classifier(provider, selected_model)
    header_classifier = build_financial_voucher_header_classifier(provider, selected_model)
    return generate_financial_vouchers(file_url, ai_classifier=ai_classifier, header_classifier=header_classifier)


def build_financial_voucher_response(tool_result, ai_classifier=None, provider_label=None, called_by_model=False):
    ai_log = (
        f"AI辅助判断采纳 {tool_result.get('ai_applied_count', 0)}/{tool_result.get('ai_candidate_count', 0)} 条。"
        if ai_classifier else f"{provider_label or '当前模型'} 未配置 API Key，已使用规则兜底生成。"
    )
    logs = [
        "财务凭证生成工具执行成功。",
        ai_log,
        f"识别交易 {tool_result['transaction_count']} 笔，生成分录 {tool_result['voucher_row_count']} 行。"
    ]
    if called_by_model:
        logs.insert(0, "大模型调用了：generate_financial_voucher_report。")

    return {
        "status": "success",
        "reply": tool_result["text"],
        "action_button": {
            "type": "download_file",
            "label": "⬇️ 下载财务报表",
            "url": tool_result.get("file_url"),
            "file_name": tool_result.get("file_name"),
        },
        "logs": logs
    }



def is_boss_user():
    user_roles = frappe.get_roles(frappe.session.user)
    return frappe.session.user == "Administrator" or "Administrator" in user_roles or "System Manager" in user_roles or "Accounts Manager" in user_roles


def _build_model_payload(message, provider, selected_model, is_boss, lang):
    current_date = frappe.utils.nowdate()
    target_language = language_label(lang)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(current_date, is_boss, provider["label"], target_language),
        },
        {"role": "user", "content": message},
    ]
    payload = {"model": selected_model, "messages": messages}
    if should_attach_erp_tools(message):
        payload.update({"tools": get_tools(is_boss), "tool_choice": "auto"})
    return payload


def _run_voucher_fast_path(voucher_file_url, is_boss, provider, selected_model):
    if not is_boss:
        return {
            "status": "success",
            "reply": "⚠️ 抱歉，您的账号当前无权访问该机密业务模块。",
            "logs": ["后端权限拦截：当前用户无权生成财务凭证报表。"],
        }
    ai_classifier = build_financial_voucher_ai_classifier(provider, selected_model) if provider.get("api_key") else None
    header_classifier = build_financial_voucher_header_classifier(provider, selected_model) if provider.get("api_key") else None
    tool_result = generate_financial_vouchers(
        voucher_file_url,
        ai_classifier=ai_classifier,
        header_classifier=header_classifier,
    )
    return build_financial_voucher_response(
        tool_result,
        ai_classifier=ai_classifier,
        provider_label=provider["label"],
    )


def _build_http_error_response(provider, error):
    status_code = error.response.status_code if error.response is not None else None
    if status_code == 401:
        detail = "API Key 无效、已过期或没有调用权限（401 Unauthorized）。"
    else:
        detail = f"接口返回 HTTP {status_code or '错误'}。"
    if provider:
        return {
            "status": "success",
            "reply": build_ai_error_reply(provider, detail),
            "logs": [f"{provider['label']} 调用失败：{detail}"],
        }
    return {
        "status": "success",
        "reply": f"⚠️ 连接大脑时发生异常 / Connection Error：<br><br><b>{detail}</b>",
        "logs": ["发生异常！"],
    }

# 💥 极其关键的修改：接收 JS 传来的 lang 语言参数！
@frappe.whitelist()
def chat(message, platform, model_id, lang="zh"):
    frappe.logger().info(f"AI 小助手接收到指令：[{message}]，准备呼叫：[{model_id}]，语言锁定为：[{lang}]")
    provider = None

    try:
        is_boss = is_boss_user()
        if is_simple_greeting(message):
            return {
                "status": "success",
                "reply": build_local_greeting_reply(lang),
                "logs": ["本地快速回复：寒暄消息未调用外部大模型。"],
            }

        provider = get_ai_provider_config(platform)
        selected_model = provider.get("model") or model_id or provider.get("default_model")
        voucher_file_url = extract_financial_voucher_file_url(message)
        if voucher_file_url:
            return _run_voucher_fast_path(voucher_file_url, is_boss, provider, selected_model)

        if not provider["api_key"]:
            return {
                "status": "success",
                "reply": build_ai_error_reply(provider, "缺少 API Key。"),
                "logs": [f"{provider['label']} 缺少 API Key 配置。"],
            }

        url = f"{provider['base_url'].rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"}
        payload = _build_model_payload(message, provider, selected_model, is_boss, lang)
        frappe.logger().info(f"AI 小助手实际调用模型：[{selected_model}]，平台：[{provider['label']}]")

        response = requests.post(url, headers=headers, json=payload, timeout=ai_chat_timeout())
        response.raise_for_status(); response_message = response.json()["choices"][0]["message"]
        if response_message.get("tool_calls"):
            return _handle_tool_call(response_message, payload, url, headers, provider, selected_model, is_boss, lang, voucher_file_url)

        return {
            "status": "success",
            "reply": response_message.get("content"),
            "logs": ["大模型未触发数据库查询，已获取常规智能回复！"],
        }
    except requests.exceptions.HTTPError as e:
        return _build_http_error_response(provider, e)
    except Exception as e:
        return {
            "status": "success",
            "reply": f"⚠️ 连接大脑时发生异常 / Connection Error：<br><br><b>{str(e)}</b>",
            "logs": ["发生异常！"],
        }

def _handle_tool_call(response_message, payload, url, headers, provider, selected_model, is_boss, lang, voucher_file_url=None):
    tool_call = response_message["tool_calls"][0]
    function_name = tool_call["function"]["name"]
    tool_call_id = tool_call["id"]

    try:
        args = json.loads(tool_call["function"].get("arguments", "{}"))
    except Exception:
        args = {}

    if not is_valid_tool(function_name):
        return {
            "status": "success",
            "reply": response_message.get("content") or "模型请求了未知工具，已取消执行。",
            "logs": [f"未知工具调用已拦截：{function_name}"],
        }

    if is_restricted_tool(function_name) and not is_boss:
        return {
            "status": "success",
            "reply": "⚠️ 抱歉，您的账号当前无权访问该机密业务模块。",
            "logs": ["后端权限拦截：当前用户无权调用机密业务工具。"],
        }

    context = {
        "provider": provider,
        "selected_model": selected_model,
        "voucher_file_url": voucher_file_url,
    }
    tool_result = dispatch_tool(function_name, args, context)

    if isinstance(tool_result, dict) and tool_result.get("status") in {"success", "missing_file"} and "reply" in tool_result:
        return tool_result

    messages = list(payload.get("messages") or [])
    messages.append(response_message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": function_name,
        "content": tool_result["text"],
    })

    summary_payload = {
        "model": payload["model"],
        "messages": messages,
    }
    second_response = requests.post(url, headers=headers, json=summary_payload, timeout=ai_tool_summary_timeout())
    second_response.raise_for_status()
    final_reply = second_response.json()["choices"][0]["message"]["content"]

    if "无权访问该机密业务模块" in final_reply:
        return {
            "status": "success",
            "reply": final_reply,
            "logs": ["后端检测到权限拦截回复，已取消导出按钮。"],
        }

    export_data = translate_headers(tool_result.get("data", []), lang)
    return {
        "status": "success",
        "reply": final_reply,
        "action_button": {
            "type": "export_excel",
            "label": "⬇️ Export Data / 导出数据",
            "data": export_data,
            "file_prefix": tool_file_prefix(function_name),
        },
        "logs": ["后端 Python 接口触发成功！", f"大模型调用了：{function_name}。"],
    }

