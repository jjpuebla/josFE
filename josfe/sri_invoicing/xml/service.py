# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/service.py

import frappe
from frappe.utils import cstr, now_datetime

# ⬇️ Switch to the deterministic builder (no other imports touched)
from josfe.sri_invoicing.xml.builders import build_factura_xml
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState


def _attach_text_as_file(parent_dt: str, parent_name: str, filename: str, text: str) -> frappe.model.document.Document:
    """
    Create a PRIVATE File attached to the given parent and return the File doc.
    We rely on file_url (e.g., /private/files/xxx.xml) because your current
    validators/readers expect URL paths.
    """
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "content": text or "",
        "is_private": 1,
        "attached_to_doctype": parent_dt,
        "attached_to_name": parent_name,
    })
    file_doc.insert(ignore_permissions=True)
    return file_doc


def _process_signing(qdoc):
    """
    Rebuild (if missing) and sign the XML, then advance the queue state.
    NOTE: We only build XML here if xml_file is empty to avoid duplicates.
    """
    # 1) Ensure we have the SI
    if not qdoc.sales_invoice:
        frappe.throw("La cola no tiene Sales Invoice asociado.")
    si = frappe.get_doc("Sales Invoice", qdoc.sales_invoice)

    # 2) Generate & attach XML ONLY if missing (idempotent behavior)
    if not cstr(qdoc.xml_file):
        # Deterministic builder returns (xml_string, meta)
        xml_str, meta = build_factura_xml(si.name)

        estab = (meta.get("estab") or str(getattr(si, "sri_establishment_code", "000"))).zfill(3)
        pto   = (meta.get("pto_emi") or str(getattr(si, "sri_emission_point_code", "000"))).zfill(3)
        sec   = (meta.get("secuencial") or str(getattr(si, "sri_sequential_assigned", "0"))).zfill(9)
        filename = f"FACTURA-{estab}-{pto}-{sec}.xml"

        f = _attach_text_as_file("Sales Invoice", si.name, filename, xml_str)
        qdoc.db_set("xml_file", f.file_url)

    # 3) Placeholder signing step (integrate signer when ready)
    #    For now, do not duplicate attachments; when signer is implemented,
    #    replace this with signed content and set 'signed_xml_file'.
    if not cstr(qdoc.signed_xml_file):
        # Keep it empty until signer writes the signed file, or copy the same XML if your
        # downstream expects a value to progress. Here we leave it empty intentionally.
        pass

    # 4) Advance state to the next step (prefer enum, else literal)
    next_state = getattr(SRIQueueState, "ReadyToTransmit", None)
    if next_state:
        qdoc.db_set("state", next_state.value)  # Usually "Listo para Transmitir"
    else:
        qdoc.db_set("state", "Listo para Transmitir")

    # 5) Audit fields (keep your existing fields intact)
    qdoc.db_set("last_error", "")
    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)


def on_queue_update(doc, method=None):
    """
    Hook: called whenever SRI XML Queue is updated.
    If state == 'Firmando', generate & (placeholder) sign the XML, then advance to 'Listo para Transmitir'.
    """
    try:
        if cstr(doc.state) == SRIQueueState.Signing.value:
            _process_signing(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), title="SRI XML Queue on_update failure")
