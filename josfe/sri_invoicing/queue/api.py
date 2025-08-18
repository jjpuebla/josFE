import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState

QUEUE_DTYPE = "SRI XML Queue"

def enqueue_for_sales_invoice(si_name: str) -> str:
    existing = frappe.db.get_value(QUEUE_DTYPE, {"sales_invoice": si_name}, "name")
    if existing:
        return existing
    si = frappe.get_doc("Sales Invoice", si_name)
    if si.docstatus != 1:
        frappe.throw(_("Sales Invoice {0} must be submitted to enqueue.").format(si.name))
    try:
        q = frappe.get_doc({
            "doctype": QUEUE_DTYPE,
            "sales_invoice": si.name,
            "company": si.company,
            "customer": getattr(si, "customer", None),
            "state": SRIQueueState.Queued.value,  # "En Cola"
        })
        q.insert(ignore_permissions=True)
        return q.name
    except DuplicateEntryError:
        return frappe.db.get_value(QUEUE_DTYPE, {"sales_invoice": si_name}, "name")

def enqueue_on_sales_invoice_submit(doc, method=None):
    try:
        enqueue_for_sales_invoice(doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), title="SRI enqueue_on_sales_invoice_submit failed")

def on_sales_invoice_cancel(doc, method=None):
    """When an SI is canceled, mark the queue as Cancelado (terminal).
    If guard disallows from the current state, force-set to Cancelado with audit note.
    """
    try:
        qname = frappe.db.get_value(QUEUE_DTYPE, {"sales_invoice": doc.name}, "name")
        if not qname:
            return  # nothing to do
        q = frappe.get_doc(QUEUE_DTYPE, qname)
        target = SRIQueueState.Canceled.value  # "Cancelado"

        # Try a legal transition first
        try:
            q.transition_to(target, reason="Sales Invoice canceled")
        except Exception:
            # If the current state doesn't allow cancel, force-set (operationally safe on cancel)
            q.db_set("state", target)
            q.db_set("last_error", "Marked Cancelado due to Sales Invoice cancel")
    except Exception:
        frappe.log_error(frappe.get_traceback(), title="SRI on_sales_invoice_cancel failed")
