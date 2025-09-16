# josfe/ui_controls/ui_settings.py
import frappe
from frappe.model.document import Document

class UISettings(Document):
    def validate(self):
        """Enforce uniqueness per (role, doctype_name)."""
        if not self.role or not self.doctype_name:
            frappe.throw("Both <b>Role</b> and <b>Doctype</b> must be set.")

        exists = frappe.db.exists(
            "UI Settings",
            {
                "role": self.role,
                "doctype_name": self.doctype_name,
                "name": ["!=", self.name],
            },
        )
        if exists:
            frappe.throw(
                f"UI Settings already defined for Role <b>{self.role}</b> "
                f"and Doctype <b>{self.doctype_name}</b>."
            )
