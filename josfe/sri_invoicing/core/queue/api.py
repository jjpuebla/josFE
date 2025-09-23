# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/queue/api.py

from __future__ import annotations
from typing import Optional
import frappe
from frappe import _
from josfe.sri_invoicing.xml.builders import build_factura_xml
from josfe.sri_invoicing.xml import service as xml_service, paths as xml_paths

from josfe.sri_invoicing.xml import builders
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState




QUEUE_DTYPE = "SRI XML Queue"

# -----------------------------
# Core queue logic
# -----------------------------

# apps/josfe/josfe/sri_invoicing/queue/api.py

@frappe.whitelist()
def build_xml_for_queue(qname: str) -> str:
    """Generate XML for a queue row and persist path in xml_file (Generado stage).
    Supports Sales Invoice (FC) and Nota Credito (NC).
    """
    q = frappe.get_doc(QUEUE_DTYPE, qname)

    try:
        ref_dt = (getattr(q, "reference_doctype", "") or "").strip()
        ref_name = getattr(q, "reference_name", None)

        # --- Centralized builder dispatch ---
        from josfe.sri_invoicing.xml import builders

        XML_BUILDERS = {
            "FC": builders.build_factura_xml,
            "Sales Invoice": builders.build_factura_xml,
            "NC": builders.build_nota_credito_xml,
            "Nota Credito FE": builders.build_nota_credito_xml,
            # 🚀 Future-ready:
            # "ND": builders.build_nota_debito_xml,
            # "Nota Debito FE": builders.build_nota_debito_xml,
            # "RT": builders.build_retencion_xml,
            # "Retencion FE": builders.build_retencion_xml,
            # "GR": builders.build_guia_remision_xml,
            # "Guia Remision FE": builders.build_guia_remision_xml,
        }

        builder = XML_BUILDERS.get(ref_dt)
        if not builder:
            # Legacy fallback for old queue rows with sales_invoice field
            if getattr(q, "sales_invoice", None):
                si = frappe.get_doc("Sales Invoice", q.sales_invoice)
                xml_string, meta = builders.build_factura_xml(si.name)
            else:
                frappe.throw(f"Unsupported or missing reference_doctype: {ref_dt}")
        else:
            if not ref_name:
                frappe.throw("Queue row missing document reference")
            xml_string, meta = builder(ref_name)

        # --- Filename and write to Generado folder ---
        estab = (meta.get("estab") or "000").zfill(3)
        pto   = (meta.get("pto_emi") or "000").zfill(3)
        sec   = (meta.get("secuencial") or "0").zfill(9)
        filename = f"{estab}-{pto}-{sec}.xml"

        file_url = xml_service._write_to_sri(
            rel_dir=xml_paths.GEN,
            filename=filename,
            data=xml_string.encode("utf-8"),
        )

        # Persist file path in queue
        q.db_set("xml_file", file_url)

        # Notify
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"name": q.name, "state": q.state},
            user=None,
            doctype=QUEUE_DTYPE,
        )

        return file_url

    except Exception as e:
        frappe.log_error(f"Error building XML for {qname}: {e}", "SRI XML Queue")
        frappe.db.set_value(QUEUE_DTYPE, q.name, "state", SRIQueueState.Error.value)
        raise



def enqueue_on_sales_invoice_submit(doc, method):
    """Hook: enqueue SI to the SRI XML Queue on submit."""
    # 🚫 If this SI is a Credit Note return, do NOT enqueue as Factura
    if getattr(doc, "is_return", 0):
        return
    enqueue_for_sales_invoice(doc.name)

def enqueue_on_sales_invoice_cancel(doc, method):
    """Hook: mark queue row as canceled if SI is canceled."""
    qname = frappe.db.exists(QUEUE_DTYPE, {"reference_doctype": "FC", "reference_name": doc.name})
    if qname:
        frappe.db.set_value(QUEUE_DTYPE, qname, "state", SRIQueueState.Cancelado.value)
        # 🔔 Notify tabs that state changed to Cancelado
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"name": qname, "state": SRIQueueState.Cancelado.value},
            user=None,
            doctype=QUEUE_DTYPE,
        )

