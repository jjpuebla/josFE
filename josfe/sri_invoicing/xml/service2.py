# apps/josfe/josfe/sri_invoicing/xml/service2.py
# Sandbox wrapper for XML Queue updates:
# - Delegates to base service.on_queue_update (keeps existing signing flow)
# - Adds transmission flow for state == "Enviado" using soap.enviar_recepcion / consultar_autorizacion
#
# Merge back into service.py once validated.

from __future__ import annotations
import os
import re
import traceback
import frappe
from frappe.utils import now_datetime

# Reuse your tested behavior
from . import service as base_service
from josfe.sri_invoicing.transmission import soap


def on_queue_update(doc, method=None):
    """
    Entry point wired from hooks (temporarily replace service.on_queue_update).
    1) Run original signing flow (base_service)
    2) If state == "Enviado", perform Recepción + Autorización and update Queue state
    """
    try:
        # 1) Delegate to the original handler (signing on "Firmado", etc.)
        try:
            base_service.on_queue_update(doc, method)
        except Exception:
            # We don't fail fast; continue so we can still handle Enviado when needed.
            frappe.log_error(
                title="[service2] base_service.on_queue_update failed",
                message=traceback.format_exc(),
            )

        # Reload to get latest changes done by base_service
        doc.reload()

        # 2) Transmission path
        if (doc.state or "").strip().lower() == "enviado":
            _handle_transmission(doc)

    except Exception:
        frappe.log_error(
            title="[service2] on_queue_update unhandled error",
            message=traceback.format_exc(),
        )


# -------------------------
# Transmission helpers
# -------------------------
def _format_msgs(title: str, mensajes) -> str:
    """
    Pretty-print SRI messages returned by soap.* calls.
    Accepts str / dict / list[dict|str]. Returns Markdown.
    """
    # Simple string or no messages
    if mensajes is None:
        return f"**{title}**: (sin mensajes)"
    if isinstance(mensajes, (bytes, str)):
        if isinstance(mensajes, bytes):
            try:
                mensajes = mensajes.decode("utf-8", errors="ignore")
            except Exception:
                mensajes = repr(mensajes)
        return f"**{title}**\n```\n{mensajes}\n```"

    # Normalize to list
    if isinstance(mensajes, dict):
        mensajes = [mensajes]
    if not isinstance(mensajes, (list, tuple)):
        return f"**{title}**\n- {repr(mensajes)}"

    lines = []
    for m in mensajes:
        if isinstance(m, dict):
            ident = (m.get("identificador") or m.get("codigo") or m.get("ident") or "").strip()
            texto = (m.get("mensaje") or m.get("texto") or m.get("detalle") or "").strip()
            info  = (m.get("informacionAdicional") or m.get("info") or "").strip()
            tipo  = (m.get("tipo") or "").strip()

            parts = []
            if ident:
                parts.append(f"[{ident}]")
            if texto:
                parts.append(texto)
            entry = " ".join(parts) if parts else repr(m)

            if info:
                entry += f" — {info}"
            if tipo:
                entry += f" ({tipo})"

            lines.append(f"- {entry}")
        else:
            lines.append(f"- {m!r}")

    return f"**{title}**\n" + "\n".join(lines)

