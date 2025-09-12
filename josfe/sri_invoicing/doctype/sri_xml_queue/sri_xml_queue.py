# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.py

import os
import frappe
from enum import Enum
from typing import Dict, Set, Optional
from frappe.model.document import Document
from josfe.sri_invoicing.xml import paths as xml_paths

class SRIQueueState(str, Enum):
    Generado   = "Generado"     # XML built and stored
    Firmado    = "Firmado"      # XML digitally signed
    Enviado    = "Enviado"      # Sent to SRI, awaiting response (PPR)
    Autorizado = "Autorizado"   # Accepted by SRI
    Devuelto   = "Devuelto"     # Returned/rejected by SRI (Recepción or Autorización)
    Cancelado  = "Cancelado"    # Manually canceled
    Error      = "Error"        # Any failure (signing/transmission)

    @classmethod
    def terminals(cls) -> Set["SRIQueueState"]:
        return {cls.Autorizado, cls.Cancelado}

# Allowed transitions (backend logic remains intact)
ALLOWED: Dict[SRIQueueState, Set[SRIQueueState]] = {
    SRIQueueState.Generado: {SRIQueueState.Firmado, SRIQueueState.Cancelado, SRIQueueState.Error},
    SRIQueueState.Firmado:  {SRIQueueState.Enviado, SRIQueueState.Cancelado, SRIQueueState.Error},
    SRIQueueState.Enviado:  {SRIQueueState.Autorizado, SRIQueueState.Devuelto, SRIQueueState.Error},
    SRIQueueState.Autorizado: set(),  # final
    SRIQueueState.Devuelto: {SRIQueueState.Generado, SRIQueueState.Cancelado},  # retry or cancel
    SRIQueueState.Cancelado: set(),   # final
    SRIQueueState.Error: {SRIQueueState.Generado, SRIQueueState.Cancelado},     # retry or cancel
}

def _coerce_state(val: str) -> SRIQueueState:
    try:
        return SRIQueueState(val)
    except Exception:
        frappe.throw(f"Invalid state: {frappe.as_json(val)}")

class SRIXMLQueue(Document):
    """DocType model for the SRI XML Queue state machine."""

    def before_insert(self):
        # Populate company & customer from Sales Invoice when available
        if getattr(self, "sales_invoice", None):
            try:
                si = frappe.get_doc("Sales Invoice", self.sales_invoice)
                self.company = self.company or getattr(si, "company", None)
                self.customer = self.customer or getattr(si, "customer", None)
            except Exception:
                # don't hard-fail in tests
                pass

        # ✅ ensure new file starts under canonical SRI/Generados
        prefix = f"/private/files/{xml_paths.ROOT_FOLDER_NAME}/{xml_paths.GEN}/"
        if self.xml_file and not (self.xml_file or "").startswith(prefix):
            from josfe.sri_invoicing.xml.service import _move_xml_file
            try:
                new_url = _move_xml_file(self.xml_file, "Generado")
                if new_url:
                    self.xml_file = new_url
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    "SRI move GENERADO before_insert"
                )

    def validate(self):
        _coerce_state(self.state)

    def on_update(self):
        self.last_transition_by = frappe.session.user
        self.last_transition_at = frappe.utils.now_datetime()

    # --- State machine API ---
    def transition_to(self, to_state: str, reason: Optional[str] = None):
        from_state = _coerce_state(self.state)
        to_state_e = _coerce_state(to_state)

        # Reenviar: call the same unified sender as Enviar (no alternate path)
        if from_state == SRIQueueState.Enviado and to_state_e == SRIQueueState.Enviado:
            try:
                from josfe.sri_invoicing.xml.service import send_to_sri
                send_to_sri(self.name, is_retry=1)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "SRI reenviar error")
            return

        if to_state_e not in ALLOWED[from_state]:
            frappe.throw(
                f"Illegal transition {from_state.value} → {to_state_e.value}",
                title="Transition Not Allowed",
            )

        if reason:
            self.last_error = reason

        self.state = to_state_e.value
        self.save(ignore_permissions=True)

