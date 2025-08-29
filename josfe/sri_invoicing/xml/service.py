# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/service.py

import frappe
from frappe.utils import cstr, now_datetime

from josfe.sri_invoicing.xml.builders import build_sales_invoice_xml
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
        "is_private": 1,
        "attached_to_doctype": parent_dt,
        "attached_to_name": parent_name,
        "content": text.encode("utf-8"),
    })
    file_doc.insert(ignore_permissions=True)
    return file_doc


def _placeholder_sign(xml_text: str) -> str:
    """
    TODO: replace with real XAdES-BES signing that reads your encrypted PEM.
    For now we just echo the XML so the rest of the pipeline can run.
    """
    return xml_text


def _process_signing(qdoc):
    """
    When queue state is 'Firmando':
      1) Build XML from Sales Invoice
      2) Attach unsigned XML (private File) and store its URL in qdoc.xml_file
      3) Attach 'signed' XML (placeholder) and store its URL in qdoc.signed_xml_file
      4) Advance to 'Listo para Transmitir'
    Idempotent: if both URLs are already set, it skips work.
    """
    if not qdoc.sales_invoice:
        qdoc.db_set("last_error", "Falta Sales Invoice en la cola")
        return

    # If files already exist, skip generation/signing
    if (cstr(getattr(qdoc, "xml_file", "")).strip() and
        cstr(getattr(qdoc, "signed_xml_file", "")).strip()):
        return

    si = frappe.get_doc("Sales Invoice", qdoc.sales_invoice)

    # 1) Build unsigned XML (MVP)
    xml_text = build_sales_invoice_xml(si)

    # 2) Attach XML and store URL in the queue row
    xml_file = _attach_text_as_file("SRI XML Queue", qdoc.name, f"{si.name}.xml", xml_text)
    xml_url = cstr(xml_file.file_url or "")
    qdoc.db_set("xml_file", xml_url)

    # 3) Placeholder sign, attach, and store URL
    signed_text = _placeholder_sign(xml_text)
    signed_file = _attach_text_as_file("SRI XML Queue", qdoc.name, f"{si.name}.signed.xml", signed_text)
    signed_url = cstr(signed_file.file_url or "")
    qdoc.db_set("signed_xml_file", signed_url)

    # 4) Move to ReadyToTransmit
    qdoc.db_set("state", SRIQueueState.ReadyToTransmit.value)
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
