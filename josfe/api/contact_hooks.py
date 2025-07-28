# josfe/hooks22/contact_hooks.py

import frappe

def refresh_html(doc, method):
    # Go through all links and refresh contact_html in linked docs
    for link in doc.links or []:
        if link.link_doctype in ["Customer", "Supplier"]:
            try:
                target = frappe.get_doc(link.link_doctype, link.link_name)
                if hasattr(target, "update_contact"):
                    target.update_contact()
                    target.save(ignore_permissions=True)
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"❌ Failed to update contact_html for {link.link_doctype} {link.link_name}: {e}")
