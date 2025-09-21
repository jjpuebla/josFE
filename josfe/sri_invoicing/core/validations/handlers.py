# josfe/sri_invoicing/validations/handlers.py
import frappe

def enforce_xml_on_submit(doc, method=None):
    """
    Ensure every submitted *normal* Sales Invoice has an XML Queue entry.
    Credit Note returns (is_return=1) are excluded on purpose.
    """
    # ✅ Skip Credit Note return invoices entirely
    if getattr(doc, "is_return", 0):
        return

    # Only enforce on submitted documents
    if getattr(doc, "docstatus", 0) != 1:
        return

    # Your queue schema uses a 'sales_invoice' link field
    exists = frappe.db.exists("SRI XML Queue", {"sales_invoice": doc.name})
    if not exists:
        frappe.throw("❌ This Sales Invoice cannot be submitted without an XML Queue record.")
