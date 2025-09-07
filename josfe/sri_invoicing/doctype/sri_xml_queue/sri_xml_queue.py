# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.py

import os
import frappe
from enum import Enum
from typing import Dict, Set, Optional
from frappe.model.document import Document

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
                pass  # don't hard-fail in tests
        # ✅ ensure new file starts under SRI/GENERADOS
        if self.xml_file and not self.xml_file.startswith("/private/files/SRI/GENERADOS/"):
            from josfe.sri_invoicing.xml.service import _move_xml_file
            try:
                new_url = _move_xml_file(self.xml_file, "Generado")
                if new_url:
                    self.xml_file = new_url
            except Exception:
                frappe.log_error(frappe.get_traceback(), "SRI move GENERADO before_insert")


    def validate(self):
        _coerce_state(self.state)

    def on_update(self):
        self.last_transition_by = frappe.session.user
        self.last_transition_at = frappe.utils.now_datetime()

    # --- State machine API ---
    def transition_to(self, to_state: str, reason: Optional[str] = None):
        from_state = _coerce_state(self.state)
        to_state_e = _coerce_state(to_state)

        # Reenviar: do NOT call Recepción again; repoll Autorización instead
        if from_state == SRIQueueState.Enviado and to_state_e == SRIQueueState.Enviado:
            try:
                from josfe.sri_invoicing.xml import service as _svc
                # read current xml and extract claveAcceso
                site_files = frappe.get_site_path("private", "files")
                rel_old = (self.xml_file or "").replace("/private/files/", "", 1).lstrip("/")
                with open(os.path.join(site_files, rel_old), "rb") as f:
                    xml_bytes = f.read()
                import re as _re
                m = _re.search(rb"<\s*claveAcceso\s*>\s*([0-9]+)\s*<\s*/\s*claveAcceso\s*>", xml_bytes or b"")
                clave = (m.group(1).decode().strip() if m else "")
                if not clave:
                    frappe.msgprint("⚠ No se pudo extraer claveAcceso para reintentar Autorización.")
                    return
                from josfe.sri_invoicing.transmission import poller2
                poller2.poll_autorizacion_job(queue_name=self.name, clave=clave, ambiente="Pruebas", attempt=0)
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
