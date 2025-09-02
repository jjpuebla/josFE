# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.py

import frappe
from frappe.model.document import Document
from enum import Enum
from typing import Dict, Set, Optional

class SRIQueueState(str, Enum):
    Generado   = "Generado"     # XML built and stored
    Firmado    = "Firmado"      # XML digitally signed
    Enviado    = "Enviado"      # Sent to SRI, awaiting response
    Autorizado = "Autorizado"   # Accepted by SRI
    Devuelto   = "Devuelto"     # Returned/rejected by SRI
    Cancelado  = "Cancelado"    # Manually canceled
    Error      = "Error"        # Any failure (signing/transmission)

    @classmethod
    def terminals(cls) -> Set["SRIQueueState"]:
        return {cls.Autorizado, cls.Cancelado}

# Allowed transitions for the minimal M1 machine
ALLOWED: Dict[SRIQueueState, Set[SRIQueueState]] = {
    SRIQueueState.Generado: {SRIQueueState.Firmado, SRIQueueState.Cancelado, SRIQueueState.Error},
    SRIQueueState.Firmado: {SRIQueueState.Enviado, SRIQueueState.Cancelado, SRIQueueState.Error},
    SRIQueueState.Enviado: {SRIQueueState.Autorizado, SRIQueueState.Devuelto, SRIQueueState.Error},
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
    """DocType model for the SRI XML Queue state machine.
    States, allowed transitions, guards, and audit fields.
    """

    def before_insert(self):
        # Populate company & customer from Sales Invoice when available
        if getattr(self, "sales_invoice", None):
            try:
                si = frappe.get_doc("Sales Invoice", self.sales_invoice)
                self.company = self.company or getattr(si, "company", None)
                self.customer = self.customer or getattr(si, "customer", None)
            except Exception:
                # In tests we sometimes insert with ignore_links; don't hard-fail
                pass

    def validate(self):
        # Ensure current state is valid
        _coerce_state(self.state)

    def on_update(self):
        # Keep audit fields up to date when a change occurs
        self.last_transition_by = frappe.session.user
        self.last_transition_at = frappe.utils.now_datetime()

    # --- State machine API ---
    def transition_to(self, to_state: str, reason: Optional[str] = None):
        from_state = _coerce_state(self.state)
        to_state_e = _coerce_state(to_state)

        if to_state_e not in ALLOWED[from_state]:
            frappe.throw(
                f"Illegal transition {from_state.value} → {to_state_e.value}",
                title="Transition Not Allowed",
            )

        if reason:
            self.last_error = reason

        self.state = to_state_e.value
        self.save(ignore_permissions=True)

# Convenience/guarded APIs
@frappe.whitelist()
def transition(name: str, to_state: str, reason: Optional[str] = None):
    doc = frappe.get_doc("SRI XML Queue", name)
    doc.transition_to(to_state, reason)
    return doc.name

@frappe.whitelist()
def get_allowed_transitions(name: str):
    """Return allowed transitions for a given XML Queue row"""
    doc = frappe.get_doc("SRI XML Queue", name)
    state = _coerce_state(doc.state)
    return [s.value for s in ALLOWED.get(state, [])]

# at the top of sri_xml_queue.py
import os

@frappe.whitelist()
def get_xml_preview(name: str):
    """Return XML content from the attached file on disk for preview dialog."""
    doc = frappe.get_doc("SRI XML Queue", name)
    if not doc.xml_file:
        return ""

    try:
        file_doc = frappe.get_doc("File", {
            "attached_to_doctype": "SRI XML Queue",
            "attached_to_name": name
        })
        if not file_doc.file_url:
            return ""

        base = frappe.get_site_path("private", "files")
        rel = file_doc.file_url.replace("/private/files/", "", 1)
        path = os.path.join(base, rel)

        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="get_xml_preview failed")
        return ""
