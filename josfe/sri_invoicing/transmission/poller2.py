# apps/josfe/josfe/sri_invoicing/transmission/poller2.py
from __future__ import annotations
import os, traceback, datetime as dt
import frappe
from frappe.utils import now_datetime, add_to_date

from josfe.sri_invoicing.transmission import soap
from josfe.sri_invoicing.xml.helpers import (
    _append_comment, _db_set_state, _format_msgs
)
from josfe.sri_invoicing.xml import paths
from josfe.sri_invoicing.xml import service as xml_service

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
        start_after=eta,  # v15 style
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
    autorizado_xml_inner = auto.get("xml_autorizado")  # inner original XML
    xml_wrapper = auto.get("xml_wrapper") or ""        # our compact wrapper

    # Terminal states
    if a_estado == "AUTORIZADO" and (xml_wrapper or autorizado_xml_inner):
        # Prefer wrapper for storage/trace; fall back to inner if missing
        base_name = (doc.xml_file or "comprobante").split("/")[-1].split(".")[0]
        auth_filename = f"{base_name}.xml"  # ✅ unified: plain .xml in AUTORIZADOS
        payload = (xml_wrapper or autorizado_xml_inner or "").encode("utf-8")

        # Single source of truth: save under SRI/AUTORIZADOS
        file_url = xml_service._write_to_sri(
            rel_dir=paths.AUTH,
            filename=auth_filename,
            data=payload,
        )
        try:
            doc.db_set("xml_file", file_url)
        except Exception:
            pass

        # Comment with the canonical SRI path (no extra attachment)
        _append_comment(
            doc,
            _format_msgs("SRI (Autorización) AUTORIZADO", a_msgs) + f"\nArchivo: `{file_url}`"
        )

        # State + cleanup of stale copies (Generados/Firmados/Pendientes)
        _db_set_state(doc, "Autorizado")
        try:
            # lazy import to avoid circular: service imports poller2, so poller2 must not import service at module import time
            from josfe.sri_invoicing.xml import service as _svc
            _svc._cleanup_after_authorized(auth_filename)
        except Exception:
            pass
        return

    if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        frappe.flags.sri_devuelto_origin = "Autorización"
        _append_comment(doc, _format_msgs(f"SRI (Autorización) {a_estado}", a_msgs))

        base_name = (doc.xml_file or "comprobante").split("/")[-1].split(".")[0]
        nat_filename = f"{base_name}.xml"  # ✅ unified: plain .xml in NO_AUTORIZADOS

        if xml_wrapper:
            nat_url = xml_service._write_to_sri(
                rel_dir=paths.NOT_AUTH,
                filename=nat_filename,
                data=xml_wrapper.encode("utf-8"),
            )
            try:
                doc.db_set("xml_file", nat_url)
            except Exception:
                pass
        else:
            try:
                moved = xml_service._move_xml_file(doc.xml_file, "Devuelto", origin="Autorización")
                if moved:
                    doc.db_set("xml_file", moved)
            except Exception:
                pass

        _db_set_state(doc, "Devuelto")

        # ✅ Canonical cleanup: remove stale copies (Generados/Firmados/Pendientes)
        try:
            # lazy import avoids circular import with service ↔ poller2
            from josfe.sri_invoicing.xml import service as _svc
            _svc._cleanup_after_authorized(nat_filename)
        except Exception:
            # Fallback: at least remove the PENDIENTES copy
            try:
                # make sure `import os` is at the top of this file
                pend_abs = paths.abs_path(paths.SIGNED_SENT_PENDING, nat_filename)
                if os.path.exists(pend_abs):
                    os.remove(pend_abs)
            except Exception:
                pass

        return

    # Still pending (PPR / EN PROCESO / empty)
    _append_comment(
        doc,
        _format_msgs(f"SRI (Autorización) {a_estado or 'PPR'}", a_msgs)
        + f"\nReintento programado (intento {attempt+1}/{len(BACKOFF)})."
    )

    # Ensure it stays physically under FIRMADOS/PENDIENTES while we wait
    try:
        moved = xml_service._move_xml_file(doc.xml_file, "Enviado")

        if moved:
            doc.db_set("xml_file", moved)
    except Exception:
        pass

    _schedule_next(queue_name, clave, ambiente, attempt)
