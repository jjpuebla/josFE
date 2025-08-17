import frappe
from frappe.model.document import Document
from enum import Enum
from typing import Dict, Set, Optional


class SRIQueueState(str, Enum):
    Queued = "Queued"
    Signing = "Signing"
    ReadyToTransmit = "ReadyToTransmit"
    Transmitted = "Transmitted"
    Accepted = "Accepted"
    Rejected = "Rejected"
    Failed = "Failed"
    Canceled = "Canceled"

    @classmethod
    def terminals(cls) -> Set["SRIQueueState"]:
        return {cls.Accepted, cls.Canceled}


# Allowed transitions for the minimal M1 machine
ALLOWED: Dict[SRIQueueState, Set[SRIQueueState]] = {
    SRIQueueState.Queued: {SRIQueueState.Signing, SRIQueueState.Canceled},
    SRIQueueState.Signing: {SRIQueueState.ReadyToTransmit, SRIQueueState.Failed},
    SRIQueueState.ReadyToTransmit: {SRIQueueState.Transmitted, SRIQueueState.Failed, SRIQueueState.Canceled},
    SRIQueueState.Transmitted: {SRIQueueState.Accepted, SRIQueueState.Rejected, SRIQueueState.Failed},
    SRIQueueState.Rejected: {SRIQueueState.Queued, SRIQueueState.Canceled},
    SRIQueueState.Failed: {SRIQueueState.Queued, SRIQueueState.Canceled},
    SRIQueueState.Accepted: set(),
    SRIQueueState.Canceled: set(),
}


def _coerce_state(val: str) -> SRIQueueState:
    try:
        return SRIQueueState(val)
    except Exception:
        frappe.throw(f"Invalid state: {frappe.as_json(val)}")


class SRIXMLQueue(Document):
    """DocType model for the SRI XML Queue state machine.
    Minimal M1: just states, guards, and audit fields.
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
        # keep audit fields up to date when a change occurs
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
