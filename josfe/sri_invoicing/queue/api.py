# -*- coding: utf-8 -*-
from __future__ import annotations
import frappe
from frappe import _
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.xml.builders import build_factura_xml

QUEUE_DTYPE = "SRI XML Queue"

@frappe.whitelist()
def build_xml_for_queue(qname: str) -> str:
    """Build raw XML for the queue row, save it as a private File,
    set xml_file link, change state to 'Firmando', and return file_url.
    """
    q = frappe.get_doc("SRI XML Queue", qname)
    if not q.sales_invoice:
        frappe.throw(_("La cola no tiene Sales Invoice asociado."))

    try:
        si = frappe.get_doc("Sales Invoice", q.sales_invoice)

        # Always use the deterministic builder
        xml, meta = build_factura_xml(si.name)

        # Deterministic filename
        estab = meta.get("estab") or str(getattr(si, "sri_establishment_code", "000")).zfill(3)
        pto   = meta.get("pto_emi") or str(getattr(si, "sri_emission_point_code", "000")).zfill(3)
        sec   = meta.get("secuencial") or str(getattr(si, "sri_sequential_assigned", "0")).zfill(9)
        filename = f"FACTURA-{estab}-{pto}-{sec}.xml"

        # Create private File and attach to Sales Invoice
        f = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": xml,
            "is_private": 1,
            "attached_to_doctype": "Sales Invoice",
            "attached_to_name": si.name,
        }).insert(ignore_permissions=True)

        # Update queue row
        q.db_set("xml_file", f.file_url)
        q.db_set("state", SRIQueueState.Signing.value)  # "Firmando"
        q.db_set("last_error", "")

        return f.file_url

    except Exception as e:
        q.db_set("last_error", frappe.get_traceback())
        frappe.throw(_("Error al construir XML: {0}").format(e))


def enqueue_on_sales_invoice_submit(doc, method):
    """Hook: enqueue SI to the SRI XML Queue on submit."""
    enqueue_for_sales_invoice(doc.name)


def enqueue_on_sales_invoice_cancel(doc, method):
    """Hook: mark queue row as canceled if SI is canceled."""
    qname = frappe.db.exists("SRI XML Queue", {"sales_invoice": doc.name})
    if qname:
        frappe.db.set_value("SRI XML Queue", qname, "state", SRIQueueState.Cancelled.value)


def enqueue_on_sales_invoice_trash(doc, method):
    """Hook: delete queue row if SI is deleted."""
    qname = frappe.db.exists("SRI XML Queue", {"sales_invoice": doc.name})
    if qname:
        frappe.delete_doc("SRI XML Queue", qname, force=True)

def enqueue_for_sales_invoice(si_name: str) -> str:
    si = frappe.get_doc("Sales Invoice", si_name)
    if si.docstatus != 1:
        frappe.throw(_("Sales Invoice {0} must be submitted to enqueue.").format(si.name))

    ec_code = si.name[0:3] if si.name and len(si.name) >= 3 else None

    # Always insert the queue first
    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "sales_invoice": si.name,
        "company": si.company,
        "customer": getattr(si, "customer", None),
        "custom_jos_level3_warehouse": getattr(si, "custom_jos_level3_warehouse", None),
        "custom_jos_ec_code": ec_code,
        "posting_date": si.posting_date,
        "state": SRIQueueState.Queued.value,
    })
    q.insert(ignore_permissions=True)
    frappe.db.commit()

    try:
        build_xml_for_queue(q.name)
    except Exception as e:
        frappe.log_error(f"XML build failed for {q.name}: {e}", "SRI XML Queue")
        frappe.db.set_value(QUEUE_DTYPE, q.name, "state", SRIQueueState.Failed.value)

    return q.name


