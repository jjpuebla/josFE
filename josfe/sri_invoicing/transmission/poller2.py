# apps/josfe/josfe/sri_invoicing/transmission/poller2.py
from __future__ import annotations
import os, traceback, datetime as dt
import frappe
from frappe.utils import now_datetime, add_to_date

from josfe.sri_invoicing.transmission import soap
from josfe.sri_invoicing.xml.helpers import (
    _append_comment, _attach_private_file, _db_set_state, _format_msgs
)
from josfe.sri_invoicing.xml import paths  # new: route files into SRI/ tree

# Backoff schedule in seconds (tweak as you like)
BACKOFF = [30, 60, 180, 300, 600]  # 30s, 1m, 3m, 5m, 10m

# --- tiny local movers to avoid touching other modules ---
def _write_to_sri(rel_dir: str, filename: str, data: bytes) -> str:
    dest = paths.abs_path(rel_dir, filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data or b"")
    rel = os.path.join(paths.ROOT_FOLDER_NAME, rel_dir, filename).replace("\\", "/")
    return f"/private/files/{rel}"

def _move_xml_to(rel_dir: str, file_url: str) -> str:
    if not file_url:
        return ""
    site_files = frappe.get_site_path("private", "files")
    old_rel = file_url.replace("/private/files/", "", 1).lstrip("/")
    old_abs = os.path.join(site_files, old_rel)
    fname = os.path.basename(old_abs)
    new_abs = paths.abs_path(rel_dir, fname)
    if os.path.abspath(old_abs) != os.path.abspath(new_abs) and os.path.exists(old_abs):
        os.makedirs(os.path.dirname(new_abs), exist_ok=True)
        os.replace(old_abs, new_abs)
    rel = os.path.join(paths.ROOT_FOLDER_NAME, rel_dir, fname).replace("\\", "/")
    return f"/private/files/{rel}"

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
        auth_filename = f"{base_name}.autorizado.xml"
        payload = (xml_wrapper or autorizado_xml_inner or "").encode("utf-8")

        # 1) Timeline attachment for audit (keeps your current behavior)
        attach_url = _attach_private_file(doc, auth_filename, payload)
        _append_comment(doc, _format_msgs("SRI (Autorización) AUTORIZADO", a_msgs) + f"\nArchivo: `{attach_url}`")

        # 2) Primary working file into SRI/AUTORIZADOS and update doc.xml_file
        file_url = _write_to_sri(paths.AUTH, auth_filename, payload)
        try:
            doc.db_set("xml_file", file_url)
        except Exception:
            pass

        _db_set_state(doc, "Autorizado")
        return

    if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        # Tag origin explicitly (soap already sets this, but do it again for safety)
        frappe.flags.sri_devuelto_origin = "Autorización"

        _append_comment(doc, _format_msgs(f"SRI (Autorización) {a_estado}", a_msgs))

        # Prefer wrapper if available; else move current XML into NO_AUTORIZADOS
        base_name = (doc.xml_file or "comprobante").split("/")[-1].split(".")[0]
        nat_filename = f"{base_name}.no_autorizado.xml"

        if xml_wrapper:
            nat_url = _write_to_sri(paths.NOT_AUTH, nat_filename, xml_wrapper.encode("utf-8"))
            try:
                doc.db_set("xml_file", nat_url)
            except Exception:
                pass
        else:
            try:
                moved = _move_xml_to(paths.NOT_AUTH, doc.xml_file)
                if moved:
                    doc.db_set("xml_file", moved)
            except Exception:
                pass

        _db_set_state(doc, "Devuelto")
        return

    # Still pending (PPR / EN PROCESO / empty)
    _append_comment(
        doc,
        _format_msgs(f"SRI (Autorización) {a_estado or 'PPR'}", a_msgs)
        + f"\nReintento programado (intento {attempt+1}/{len(BACKOFF)})."
    )

    # Ensure it stays physically under FIRMADOS/PENDIENTES while we wait
    try:
        moved = _move_xml_to(paths.SIGNED_SENT_PENDING, doc.xml_file)
        if moved:
            doc.db_set("xml_file", moved)
    except Exception:
        pass

    _schedule_next(queue_name, clave, ambiente, attempt)
