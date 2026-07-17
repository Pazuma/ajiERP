import frappe


RULES = (
    ("0-30 Days", 0, 30, "Low Risk"),
    ("31-90 Days", 31, 90, "Medium Risk"),
    ("91+ Days", 91, None, "High Risk"),
)


def execute():
    """Add initial purchase delay risk rules only when none have been configured."""
    if frappe.db.count("Purchase Delay Risk Rule"):
        return
    for label, from_days, to_days, risk_level in RULES:
        frappe.get_doc(
            {
                "doctype": "Purchase Delay Risk Rule",
                "label": label,
                "from_days": from_days,
                "to_days": to_days,
                "risk_level": risk_level,
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)
