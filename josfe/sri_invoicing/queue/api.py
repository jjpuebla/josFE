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
        # Defensive: ensure name is long enough
        ec_code = None
        if si.name and len(si.name) >= 3:
            ec_code = si.name[0:3]  # first 3 characters
        else:
            frappe.throw(f"Invalid Sales Invoice name format: {si.name}")

        q = frappe.get_doc({
            "doctype": QUEUE_DTYPE,
            "sales_invoice": si.name,
            "company": si.company,
            "customer": getattr(si, "customer", None),
            "custom_jos_level3_warehouse": getattr(si, "custom_jos_level3_warehouse", None),
            "custom_jos_ec_code": ec_code,   # 👈 add hidden field in SRI XML Queue
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

def on_sales_invoice_trash(doc, method=None):
    """When a Sales Invoice is deleted, also delete linked XML Queue."""
    try:
        xmls = frappe.get_all("SRI XML Queue", {"sales_invoice": doc.name})
        for x in xmls:
            frappe.delete_doc("SRI XML Queue", x.name, force=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), title="SRI on_sales_invoice_trash failed")