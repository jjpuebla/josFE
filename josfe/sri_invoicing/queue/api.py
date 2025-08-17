import frappe
from typing import Optional

QUEUE_DTYPE = "SRI XML Queue"


def enqueue_for_sales_invoice(si_name: str) -> str:
    existing = frappe.db.exists(QUEUE_DTYPE, {"sales_invoice": si_name})
    if existing:
        return existing

    si = frappe.get_doc("Sales Invoice", si_name)

    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "sales_invoice": si.name,
        "company": si.company,
        "customer": getattr(si, "customer", None),
        "state": "Queued",
    })
    q.insert(ignore_permissions=True)
    return q.name


def enqueue_on_sales_invoice_submit(doc, method=None):
    try:
        enqueue_for_sales_invoice(doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), title="SRI enqueue_on_sales_invoice_submit failed")

