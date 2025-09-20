# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/queue/api.py

from __future__ import annotations
import frappe
from frappe import _
from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.xml.builders import build_factura_xml
from josfe.sri_invoicing.xml import service as xml_service, paths as xml_paths

from josfe.sri_invoicing.xml import builders
from josfe.sri_invoicing.core.queue.states import SRIQueueState




QUEUE_DTYPE = "SRI XML Queue"

# -----------------------------
# Core queue logic
# -----------------------------

@frappe.whitelist()
def build_xml_for_queue(qname: str) -> str:
    """Generate XML for a queue row and persist path in xml_file (Generado stage).
    Supports both Sales Invoice and Nota Credito FE.
    """
    q = frappe.get_doc(QUEUE_DTYPE, qname)

    try:
        if getattr(q, "reference_doctype", None) == "Nota Credito FE":
            from josfe.sri_invoicing.xml.builders import build_nota_credito_xml
            xml_string, meta = build_nota_credito_xml(q.reference_name)

            # 🔑 Allocate + bump Nota de Crédito counter
            from josfe.sri_invoicing.numbering.state import next_sequential
            seq = next_sequential(
                company=q.company,
                pto_emi=meta.get("pto_emi"),
                doc_type="Nota de Crédito"
            )
            meta["secuencial"] = f"{seq:09d}"

        elif getattr(q, "sales_invoice", None):
            from josfe.sri_invoicing.xml.builders import build_factura_xml
            si = frappe.get_doc("Sales Invoice", q.sales_invoice)
            xml_string, meta = build_factura_xml(si.name)

            # 🔑 Allocate + bump Factura counter
            from josfe.sri_invoicing.numbering.state import next_sequential
            seq = next_sequential(
                company=q.company,
                pto_emi=meta.get("pto_emi"),
                doc_type="Factura"
            )
            meta["secuencial"] = f"{seq:09d}"

        else:
            frappe.throw("Queue row missing document reference")

        # --- Inject real secuencial into XML ---
        from lxml import etree
        root = etree.fromstring(xml_string.encode("utf-8"))
        sec_node = root.find(".//secuencial")
        if sec_node is not None:
            sec_node.text = meta["secuencial"]
        xml_string = etree.tostring(
            root, pretty_print=True, encoding="utf-8", xml_declaration=True
        ).decode("utf-8")

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

        q.db_set("xml_file", file_url)

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
    enqueue_for_sales_invoice(doc.name)

def enqueue_on_sales_invoice_cancel(doc, method):
    """Hook: mark queue row as canceled if SI is canceled."""
    qname = frappe.db.exists(QUEUE_DTYPE, {"sales_invoice": doc.name})
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
    qname = frappe.db.exists(QUEUE_DTYPE, {"sales_invoice": doc.name})
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

def enqueue_on_nota_credito_submit(doc, method):
    enqueue_for_nota_credito(doc.name)

def enqueue_on_nota_credito_cancel(doc, method):
    qname = frappe.db.exists(QUEUE_DTYPE, {"reference_doctype": "Nota Credito FE", "reference_name": doc.name})
    if qname:
        frappe.db.set_value(QUEUE_DTYPE, qname, "state", SRIQueueState.Cancelado.value)

def enqueue_on_nota_credito_trash(doc, method):
    qname = frappe.db.exists(QUEUE_DTYPE, {"reference_doctype": "Nota Credito FE", "reference_name": doc.name})
    if qname:
        frappe.delete_doc(QUEUE_DTYPE, qname, force=True)

def enqueue_for_nota_credito(nc_name: str) -> str:
    nc = frappe.get_doc("Nota Credito FE", nc_name)
    if nc.docstatus != 1:
        frappe.throw(_("Nota Credito FE {0} must be submitted").format(nc.name))

    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "reference_doctype": "Nota Credito FE",
        "reference_name": nc.name,
        "company": nc.company,
        "customer": nc.customer,
        "posting_date": nc.posting_date,
        "state": SRIQueueState.Generado.value,
    }).insert(ignore_permissions=True)

    frappe.db.commit()
    frappe.publish_realtime("sri_xml_queue_changed", {"name": q.name, "state": q.state}, doctype=QUEUE_DTYPE)

    try:
        build_xml_for_queue(q.name)  # this will branch to credit note builder
    except Exception as e:
        frappe.log_error(f"XML build failed for NC {q.name}: {e}", "SRI XML Queue")
        frappe.db.set_value(QUEUE_DTYPE, q.name, "state", SRIQueueState.Error.value)

    return q.name

# -----------------------------
# Nota Credito FE enqueue
# -----------------------------

def enqueue_on_nota_credito_submit(doc, method):
    enqueue_for_nota_credito(doc.name)


def enqueue_on_nota_credito_cancel(doc, method):
    qname = frappe.db.exists(
        QUEUE_DTYPE,
        {"reference_doctype": "Nota Credito FE", "reference_name": doc.name}
    )
    if qname:
        frappe.db.set_value(QUEUE_DTYPE, qname, "state", SRIQueueState.Cancelado.value)


def enqueue_on_nota_credito_trash(doc, method):
    qname = frappe.db.exists(
        QUEUE_DTYPE,
        {"reference_doctype": "Nota Credito FE", "reference_name": doc.name}
    )
    if qname:
        frappe.delete_doc(QUEUE_DTYPE, qname, force=True)


def enqueue_for_nota_credito(nc_name: str) -> str:
    """Insert queue row for Nota Credito FE and trigger XML build."""
    nc = frappe.get_doc("Nota Credito FE", nc_name)
    if nc.docstatus != 1:
        frappe.throw(_("Nota Credito FE {0} must be submitted").format(nc.name))

    q = frappe.get_doc({
        "doctype": QUEUE_DTYPE,
        "reference_doctype": "Nota Credito FE",
        "reference_name": nc.name,
        "company": nc.company,
        "customer": nc.customer,
        "posting_date": nc.posting_date,
        "state": SRIQueueState.Generado.value,
    }).insert(ignore_permissions=True)

    frappe.db.commit()

    frappe.publish_realtime(
        "sri_xml_queue_changed",
        {"name": q.name, "state": q.state},
        doctype=QUEUE_DTYPE,
    )

    try:
        from josfe.sri_invoicing.core.queue.api import build_xml_for_queue
        build_xml_for_queue(q.name)
    except Exception as e:
        frappe.log_error(f"XML build failed for Nota Credito FE {q.name}: {e}", "SRI XML Queue")
        frappe.db.set_value(QUEUE_DTYPE, q.name, "state", SRIQueueState.Error.value)

    return q.name