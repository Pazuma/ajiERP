import json
import os
import re

import frappe
import requests

from .account_mapping import allowed_base_accounts


def get_ai_assistant_settings():
    try:
        if not frappe.db.exists("DocType", "AI Assistant Settings"):
            return {}
        doc = frappe.get_single("AI Assistant Settings")
        if not int(doc.get("enabled") or 0):
            return {}

        def password(fieldname):
            if not doc.get(fieldname):
                return None
            try:
                return doc.get_password(fieldname, raise_exception=False)
            except TypeError:
                try:
                    return doc.get_password(fieldname)
                except Exception:
                    return None
            except Exception:
                return None

        return {
            "default_platform": doc.get("default_platform"),
            "chat_timeout": doc.get("chat_timeout"),
            "tool_summary_timeout": doc.get("tool_summary_timeout"),
            "voucher_timeout": doc.get("voucher_timeout"),
            "qwen_base_url": doc.get("qwen_base_url"),
            "qwen_api_key": password("qwen_api_key"),
            "qwen_model": doc.get("qwen_model"),
            "deepseek_base_url": doc.get("deepseek_base_url"),
            "deepseek_api_key": password("deepseek_api_key"),
            "deepseek_model": doc.get("deepseek_model"),
            "glm_base_url": doc.get("glm_base_url"),
            "glm_api_key": password("glm_api_key"),
            "glm_model": doc.get("glm_model"),
        }
    except Exception:
        return {}


def get_ai_setting(key):
    return get_ai_assistant_settings().get(key)


def get_ai_provider_config(platform):
    settings = get_ai_assistant_settings()
    platform = (platform or settings.get("default_platform") or "qwen").lower()
    providers = {
        "qwen": {
            "label": "DashScope/Qwen",
            "base_url": settings.get("qwen_base_url") or frappe.conf.get("dashscope_base_url") or os.environ.get("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": settings.get("qwen_api_key") or frappe.conf.get("dashscope_api_key") or frappe.conf.get("qwen_api_key") or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"),
            "model": settings.get("qwen_model") or frappe.conf.get("dashscope_model") or frappe.conf.get("qwen_model") or frappe.conf.get("ai_assistant_model") or os.environ.get("DASHSCOPE_MODEL") or os.environ.get("QWEN_MODEL"),
            "default_model": "qwen-plus",
            "config_hint": "AI Assistant Settings / dashscope_api_key",
            "model_config_hint": "AI Assistant Settings / qwen_model",
            "env_hint": "DASHSCOPE_API_KEY",
            "model_env_hint": "QWEN_MODEL",
        },
        "deepseek": {
            "label": "DeepSeek",
            "base_url": settings.get("deepseek_base_url") or frappe.conf.get("deepseek_base_url") or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1",
            "api_key": settings.get("deepseek_api_key") or frappe.conf.get("deepseek_api_key") or os.environ.get("DEEPSEEK_API_KEY"),
            "model": settings.get("deepseek_model") or frappe.conf.get("deepseek_model") or frappe.conf.get("ai_assistant_model") or os.environ.get("DEEPSEEK_MODEL"),
            "default_model": "deepseek-chat",
            "config_hint": "AI Assistant Settings / deepseek_api_key",
            "model_config_hint": "AI Assistant Settings / deepseek_model",
            "env_hint": "DEEPSEEK_API_KEY",
            "model_env_hint": "DEEPSEEK_MODEL",
        },
        "glm4": {
            "label": "GLM-4",
            "base_url": settings.get("glm_base_url") or frappe.conf.get("glm_base_url") or frappe.conf.get("bigmodel_base_url") or os.environ.get("GLM_BASE_URL") or os.environ.get("BIGMODEL_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4",
            "api_key": settings.get("glm_api_key") or frappe.conf.get("glm_api_key") or frappe.conf.get("bigmodel_api_key") or os.environ.get("GLM_API_KEY") or os.environ.get("BIGMODEL_API_KEY"),
            "model": settings.get("glm_model") or frappe.conf.get("glm_model") or frappe.conf.get("bigmodel_model") or frappe.conf.get("ai_assistant_model") or os.environ.get("GLM_MODEL") or os.environ.get("BIGMODEL_MODEL"),
            "default_model": "glm-4",
            "config_hint": "AI Assistant Settings / glm_api_key",
            "model_config_hint": "AI Assistant Settings / glm_model",
            "env_hint": "GLM_API_KEY",
            "model_env_hint": "GLM_MODEL",
        },
    }
    return providers.get(platform, providers["qwen"])


@frappe.whitelist()
def get_public_ai_engine_config():
    settings = get_ai_assistant_settings()
    default_platform = (settings.get("default_platform") or "qwen").lower()
    platforms = {}
    for platform in ["qwen", "deepseek", "glm4"]:
        provider = get_ai_provider_config(platform)
        platforms[platform] = {
            "label": provider.get("label"),
            "base_url": provider.get("base_url"),
            "model": provider.get("model") or provider.get("default_model"),
        }
    return {
        "default_platform": default_platform if default_platform in platforms else "qwen",
        "platforms": platforms,
    }


def build_ai_error_reply(provider, detail):
    return (
        "⚠️ 连接大脑时发生异常 / Connection Error：<br><br>"
        f"<b>{provider['label']} {detail}</b><br><br>"
        f"请检查站点配置 <code>{provider['config_hint']}</code> 或环境变量 <code>{provider['env_hint']}</code>。"
        f"模型可通过 <code>{provider['model_config_hint']}</code> 或 <code>{provider['model_env_hint']}</code> 配置。"
    )


def extract_financial_voucher_file_url(message):
    text = str(message or "")
    has_intent = any(keyword in text for keyword in ["财务凭证", "凭证报表", "科目余额表", "资产负债表", "利润表", "financial voucher", "voucher"])
    if not has_intent:
        return None

    patterns = [
        r"路径[:：]\s*(/[^\s，,。]+)",
        r"path[:：]\s*(/[^\s，,。]+)",
        r"file_url[:=]\s*(/[^\s，,。]+)",
        r"(/private/files/[^\s，,。]+)",
        r"(/files/[^\s，,。]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def is_simple_greeting(message):
    text = re.sub(r"[\s!！。,.，?？~～]+", "", str(message or "").lower())
    greetings = {"你好", "您好", "hi", "hello", "hey", "在吗", "早", "早上好", "下午好", "晚上好"}
    return text in greetings


def build_local_greeting_reply(lang="zh"):
    if lang == "en":
        return "Hello. I am DeeplinkERP AI Assistant. You can ask me to query ERPNext documents, run financial checks, track costs, inspect assets, or generate financial voucher reports."
    if lang == "es":
        return "Hola. Soy DeeplinkERP AI Assistant. Puede pedirme consultar documentos de ERPNext, revisar finanzas, analizar costos, inspeccionar activos o generar reportes contables."
    return "您好，我是 DeeplinkERP AI Assistant。您可以让我查询 ERPNext 单据、做财务体检、成本追踪、资产盘点，或上传银行流水生成财务凭证报表。"


def should_attach_erp_tools(message):
    text = str(message or "").lower()
    keywords = [
        "销售", "订单", "发票", "采购", "入库", "出库", "库存", "供应商", "报价", "月报",
        "催款", "逾期", "财务", "资产", "成本", "支出", "利润", "负债", "低库存",
        "sales", "invoice", "purchase", "stock", "inventory", "asset", "cost", "overdue", "report",
    ]
    return any(keyword in text for keyword in keywords)


def _configured_timeout(settings_key, conf_key, default):
    try:
        return int(get_ai_setting(settings_key) or frappe.conf.get(conf_key) or default)
    except Exception:
        return default


def ai_chat_timeout():
    return _configured_timeout("chat_timeout", "ai_assistant_chat_timeout", 45)


def ai_tool_summary_timeout():
    return _configured_timeout("tool_summary_timeout", "ai_assistant_tool_summary_timeout", 60)


def ai_voucher_classification_timeout():
    return _configured_timeout("voucher_timeout", "ai_assistant_voucher_timeout", 180)


def parse_model_json_array(content):
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("模型没有返回 JSON 数组。")
    return parsed


def parse_model_json_object(content):
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("模型没有返回 JSON 对象。")
    return parsed


def build_financial_voucher_header_classifier(provider, selected_model):
    if not provider.get("api_key"):
        return None

    def classify(cell_values):
        url = f"{provider['base_url'].rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"}
        system_prompt = (
            "你是银行 Excel 表头识别助手。只判断单元格表头对应的标准字段。"
            "标准字段只能是：入账日期、转出金额、转入金额、余额、对方单位、对方账号、摘要、用途。"
            "返回严格 JSON 对象，key 为标准字段名，value 为该字段在输入列表中的索引，索引从 0 开始。"
            "无法确定的字段不要返回。不要 Markdown，不要解释。"
        )
        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(list(cell_values or []), ensure_ascii=False)},
            ],
            "temperature": 0.0,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=ai_chat_timeout())
        response.raise_for_status()
        result_json = response.json()
        content = result_json["choices"][0]["message"].get("content", "")
        return parse_model_json_object(content)

    return classify