def _handle_transmission(doc):
    """Send signed XML to SRI (Recepción), then query Autorización once."""
    # 0) Load signed XML bytes from file referenced in the queue row
    signed_path = _resolve_fs_path(doc.xml_file)
    xml_bytes = _read_bytes(signed_path)

    # 1) Recepción
    recep = {}
    try:
        recep = soap.enviar_recepcion(xml_bytes)
    except Exception:
        _append_comment(
            doc,
            "Error al invocar Recepción SRI:\n```\n" + traceback.format_exc() + "\n```"
        )
        # Keep it in Enviado (operator can retry)
        return

    estado = (recep.get("estado") or "").upper()
    mensajes = recep.get("mensajes") or []

    if estado == "DEVUELTA":
        _append_comment(doc, _format_msgs("SRI (Recepción) DEVUELTA", mensajes))
        _db_set_state(doc, "Devuelto")
        return

    if estado != "RECIBIDA":
        _append_comment(
            doc,
            f"SRI (Recepción) estado inesperado: **{estado}**\n"
            + _format_msgs("Mensajes", mensajes)
        )
        # Keep Enviado; operator can retry or check endpoints/timeouts
        return

    _append_comment(doc, _format_msgs("SRI (Recepción) RECIBIDA", mensajes))

    # 2) Autorización (single shot check; if still en proceso, keep Enviado)

    # Try to get claveAcceso from XML first, fallback to doc fields
    clave = (
        _extract_clave_acceso(xml_bytes)
        or getattr(doc, "clave_acceso", None)
        or getattr(doc, "access_key", None)
    )
    if not clave:
        _append_comment(
            doc,
            "No se pudo determinar **claveAcceso** para Autorización "
            "(ni en XML ni en campos del Doc)."
        )
        return

    # Ambiente must match the one used in Recepción
    ambiente_used = recep.get("ambiente") or "Pruebas"

    try:
        auto = soap.consultar_autorizacion(clave, ambiente_used)
    except Exception:
        _append_comment(
            doc,
            "Error al invocar Autorización SRI:\n```\n" + traceback.format_exc() + "\n```"
        )
        return

    a_estado = (auto.get("estado") or "").upper()
    a_msgs = auto.get("mensajes") or []
    autorizado_xml = auto.get("xml_autorizado")  # str if AUTORIZADO

    if a_estado == "AUTORIZADO" and autorizado_xml:
        # Persist autorizado XML as a File attached to the queue row
        base_name = os.path.splitext(os.path.basename(signed_path))[0]
        auth_filename = f"{base_name}.autorizado.xml"
        file_url = _attach_private_file(doc, auth_filename, autorizado_xml.encode("utf-8"))
        _append_comment(
            doc,
            _format_msgs("SRI (Autorización) AUTORIZADO", a_msgs) + f"\nArchivo: `{file_url}`"
        )
        _db_set_state(doc, "Autorizado")
        return

    if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        _append_comment(doc, _format_msgs(f"SRI (Autorización) {a_estado}", a_msgs))
        _db_set_state(doc, "Devuelto")
        return

    # Fallback: leave in Enviado if still pending
    _append_comment(
        doc,
        _format_msgs(f"SRI (Autorización) {a_estado or 'SIN RESPUESTA'}", a_msgs)
        + "\nSeguiremos en **Enviado**; reintentar más tarde."
    )
    
def _resolve_fs_path(file_url: str) -> str:
    """
    Convert a file_url like '/private/files/Firmado/xxx.xml' or 'private/files/Firmado/xxx.xml'
    to an absolute FS path under the current site's directory.
    """
    if not file_url:
        frappe.throw("Queue row has empty xml_file path (se esperaba XML Firmado).")
    site_root = frappe.get_site_path()  # e.g., /home/bench/sites/dev.example.com
    cleaned = file_url.lstrip("/")
    return os.path.join(site_root, cleaned)


def _read_bytes(path: str) -> bytes:
    if not os.path.exists(path):
        frappe.throw(f"Archivo XML no existe: {path}")
    with open(path, "rb") as f:
        return f.read()


def _extract_clave_acceso(xml_bytes: bytes) -> str | None:
    """
    Best-effort extraction of <claveAcceso> from XML.
    """
    try:
        text = xml_bytes.decode("utf-8", errors="ignore")
        m = re.search(r"<claveAcceso>\s*([0-9]{10,60})\s*</claveAcceso>", text)
        return m.group(1) if m else None
    except Exception:
        return None


def _attach_private_file(doc, filename: str, content: bytes) -> str:
    """
    Store a private File attached to the queue document and return file_url.
    """
    filedoc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "is_private": 1,
        "attached_to_doctype": doc.doctype,
        "attached_to_name": doc.name,
        "content": content,
        "folder": "Home/Attachments",
    }).insert(ignore_permissions=True)
    return filedoc.file_url


def _append_comment(doc, message: str):
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
        "content": message,
        "seen": 0,
    }).insert(ignore_permissions=True)


def _db_set_state(doc, new_state: str):
    doc.db_set("state", new_state)
    # Keep modified consistent
    doc.db_set("modified", now_datetime())
    frappe.db.commit()