# --- Whitelisted APIs ---

@frappe.whitelist()
def transition(name: str, to_state: str):
    """Perform a state transition (or 'Reenviar') and notify clients."""
    doc: SRIXMLQueue = frappe.get_doc("SRI XML Queue", name)
    doc.transition_to(to_state)

    try:
        frappe.publish_realtime(
            "sri_xml_queue_changed",
            {"name": doc.name, "state": doc.state},
            user=None,
            doctype="SRI XML Queue",
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "realtime publish failed")

    return {"ok": True, "name": doc.name, "state": doc.state}

@frappe.whitelist()
def get_allowed_transitions(name: str):
    """Expose simplified transitions for the List UI buttons only."""
    doc = frappe.get_doc("SRI XML Queue", name)
    state = (doc.state or "").strip()
    if state == "Generado":
        return ["Firmado"]   # UI label = "Firmar"
    if state == "Firmado":
        return ["Enviado"]   # UI label = "Enviar"
    if state == "Enviado":
        return ["Enviado"]   # UI label = "Reenviar"
    return []

@frappe.whitelist()
def get_xml_preview(name: str):
    """Return XML content from disk for preview dialog."""
    doc = frappe.get_doc("SRI XML Queue", name)
    if not doc.xml_file:
        return ""
    try:
        base = frappe.get_site_path("private", "files")
        rel = doc.xml_file.replace("/private/files/", "", 1)
        path = os.path.join(base, rel)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_xml_preview error")
        return ""

# @frappe.whitelist()
# def get_pdf_url(name: str) -> str:
#     """Return the PDF /private/files URL if it exists; build it if missing."""
#     import os
#     from frappe.utils import getdate
#     from josfe.sri_invoicing.xml import paths as xml_paths
#     from josfe.sri_invoicing.pdf_emailing.pdf_builder import build_invoice_pdf

#     doc = frappe.get_doc("SRI XML Queue", name)

#     # Resolve linked Sales Invoice exactly like pdf_builder does
#     inv = None
#     if doc.get("sales_invoice"):
#         inv = frappe.get_doc("Sales Invoice", doc.sales_invoice)
#     elif doc.get("reference_doctype") == "Sales Invoice" and doc.get("reference_name"):
#         inv = frappe.get_doc("Sales Invoice", doc.reference_name)
#     else:
#         return ""

#     # Build path: use invoice.posting_date and invoice.name
#     d = getdate(inv.posting_date)
#     rel_dir = f"RIDE/{d.month:02d}-{d.year}"
#     fname = f"{inv.name}.pdf"
#     abs_path = xml_paths.abs_path(rel_dir, fname)
#     url = xml_paths.to_file_url(rel_dir, fname)

#     # If missing, build the PDF now
#     if not os.path.exists(abs_path):
#         try:
#             url = build_invoice_pdf(doc)
#         except Exception:
#             frappe.log_error(frappe.get_traceback(), "get_pdf_url build failed")
#             return ""

#     return url

@frappe.whitelist()
def download_pdf(name: str) -> dict:
    """
    Ensure the PDF exists, then return it as base64 along with the correct filename.
    This avoids hitting /private/files from the browser (auth issues).
    """
    import os, base64
    from josfe.sri_invoicing.pdf_emailing.pdf_builder import build_invoice_pdf

    qdoc = frappe.get_doc("SRI XML Queue", name)

    # Build (or rebuild) to guarantee the file exists; returns /private/files/... URL
    pdf_url = build_invoice_pdf(qdoc)

    # Convert URL -> absolute path
    abs_path = frappe.get_site_path("private", "files", pdf_url.replace("/private/files/", ""))
    if not os.path.exists(abs_path):
        frappe.throw(f"PDF file not found: {abs_path}")

    with open(abs_path, "rb") as f:
        data_b64 = base64.b64encode(f.read()).decode("utf-8")

    return {
        "data": data_b64,
        "filename": os.path.basename(abs_path),  # e.g. 002-002-000000266.pdf
    }