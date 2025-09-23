# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/service.py

from __future__ import annotations
import os, re, tempfile, subprocess
import frappe
import html
from frappe.utils import cstr, now_datetime, escape_html
from josfe.sri_invoicing.xml.utils import format_xml_bytes

from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.xml.xades_template import inject_signature_template
from josfe.sri_invoicing.xml import paths
from josfe.sri_invoicing.core.transmission import soap, poller2
from josfe.sri_invoicing.xml.helpers import (
    _append_comment, _attach_private_file, _db_set_state, _format_msgs
)

PRIVATE_PREFIX = "/private/files/"
paths.ensure_all_dirs()  # idempotent

# Logical SRI directories we always want under /private/files/SRI/<...>
FINAL_DIRS = {
    "GENERADOS",
    "FIRMADOS",
    "FIRMADOS/PENDIENTES",
    "FIRMADOS/RECHAZADOS",
    "FIRMADOS/Rechazados",   # tolerate existing mix-case
    "AUTORIZADOS",
    "NO_AUTORIZADOS",
}

# ------------------------------
# Path & file helpers
# ------------------------------
def _resolve_private_relpath(file_url: str) -> str | None:
    if not file_url:
        return None
    if file_url.startswith(PRIVATE_PREFIX):
        return file_url.split(PRIVATE_PREFIX, 1)[1].lstrip("/")
    frappe.throw(f"Unrecognized file_url format: {file_url}")

def _abs_from_url(file_url: str) -> str:
    rel = _resolve_private_relpath(file_url)
    return os.path.join(frappe.get_site_path("private", "files"), rel)

def _read_bytes(file_url: str) -> bytes:
    p = _abs_from_url(file_url)
    if not os.path.exists(p):
        frappe.throw(f"XML file not found on disk: {p}")
    with open(p, "rb") as f:
        return f.read()

def _move_xml_file(old_url: str, to_state: str, *, origin: str | None = None) -> str:
    """Move working XML to the correct SRI/ folder; return new /private/files/..."""
    if not old_url:
        return ""
    site_files = frappe.get_site_path("private", "files")
    old_rel = old_url.replace("/private/files/", "", 1).lstrip("/")
    old_abs = os.path.join(site_files, old_rel)

    filename = os.path.basename(old_abs)
    rel_dir = paths.rel_for_state(to_state, origin=origin)
    dest_abs = paths.abs_path(rel_dir, filename)

    if os.path.abspath(old_abs) == os.path.abspath(dest_abs):
        return paths.to_file_url(rel_dir, filename)

    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    if not os.path.exists(old_abs):
        frappe.throw(f"Source XML file not found: {old_abs}")
    os.replace(old_abs, dest_abs)
    return paths.to_file_url(rel_dir, filename)

