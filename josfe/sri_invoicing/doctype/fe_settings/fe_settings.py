# apps/josfe/josfe/doctype/fe_settings/fe_settings.py

import frappe
from frappe.model.document import Document

class FESettings(Document):
    """Singleton DocType; business logic kept in helper(s) below."""
    pass

def get_settings():
    """Cache-friendly accessor for FE Settings singleton with sane defaults."""
    doc = frappe.get_single("FE Settings")
    # Ensure defaults if fields missing (older sites)
    return frappe._dict({
        "env_override": getattr(doc, "env_override", "") or "",
        "contingency_mode": int(getattr(doc, "contingency_mode", 0) or 0),
        "debug_logging": int(getattr(doc, "debug_logging", 0) or 0),
        "xml_subdir": getattr(doc, "xml_subdir", "sri_xml") or "sri_xml",
        "retry_max_attempts": int(getattr(doc, "retry_max_attempts", 5) or 5),
        "retry_backoff_seconds": int(getattr(doc, "retry_backoff_seconds", 30) or 30),
        "batch_size": int(getattr(doc, "batch_size", 20) or 20),
        "allow_test_stubs": int(getattr(doc, "allow_test_stubs", 0) or 0),
        "private_files_only": int(getattr(doc, "private_files_only", 1) or 1),
    })
