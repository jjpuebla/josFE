# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/queue/api.py

from __future__ import annotations
import os
import frappe
from frappe import _
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.xml.builders import build_factura_xml

QUEUE_DTYPE = "SRI XML Queue"

# -----------------------------
# Helpers for file handling
# -----------------------------

def _ensure_stage_dir(stage_folder: str) -> str:
    """Ensure /private/files/<stage_folder> exists; return absolute path."""
    base = frappe.get_site_path("private", "files")
    full = os.path.join(base, stage_folder)
    os.makedirs(full, exist_ok=True)
    return full

def _write_xml_to_stage(filename: str, xml: str, stage_folder: str) -> str:
    """
    Write XML as a real file under /private/files/<stage_folder>/<filename>.
    Return file_url (/private/files/<stage_folder>/<filename>).
    """
    full_dir = _ensure_stage_dir(stage_folder)
    full_path = os.path.join(full_dir, filename)
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(xml)
    return f"/private/files/{stage_folder}/{filename}"

# -----------------------------
# Core queue logic
# -----------------------------

@frappe.whitelist()
def build_xml_for_queue(qname: str) -> str:
    """
    Build raw XML for the queue row, save it as a private File in 'Generado',
    attach to the queue, set state to 'Generado', and return file_url.
    (Does not auto-advance to 'Firmado' — user action will.)
    """
    q = frappe.get_doc(QUEUE_DTYPE, qname)
    if not q.sales_invoice:
        frappe.throw(_("La cola no tiene Sales Invoice asociado."))

    try:
        si = frappe.get_doc("Sales Invoice", q.sales_invoice)

        # Deterministic builder
        xml, meta = build_factura_xml(si.name)

        estab = (meta.get("estab") or "000").zfill(3)
        pto   = (meta.get("pto_emi") or "000").zfill(3)
        sec   = (meta.get("secuencial") or "0").zfill(9)
        filename = f"{estab}-{pto}-{sec}.xml"

        # Save under "Generado"
        file_url = _write_xml_to_stage(filename, xml, "Generado")

        # Keep exactly ONE attachment on the queue row: delete previous if any
        for fname in frappe.get_all(
            "File",
            filters={"attached_to_doctype": QUEUE_DTYPE, "attached_to_name": q.name},
            pluck="name",
        ):
            frappe.delete_doc("File", fname, force=True, ignore_permissions=True)

        # Create File doc pointing to disk file (no DB content)
        frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "file_url": file_url,
            "is_private": 1,
            "attached_to_doctype": QUEUE_DTYPE,
            "attached_to_name": q.name,
        }).insert(ignore_permissions=True)

        q.db_set("xml_file", file_url)
        q.db_set("state", SRIQueueState.Generado.value)
        q.db_set("last_error", "")

        return file_url

    except Exception as e:
        q.db_set("last_error", frappe.get_traceback())
        frappe.throw(_("Error al construir XML: {0}").format(e))

def enqueue_on_sales_invoice_submit(doc, method):
    """Hook: enqueue SI to the SRI XML Queue on submit."""
    enqueue_for_sales_invoice(doc.name)

def enqueue_on_sales_invoice_cancel(doc, method):
    """Hook: mark queue row as canceled if SI is canceled."""
    qname = frappe.db.exists(QUEUE_DTYPE, {"sales_invoice": doc.name})
    if qname:
        frappe.db.set_value(QUEUE_DTYPE, qname, "state", SRIQueueState.Cancelado.value)

def enqueue_on_sales_invoice_trash(doc, method):
    """Hook: delete queue row if SI is deleted."""
    qname = frappe.db.exists(QUEUE_DTYPE, {"sales_invoice": doc.name})
    if qname:
        frappe.delete_doc(QUEUE_DTYPE, qname, force=True)

# Some installs referenced this name in hooks; keep alias to be safe
on_sales_invoice_trash = enqueue_on_sales_invoice_trash

def enqueue_for_sales_invoice(si_name: str) -> str:
    """Insert the queue row for a Sales Invoice and build its XML (state = Generado)."""
    si = frappe.get_doc("Sales Invoice", si_name)
    if si.docstatus != 1:
        frappe.throw(_("Sales Invoice {0} must be submitted to enqueue.").format(si.name))

    ec_code = si.name[0:3] if si.name and len(si.name) >= 3 else None

    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "sales_invoice": si.name,
        "company": si.company,
        "customer": getattr(si, "customer", None),
        "custom_jos_level3_warehouse": getattr(si, "custom_jos_level3_warehouse", None),
        "custom_jos_ec_code": ec_code,
        "posting_date": si.posting_date,
        "state": SRIQueueState.Generado.value,  # initial
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    try:
        build_xml_for_queue(q.name)
    except Exception as e:
        frappe.log_error(message=f"XML build failed for {q.name}: {e}", title="SRI XML Queue")
        frappe.db.set_value(QUEUE_DTYPE, q.name, "state", SRIQueueState.Error.value)

    return q.name
