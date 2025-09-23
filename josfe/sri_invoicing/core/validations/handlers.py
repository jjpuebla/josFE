# josfe/sri_invoicing/core/validations/handlers.py
import frappe

def enforce_xml_on_submit(doc, method=None):
    """
    Ensure every submitted Sales Invoice or Credit Note FE
    has a corresponding XML Queue entry.
    - Skip return SIs (they enqueue via NC flow).
    - Match against reference_doctype + reference_name
      instead of old sales_invoice field.
    """

    # Only enforce on submitted docs
    if getattr(doc, "docstatus", 0) != 1:
        return

    # Sales Invoice (Factura)
    if doc.doctype == "Sales Invoice":
        # 🚫 Skip returns (handled as Credit Notes)
        if getattr(doc, "is_return", 0):
            return
        exists = frappe.db.exists(
            "SRI XML Queue",
            {"reference_doctype": "FC", "reference_name": doc.name},
        )
        if not exists:
            frappe.throw("❌ This Sales Invoice cannot be submitted without an XML Queue record.")

    # Credit Note (Nota Credito FE)
    elif doc.doctype == "Nota Credito FE":
        exists = frappe.db.exists(
            "SRI XML Queue",
            {"reference_doctype": "NC", "reference_name": doc.name},
        )
        if not exists:
            frappe.throw("❌ This Credit Note cannot be submitted without an XML Queue record.")
