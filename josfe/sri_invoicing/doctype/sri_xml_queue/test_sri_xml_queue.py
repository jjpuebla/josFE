import frappe
import pytest

from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import (
    SRIXMLQueue,
    SRIQueueState,
    ALLOWED,
)
from josfe.sri_invoicing.core.queue import api as queue_api


def _make_queue(si_name: str = "FAKE-SI") -> SRIXMLQueue:
    q = frappe.get_doc({
        "doctype": "SRI XML Queue",
        "sales_invoice": si_name,
        "company": "FAKE-COMPANY",
        "customer": "FAKE-CUSTOMER",
        "state": SRIQueueState.Queued.value,
    })
    q.flags.ignore_links = True
    q.flags.ignore_mandatory = True
    q.insert()
    return q


def test_states_enum_and_matrix():
    assert SRIQueueState.Signing in ALLOWED[SRIQueueState.Queued]
    assert SRIQueueState.Accepted not in ALLOWED[SRIQueueState.Queued]


def test_guard_blocks_illegal_transition():
    q = _make_queue()
    with pytest.raises(Exception):
        q.transition_to("Accepted")


def test_valid_transition_succeeds():
    q = _make_queue()
    q.transition_to("Signing")
    assert q.reload().state == SRIQueueState.Signing.value


def test_enqueue_is_idempotent(monkeypatch):
    q = _make_queue("FAKE-SI-123")
    existing = frappe.db.exists("SRI XML Queue", {"sales_invoice": "FAKE-SI-123"})
    assert existing == q.name

    name = queue_api.enqueue_for_sales_invoice("FAKE-SI-123")
    assert name == q.name


def test_hooks_registered():
    hooks = frappe.get_hooks("doc_events")
    merged = {}
    for d in hooks:
        merged.update(d)
    assert "Sales Invoice" in merged
    assert "on_submit" in merged["Sales Invoice"]