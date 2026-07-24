import frappe


WORKFLOW_NAME = "Engineering Drawing Approval"
STATES = [
    ("Draft", "Manufacturing User"),
    ("Pending Approval", "Manufacturing Manager"),
    ("Finalized", "Manufacturing Manager"),
    ("Rejected", "Manufacturing User"),
    ("Obsolete", "Manufacturing Manager"),
]
TRANSITIONS = [
    ("Draft", "Submit for Approval", "Pending Approval", "Manufacturing User"),
    ("Pending Approval", "Approve and Finalize", "Finalized", "Manufacturing Manager"),
    ("Pending Approval", "Reject", "Rejected", "Manufacturing Manager"),
    ("Rejected", "Resume Editing", "Draft", "Manufacturing User"),
    ("Finalized", "Mark Obsolete", "Obsolete", "Manufacturing Manager"),
]


def execute():
    ensure_workflow_masters()
    workflow = frappe.db.get_value("Workflow", {"document_type": "Engineering Drawing", "is_active": 1}, "name")
    if workflow:
        return

    workflow = frappe.get_doc(
        {
            "doctype": "Workflow",
            "workflow_name": WORKFLOW_NAME,
            "document_type": "Engineering Drawing",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "status",
            "states": [
                {"state": state, "doc_status": "0", "allow_edit": role, "avoid_status_override": 0}
                for state, role in STATES
            ],
            "transitions": [
                {
                    "state": state,
                    "action": action,
                    "next_state": next_state,
                    "allowed": role,
                    "allow_self_approval": 0 if action == "Approve and Finalize" else 1,
                }
                for state, action, next_state, role in TRANSITIONS
            ],
        }
    )
    workflow.insert(ignore_permissions=True)


def ensure_workflow_masters():
    for state, _role in STATES:
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": get_style(state)}).insert(
                ignore_permissions=True
            )
        elif state == "Finalized":
            # Finalized is a positive outcome; ensure a pre-existing global
            # Workflow State does not render engineering drawings as gray.
            frappe.db.set_value("Workflow State", state, "style", "Success", update_modified=False)
    for _state, action, _next_state, _role in TRANSITIONS:
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
                ignore_permissions=True
            )


def get_style(state):
    return {
        "Draft": "Danger",
        "Pending Approval": "Warning",
        "Finalized": "Success",
        "Rejected": "Danger",
        "Obsolete": "Inverse",
    }[state]
