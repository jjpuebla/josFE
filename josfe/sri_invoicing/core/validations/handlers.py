# josfe/sri_invoicing/validations/handlers.py
import frappe

def enforce_xml_on_submit(doc, method):
    """
    Ensure every submitted Sales Invoice has an XML Queue entry.
    This prevents invoices from being submitted without XML.
    """
    if doc.docstatus == 1:
        exists = frappe.db.exists("SRI XML Queue", {"sales_invoice": doc.name})
        if not exists:
            frappe.throw("❌ This Sales Invoice cannot be submitted without an XML Queue record.")