def build_financial_voucher_ai_classifier(provider, selected_model):
    if not provider.get("api_key"):
        return None

    def classify(candidates):
        if not candidates:
            return {}

        url = f"{provider['base_url'].rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"}
        allowed_accounts = allowed_base_accounts()
        system_prompt = (
            "你是中国小企业会计凭证分类助手。只根据银行交易摘要、用途、对方单位、对方账号、方向和金额判断会计科目。"
            "必须返回严格 JSON 数组，不要 Markdown，不要解释。"
            '每项格式：{"id": string, "debit_account": string, "credit_account": string, "confidence": number, "reason": string}。'
            "允许使用基础科目或带明细的子科目，例如 管理费用-办公费、应付账款-某公司、其他应付款-某人。"
            "支出 direction=out 时贷方必须是 银行存款；收入 direction=in 时借方必须是 银行存款。"
            f"基础科目只能来自：{', '.join(allowed_accounts)}。"
            "无法确定时使用 fallback_debit_account/fallback_credit_account，并把 confidence 设为 0.5。"
        )
        suggestions = {}
        batch_size = 40
        for start in range(0, len(candidates), batch_size):
            batch = candidates[start:start + batch_size]
            payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
                ],
                "temperature": 0.1,
            }
            response = requests.post(url, headers=headers, json=payload, timeout=ai_voucher_classification_timeout())
            response.raise_for_status()
            result_json = response.json()
            content = result_json["choices"][0]["message"].get("content", "")
            rows = parse_model_json_array(content)

            candidate_ids = {item["id"] for item in batch}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item_id = row.get("id")
                if item_id in candidate_ids:
                    suggestions[item_id] = row
        return suggestions

    return classify