def _write_to_sri(rel_dir: str, filename: str, data: bytes) -> str:
    # --- Normalize: always pass a LOGICAL dir (without leading 'SRI/')
    def _normalize_rel_dir(rd: str) -> str:
        rd_in = (rd or "").strip().replace("\\", "/").lstrip("/")
        # If caller passed 'SRI/...', strip it so paths.* can add it exactly once
        if rd_in.upper().startswith("SRI/"):
            frappe.logger("sri_flow").warning(
                f"[NORMALIZE] stripping leading 'SRI/': rel_dir='{rd}' → '{rd_in[4:]}'"
            )
            rd_in = rd_in[4:]  # remove 'SRI/'

        # Canonicalize to a known logical name if it matches (case-insensitive)
        # This avoids duplicates like 'FIRMADOS/Rechazados' vs 'FIRMADOS/RECHAZADOS'
        try:
            canon = next((d for d in FINAL_DIRS if d.upper() == rd_in.upper()), None)
            return canon or rd_in
        except Exception:
            return rd_in

    rel_dir = _normalize_rel_dir(rel_dir)

    dest = paths.abs_path(rel_dir, filename)  # paths.* adds the single 'SRI/' root
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    # Normalize XML before saving (pretty/clean wrappers)
    try:
        data = format_xml_bytes(data or b"")
    except Exception:
        pass

    with open(dest, "wb") as f:
        f.write(data or b"")

    # 🟢 Human-friendly rewrite for final states (AUTORIZADO/DEVUELTO/RECHAZADO)
    # rel_dir is logical (no 'SRI/'), so this check is reliable
    try:
        if any(stage in rel_dir.upper() for stage in ["AUTORIZADOS", "DEVUELTOS", "RECHAZADOS"]):
            text = (data or b"").decode("utf-8", errors="ignore")
            text = html.unescape(text)
            with open(dest, "w", encoding="utf-8") as ftxt:
                ftxt.write(text)
    except Exception as e:
        frappe.log_error(f"Unescape final XML failed: {e}", "SRI XML Queue")

    frappe.logger("sri_flow").info(f"[WRITE] rel_dir={rel_dir} filename={filename} → {dest}")
    return paths.to_file_url(rel_dir, filename)  # returns '/private/files/SRI/<rel_dir>/<filename>'


def _cleanup_after_authorized(filename: str) -> None:
    """When authorized, remove any duplicates from GENERADOS/FIRMADOS/PENDIENTES."""
    try:
        for rel in (paths.GEN, paths.SIGNED, paths.SIGNED_SENT_PENDING):
            p = paths.abs_path(rel, filename)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        frappe.log_error(frappe.get_traceback(), "SRI cleanup_after_authorized")

def cleanup_pendiente_if_rechazado(new_url: str):
    """
    If a .rechazado.xml or .no_autorizado.xml exists,
    remove the corresponding PENDIENTES .xml copy.
    """
    site_files = frappe.get_site_path("private", "files")
    base = os.path.basename(new_url)

    # strip suffixes like .rechazado.xml → .xml
    if base.endswith(".rechazado.xml"):
        orig = base.replace(".rechazado.xml", ".xml")
    elif base.endswith(".no_autorizado.xml"):
        orig = base.replace(".no_autorizado.xml", ".xml")
    else:
        return  # nothing to do

    pendiente_path = os.path.join(site_files, "SRI", "FIRMADOS", "PENDIENTES", orig)
    if os.path.exists(pendiente_path):
        try:
            os.remove(pendiente_path)
            frappe.logger("sri_flow").info(f"🧹 Removed leftover pendiente: {pendiente_path}")
        except Exception as e:
            frappe.log_error(f"Failed to delete pendiente {pendiente_path}: {e}", "SRI XML Cleanup")

# ------------------------------
# XML helpers
# ------------------------------
def _extract_clave_acceso(xml_bytes: bytes) -> str | None:
    """Extract <claveAcceso> from the XML (infoTributaria/claveAcceso)."""
    try:
        import lxml.etree as ET  # preferred
        root = ET.fromstring(xml_bytes)
        vals = root.xpath('//*[local-name()="claveAcceso"]/text()')
        if vals:
            return (vals[0] or "").strip()
    except Exception:
        pass
    # Regex fallback (best-effort)
    try:
        import re as _re
        m = _re.search(rb"<\s*claveAcceso\s*>\s*([0-9]+)\s*<\s*/\s*claveAcceso\s*>", xml_bytes)
        if m:
            return m.group(1).decode().strip()
    except Exception:
        pass
    return None


