import frappe
from typing import Optional

QUEUE_DTYPE = "SRI XML Queue"


def enqueue_for_sales_invoice(si_name: str) -> str:
    """Create or return an existing queue item for a Sales Invoice.
    Idempotent; update-safe.
    """
    # Return existing
    existing = frappe.db.exists(QUEUE_DTYPE, {"sales_invoice": si_name})
    if existing:
        return existing

    # Pull essentials from SI
    si = frappe.get_doc("Sales Invoice", si_name)

    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "sales_invoice": si.name,
        "company": si.company,
        "customer": getattr(si, "customer", None),
        "state": "Queued",
    })
    # Let doctype hooks handle audit fields
    q.insert(ignore_permissions=True)
    return q.name


def enqueue_on_sales_invoice_submit(doc, method=None):
    """Doc Event hook for Sales Invoice.on_submit"""
    try:
        enqueue_for_sales_invoice(doc.name)
    except Exception:
        # Never block accounting flow; log and move on
        frappe.log_error(frappe.get_traceback(), title="SRI enqueue_on_sales_invoice_submit failed")