def enqueue_on_sales_invoice_trash(doc, method):
    """Hook: delete queue row if SI is deleted."""
    qname = frappe.db.exists(QUEUE_DTYPE, {"reference_doctype": "FC", "reference_name": doc.name})
    if qname:
        frappe.delete_doc(QUEUE_DTYPE, qname, force=True)
        # 🔔 Notify tabs to refresh (we only send a hint; client just refreshes)
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"deleted": qname},
            user=None,
            doctype=QUEUE_DTYPE,
        )

# Some installs referenced this name in hooks; keep alias to be safe
on_sales_invoice_trash = enqueue_on_sales_invoice_trash

def enqueue_for_sales_invoice(si_name: str) -> str:
    si = frappe.get_doc("Sales Invoice", si_name)
    if si.docstatus != 1:
        frappe.throw(_("Sales Invoice {0} must be submitted to enqueue.").format(si.name))
    # 🚫 safety: never enqueue returns as factura
    if getattr(si, "is_return", 0):
        return si_name  # do nothing

    ec_code = si.name[0:3] if si.name and len(si.name) >= 3 else None

    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "reference_doctype": "FC",       # shorthand for Sales Invoice
        "reference_name": si.name,
        "company": si.company,
        "customer": getattr(si, "customer", None),
        "custom_jos_level3_warehouse": getattr(si, "custom_jos_level3_warehouse", None),
        "posting_date": si.posting_date,
        "state": SRIQueueState.Generado.value,
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    # 🔔 Notify once: new row exists
    frappe.publish_realtime(
        "sri_xml_queue_changed",
        {"name": q.name, "state": q.state},
        user=None,
        doctype=QUEUE_DTYPE,
    )

    try:
        build_xml_for_queue(q.name)  # publishes when XML ready
    except Exception as e:
        frappe.log_error(message=f"XML build failed for {q.name}: {e}", title="SRI XML Queue")
        frappe.db.set_value(QUEUE_DTYPE, q.name, "state", SRIQueueState.Error.value)
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"name": q.name, "state": SRIQueueState.Error.value},
            user=None,
            doctype=QUEUE_DTYPE,
        )

    return q.name

def enqueue_on_nota_credito_submit(doc, method: Optional[str] = None):
    """Doc Event: Nota Credito FE.on_submit → create/refresh queue row and generate XML."""
    if not doc or not getattr(doc, "name", None):
        return

    # 🔑 FIX: use "NC" consistently both for lookup and insert
    qname = frappe.db.get_value(
        "SRI XML Queue",
        {"reference_doctype": "NC", "reference_name": doc.name},
        "name",
    )

    if not qname:
        q = frappe.get_doc({
            "doctype": "SRI XML Queue",
            "reference_doctype": "NC",
            "reference_name": doc.name,
            "company": doc.company,
            "customer": getattr(doc, "customer", None),
            "custom_jos_level3_warehouse": getattr(doc, "custom_jos_level3_warehouse", None),
            "custom_jos_sri_emission_point_code": getattr(doc, "custom_jos_sri_emission_point_code", None),
            "posting_date": doc.posting_date,
            "state": SRIQueueState.Generado.value,
        }).insert(ignore_permissions=True)
        qname = q.name

    # build XML for this queue row
    file_url = build_xml_for_queue(qname)

    # mark as QUEUED (or keep as Generado if that’s your intended first state)
    frappe.db.set_value("SRI XML Queue", qname, "state", SRIQueueState.Generado.value)

    frappe.db.commit()


def enqueue_on_nota_credito_cancel(doc, method: Optional[str] = None):
    if not doc or not getattr(doc, "name", None):
        return
    qname = frappe.db.get_value(
        "SRI XML Queue",
        {"reference_doctype": "NC", "reference_name": doc.name},
        "name",
    )
    if qname:
        frappe.db.set_value("SRI XML Queue", qname, "state", SRIQueueState.Cancelado.value)
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"name": qname, "state": SRIQueueState.Cancelado.value},
            user=None,
            doctype=QUEUE_DTYPE,
        )
        frappe.db.commit()


def enqueue_on_nota_credito_trash(doc, method: Optional[str] = None):
    if not doc or not getattr(doc, "name", None):
        return
    qname = frappe.db.get_value(
        "SRI XML Queue",
        {"reference_doctype": "NC", "reference_name": doc.name},
        "name",
    )
    if qname:
        frappe.delete_doc("SRI XML Queue", qname, force=True)
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"deleted": qname},
            user=None,
            doctype=QUEUE_DTYPE,
        )
        frappe.db.commit()