# ------------------------------
# Signing
# ------------------------------
def _process_signing(qdoc):
    """Sign XML with xmlsec1, then move into SRI/FIRMADOS/ and update xml_file field."""
    if not cstr(qdoc.xml_file):
        frappe.throw("No XML file path in this SRI XML Queue row.")

    site_files = frappe.get_site_path("private", "files")
    rel_old = (qdoc.xml_file or "").replace("/private/files/", "", 1).lstrip("/")
    old_path = os.path.join(site_files, rel_old)
    if not os.path.exists(old_path):
        frappe.throw(f"XML file not found on disk: {old_path}")

    # Load credentials
    cred = frappe.get_doc("Credenciales SRI", {"company": qdoc.company, "jos_activo": 1})
    priv_pem = frappe.get_site_path("private", "files", f"{cred.name}_private.pem")
    cert_pem = frappe.get_site_path("private", "files", f"{cred.name}_cert.pem")
    if not os.path.exists(priv_pem) or not os.path.exists(cert_pem):
        frappe.throw("❌ PEM files not found. Ejecuta 'Validar Firma' en Credenciales SRI.")

    # Inject signature template (ensures id="comprobante" on the document root)
    with open(old_path, "r", encoding="utf-8") as f:
        raw_xml = f.read()
    ready_xml = inject_signature_template(raw_xml, cert_pem)
    if ready_xml != raw_xml:
        with open(old_path, "w", encoding="utf-8") as f:
            f.write(ready_xml)

    # 🔁 Dynamic, future-proof signing for any SRI doc type
    #    (factura, notaCredito, notaDebito, retencion, guiaRemision, etc.)
    from josfe.sri_invoicing.xml.signer import sign_with_xmlsec

    try:
        with open(old_path, "rb") as f:
            signed = sign_with_xmlsec(f.read(), priv_pem, cert_pem)
        with open(old_path, "wb") as f:
            f.write(signed)
    except Exception as e:
        # Keep the original stderr visible if it came from xmlsec
        msg = getattr(e, "args", [str(e)])[0]
        frappe.throw(f"Error ejecutando xmlsec1: {frappe.utils.escape_html(msg)}")

    # ✅ Move to FIRMADOS and update DB immediately
    new_url = _move_xml_file(qdoc.xml_file, "Firmado")
    if new_url:
        qdoc.db_set("xml_file", new_url)
        qdoc.xml_file = new_url

    # Bookkeeping
    qdoc.db_set("last_error", "")
    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)

    # Timeline note
    try:
        from josfe.sri_invoicing.xml.helpers import _append_comment
        _append_comment(qdoc, "✔ XML firmado correctamente.")
    except Exception:
        pass


