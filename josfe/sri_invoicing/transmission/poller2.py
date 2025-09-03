# apps/josfe/josfe/sri_invoicing/transmission/poller2.py
from __future__ import annotations
import os, traceback, datetime as dt
import frappe
from frappe.utils import now_datetime, add_to_date



from josfe.sri_invoicing.transmission import soap
from josfe.sri_invoicing.xml.helpers import (
    _append_comment, _attach_private_file, _db_set_state, _format_msgs
)

# Backoff schedule in seconds (tweak as you like)
BACKOFF = [30, 60, 180, 300, 600]  # 30s, 1m, 3m, 5m, 10m

def _schedule_next(queue_name: str, clave: str, ambiente: str, attempt: int):
    if attempt >= len(BACKOFF):
        # Stop scheduling; operator can manually retry from UI
        return
    eta = add_to_date(now_datetime(), seconds=BACKOFF[attempt])
    frappe.enqueue(
        "josfe.sri_invoicing.transmission.poller2.poll_autorizacion_job",
        queue_name=queue_name,
        clave=clave,
        ambiente=ambiente,
        attempt=attempt+1,
        queue="long",
        job_name=f"sri_poll:{queue_name}:{attempt+1}",
        enqueue_after_commit=True,
        start_after=eta,  # <-- this is the v15 way
    )

@frappe.whitelist()
def poll_autorizacion_job(queue_name: str, clave: str, ambiente: str, attempt: int = 0):
    """
    Background poller. attempt starts at 0.
    """
    try:
        doc = frappe.get_doc("SRI XML Queue", queue_name)
    except Exception:
        frappe.log_error("poll_autorizacion_job: doc fetch failed", traceback.format_exc())
        return

    # If already final, stop
    if (doc.state or "").lower() in {"autorizado", "devuelto"}:
        return

    # Hit SRI
    try:
        auto = soap.consultar_autorizacion(clave, ambiente)
    except Exception:
        _append_comment(doc, "Error al invocar Autorización SRI (poll):\n```\n" + traceback.format_exc() + "\n```")
        _schedule_next(queue_name, clave, ambiente, attempt)
        return

    a_estado = (auto.get("estado") or "").upper()
    a_msgs = auto.get("mensajes") or []
    autorizado_xml = auto.get("xml_autorizado")

    # Terminal states
    if a_estado == "AUTORIZADO" and autorizado_xml:
        # Persist autorizado XML
        base_name = (doc.xml_file or "comprobante").split("/")[-1].split(".")[0]
        auth_filename = f"{base_name}.autorizado.xml"
        file_url = _attach_private_file(doc, auth_filename, autorizado_xml.encode("utf-8"))
        _append_comment(doc, _format_msgs("SRI (Autorización) AUTORIZADO", a_msgs) + f"\nArchivo: `{file_url}`")
        _db_set_state(doc, "Autorizado")
        return

    if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        _append_comment(doc, _format_msgs(f"SRI (Autorización) {a_estado}", a_msgs))
        _db_set_state(doc, "Devuelto")
        return

    # Still pending (PPR / EN PROCESO / empty)
    _append_comment(doc, _format_msgs(f"SRI (Autorización) {a_estado or 'PPR'}", a_msgs)
                         + f"\nReintento programado (intento {attempt+1}/{len(BACKOFF)}).")
    _schedule_next(queue_name, clave, ambiente, attempt)
