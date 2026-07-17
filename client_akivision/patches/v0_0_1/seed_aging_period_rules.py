import frappe


RULES = (
    ("30天内到期", 0, 30, "低风险"),
    ("31-60天逾期", 31, 60, "低风险"),
    ("61-90天逾期", 61, 90, "中风险"),
    ("91-180天逾期", 91, 180, "高风险"),
    ("180天以上逾期", 181, None, "高风险"),
)


def execute():
    """Add initial aging rules only when the administrator has not configured them."""
    if frappe.db.count("Aging Period Rule"):
        return
    for label, from_days, to_days, risk_level in RULES:
        frappe.get_doc(
            {
                "doctype": "Aging Period Rule",
                "label": label,
                "from_days": from_days,
                "to_days": to_days,
                "risk_level": risk_level,
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