def _process_transmission(qdoc, stage_state: str):
    """Handle movement + calls for Enviado/Autorizado/Devuelto."""
    if not cstr(qdoc.xml_file):
        frappe.throw("No XML file path in this SRI XML Queue row.")

    state = (stage_state or "").strip()
    origin = getattr(frappe.flags, "sri_devuelto_origin", None)

    if state == SRIQueueState.Enviado.value:
        # 1) Move to PENDIENTES right away
        try:
            moved = _move_xml_file(qdoc.xml_file, "Enviado")
            if moved:
                qdoc.db_set("xml_file", moved)
        except Exception:
            pass

        # 2) Recepción (one call)
        xml_bytes = None
        try:
            site_files = frappe.get_site_path("private", "files")
            rel_old = (qdoc.xml_file or "").replace("/private/files/", "", 1).lstrip("/")
            old_path = os.path.join(site_files, rel_old)
            with open(old_path, "rb") as f:
                xml_bytes = f.read()
        except Exception:
            pass

        rc = {}
        try:
            from josfe.sri_invoicing.core.transmission import soap
            rc = soap.enviar_recepcion(xml_bytes or b"")
        except Exception:
            rc = {}

        r_estado = (rc.get("estado") or "").upper()
        r_msgs = rc.get("mensajes") or []
        ambiente = rc.get("ambiente") or "Pruebas"
        r_wrap = rc.get("xml_wrapper") or ""

        # helper: detect id=43 "CLAVE ACCESO REGISTRADA"
        def is_id_43(msgs):
            for m in msgs or []:
                if (m.get("identificador") or "").strip() == "43":
                    return True
                txt = ((m.get("mensaje") or "") + " " + (m.get("informacionAdicional") or "")).upper()
                if "CLAVE ACCESO REGISTRADA" in txt:
                    return True
            return False

        # 3) True reception DEVUELTA/RECHAZADO (not 43) → Rechazados + Devuelto
        if r_estado in {"DEVUELTA", "RECHAZADO"} and not is_id_43(r_msgs):
            frappe.flags.sri_devuelto_origin = "Recepción"
            base = os.path.basename(qdoc.xml_file).rsplit(".", 1)[0]
            rej_name = f"{base}.rechazado.xml"
            url = _write_to_sri(paths.SIGNED_REJECTED, rej_name, (r_wrap or "").encode("utf-8"))
            qdoc.db_set("xml_file", url)
            
            cleanup_pendiente_if_rechazado(url)
            try:
                from josfe.sri_invoicing.xml.helpers import _append_comment, _format_msgs, _db_set_state
                _append_comment(qdoc, _format_msgs("SRI (Recepción) DEVUELTA/RECHAZADO", r_msgs))
                _db_set_state(qdoc, "Devuelto")
            except Exception:
                qdoc.db_set("state", "Devuelto")
            return

        # 4) RECIBIDA or id=43 → try Autorización immediately
        clave = ""
        try:
            import re as _re
            m = _re.search(rb"<\s*claveAcceso\s*>\s*([0-9]+)\s*<\s*/\s*claveAcceso\s*>", xml_bytes or b"")
            if m:
                clave = m.group(1).decode().strip()
        except Exception:
            pass

        auto = {}
        try:
            from josfe.sri_invoicing.core.transmission import soap
            auto = soap.consultar_autorizacion(clave, ambiente)
        except Exception:
            auto = {}

        a_estado = (auto.get("estado") or "").upper()
        a_msgs = auto.get("mensajes") or []
        a_wrap = auto.get("xml_wrapper") or auto.get("xml_autorizado")

        if a_estado == "AUTORIZADO" and a_wrap:
            base = os.path.basename(qdoc.xml_file).rsplit(".", 1)[0]
            # ✅ keep original filename (no .autorizado suffix)
            file_url = _write_to_sri(paths.AUTH, f"{base}.xml", (a_wrap or "").encode("utf-8"))
            qdoc.db_set("xml_file", file_url)
            try:
                from josfe.sri_invoicing.xml.helpers import _append_comment, _format_msgs, _db_set_state
                _append_comment(qdoc, _format_msgs("SRI (Autorización) AUTORIZADO", a_msgs) + f"\nArchivo: `{file_url}`")
                _db_set_state(qdoc, "Autorizado")
            except Exception:
                qdoc.db_set("state", "Autorizado")
            try:
                # ✅ remove stale copies (Generados/Firmados/Pendientes)
                _cleanup_after_authorized(os.path.basename(file_url))
            except Exception:
                pass
            return

        if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
            frappe.flags.sri_devuelto_origin = "Autorización"
            base = os.path.basename(qdoc.xml_file).rsplit(".", 1)[0]
            nat_name = f"{base}.xml"
            if auto.get("xml_wrapper"):
                nat_url = _write_to_sri(paths.NOT_AUTH, nat_name, auto["xml_wrapper"].encode("utf-8"))
                qdoc.db_set("xml_file", nat_url)

                cleanup_pendiente_if_rechazado(nat_url)
            else:
                moved = _move_xml_file(qdoc.xml_file, "Devuelto", origin="Autorización")
                if moved:
                    qdoc.db_set("xml_file", moved)
            try:
                from josfe.sri_invoicing.xml.helpers import _append_comment, _format_msgs, _db_set_state
                _append_comment(qdoc, _format_msgs(f"SRI (Autorización) {a_estado}", a_msgs))
                _db_set_state(qdoc, "Devuelto")
            except Exception:
                qdoc.db_set("state", "Devuelto")
            return

        # 5) Still PPR — leave Enviado and schedule poller
        try:
            from josfe.sri_invoicing.xml.helpers import _append_comment, _format_msgs
            _append_comment(qdoc, _format_msgs(f"SRI (Autorización) {a_estado or 'PPR'}", a_msgs))
        except Exception:
            pass
        try:
            from josfe.sri_invoicing.core.transmission import poller2
            poller2.poll_autorizacion_job(queue_name=qdoc.name, clave=clave, ambiente=ambiente, attempt=0)
        except Exception:
            frappe.enqueue(
                "josfe.sri_invoicing.core.transmission.poller2.poll_autorizacion_job",
                queue_name=qdoc.name, clave=clave, ambiente=ambiente, attempt=0,
                queue="long", job_name=f"sri_poll:{qdoc.name}:0", enqueue_after_commit=True
            )

    elif state == SRIQueueState.Autorizado.value:
        # ✅ ensure final file is only in AUTORIZADOS, clean old copies
        filename = os.path.basename(qdoc.xml_file)
        new_url = _move_xml_file(qdoc.xml_file, "Autorizado")
        if new_url:
            qdoc.db_set("xml_file", new_url)
            try:
                _cleanup_after_authorized(filename)
            except Exception:
                pass

    elif state == SRIQueueState.Devuelto.value:
        new_url = _move_xml_file(qdoc.xml_file, "Devuelto", origin=origin)
        if new_url:
            qdoc.db_set("xml_file", new_url)

    # Bookkeeping (do not remove)
    qdoc.db_set("last_error", "")
    qdoc.db_set("last_transition_at", now_datetime())
    qdoc.db_set("last_transition_by", frappe.session.user)

# ------------------------------
# Hook: on_update
# ------------------------------
def on_queue_update(doc, method=None):
    """Single, merged entry point (service2 deleted)."""
    try:
        state = cstr(doc.state)

        # Ensure GENERADOS path (only when needed) — NO early return here
        if state == SRIQueueState.Generado.value:
            if doc.xml_file and not doc.xml_file.startswith("/private/files/SRI/GENERADOS/"):
                try:
                    new_url = _move_xml_file(doc.xml_file, "Generado")
                    if new_url:
                        doc.db_set("xml_file", new_url)
                except Exception:
                    frappe.log_error(frappe.get_traceback(), "SRI move GENERADO")

        elif state == SRIQueueState.Firmado.value:
            _process_signing(doc)

        elif state in {
            SRIQueueState.Enviado.value,
            SRIQueueState.Autorizado.value,
            SRIQueueState.Devuelto.value,
        }:
            _process_transmission(doc, state)

        # Cancelado / Error -> no file movement

    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="SRI XML Queue on_update failure (service.py)",
        )

# ------------------------------
# Unified sender: Enviar & Reenviar call this one entry point
# ------------------------------
@frappe.whitelist()
def send_to_sri(qname: str, is_retry: int = 0):
    """
    Single entry point for both 'Enviar' and 'Reenviar'.
    Runs the same Recepción → Autorización pipeline and writes via _write_to_sri().
    """
    qdoc = frappe.get_doc("SRI XML Queue", qname)
    frappe.logger("sri_flow").info(f"[SEND] start q={qname} retry={is_retry} state={qdoc.state}")

    # Ensure signed file is in place; users may hit re-send after edits
    if (cstr(qdoc.state) or "").strip() == SRIQueueState.Generado.value:
        _process_signing(qdoc)

    # Drive the same transmission pipeline used by state updates
    _process_transmission(qdoc, SRIQueueState.Enviado.value)

    frappe.logger("sri_flow").info(f"[SEND] end   q={qname} retry={is_retry} state={qdoc.state} file={qdoc.xml_file}")
    return {"ok": True, "name": qdoc.name, "state": qdoc.state, "xml_file": qdoc.xml_file}