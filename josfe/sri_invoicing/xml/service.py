# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/service.py

from __future__ import annotations
import os, re, tempfile, subprocess
import frappe
from frappe.utils import cstr, now_datetime, escape_html

from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.xml.xades_template import inject_signature_template
from josfe.sri_invoicing.xml import paths
from josfe.sri_invoicing.transmission import soap, poller2
from josfe.sri_invoicing.xml.helpers import (
    _append_comment, _attach_private_file, _db_set_state, _format_msgs
)

PRIVATE_PREFIX = "/private/files/"
paths.ensure_all_dirs()  # idempotent


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
    dest = paths.abs_path(rel_dir, filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data or b"")
    return paths.to_file_url(rel_dir, filename)

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

    # Inject signature template
    with open(old_path, "r", encoding="utf-8") as f:
        raw_xml = f.read()
    ready_xml = inject_signature_template(raw_xml, cert_pem)
    if ready_xml != raw_xml:
        with open(old_path, "w", encoding="utf-8") as f:
            f.write(ready_xml)

    # Run xmlsec1
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_out:
        cmd = [
            "xmlsec1", "--sign",
            "--privkey-pem", f"{priv_pem},{cert_pem}",
            "--id-attr:id", "factura",
            "--output", tmp_out.name,
            old_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode(errors="ignore") or str(e)
            frappe.throw(f"Error ejecutando xmlsec1: {frappe.utils.escape_html(stderr)}")

        os.replace(tmp_out.name, old_path)

    # ✅ Move to FIRMADOS and update DB immediately
    new_url = _move_xml_file(qdoc.xml_file, "Firmado")
    if new_url:
        qdoc.db_set("xml_file", new_url)   # commit new path to DB
        qdoc.xml_file = new_url            # update in-memory doc for next steps

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


# ------------------------------
# Transmission (Recepción + Poller)
# ------------------------------
def _send_to_recepcion_and_route(qdoc) -> None:
    """
    Submit to SRI Recepción. Route file/state based on the response:
    - DEVUELTA/RECHAZADO (not id=43) -> FIRMADOS/Rechazados + state Devuelto
    - RECIBIDA or DEVUELTA id=43 -> immediately query Autorización
    - Autorización result:
        * AUTORIZADO -> AUTORIZADOS + state Autorizado
        * NO AUTORIZADO/RECHAZADO/DEVUELTA -> NO_AUTORIZADOS + state Devuelto
        * PPR -> leave in PENDIENTES, state Enviado, schedule poller
    """
    xml_bytes = _read_bytes(qdoc.xml_file)
    result = soap.enviar_recepcion(xml_bytes)

    r_estado = (result.get("estado") or "").upper()
    r_msgs = result.get("mensajes") or []
    ambiente = result.get("ambiente") or "Pruebas"
    r_wrap = result.get("xml_wrapper") or ""

    # helper: detect id=43 "CLAVE ACCESO REGISTRADA"
    def is_id_43(msgs):
        for m in msgs or []:
            if (m.get("identificador") or "").strip() == "43":
                return True
            txt = ((m.get("mensaje") or "") + " " + (m.get("informacionAdicional") or "")).upper()
            if "CLAVE ACCESO REGISTRADA" in txt:
                return True
        return False

    # If Recepción says DEVUELTA/RECHAZADO but it's id=43 → treat as RECIBIDA
    if r_estado in {"DEVUELTA", "RECHAZADO"} and not is_id_43(r_msgs):
        frappe.flags.sri_devuelto_origin = "Recepción"
        base = os.path.basename(qdoc.xml_file).rsplit(".", 1)[0]
        rej_name = f"{base}.rechazado.xml"
        url = _write_to_sri(paths.SIGNED_REJECTED, rej_name, (r_wrap or "").encode("utf-8"))
        qdoc.db_set("xml_file", url)
        _append_comment(qdoc, _format_msgs("SRI (Recepción) DEVUELTA/RECHAZADO", r_msgs))
        _db_set_state(qdoc, "Devuelto")
        return

    # Otherwise (RECIBIDA or id=43 case) → try Autorización immediately
    clave = _extract_clave_acceso(xml_bytes) or ""
    if not clave:
        _append_comment(qdoc, "⚠ No se pudo extraer claveAcceso; no se puede consultar Autorización.")
        return

    auto = soap.consultar_autorizacion(clave, ambiente)
    a_estado = (auto.get("estado") or "").upper()
    a_msgs = auto.get("mensajes") or []
    a_wrap = auto.get("xml_wrapper") or auto.get("xml_autorizado")

    if a_estado == "AUTORIZADO" and a_wrap:
        base = os.path.basename(qdoc.xml_file).rsplit(".", 1)[0]
        auth_name = f"{base}.autorizado.xml"
        file_url = _write_to_sri(paths.AUTH, auth_name, (a_wrap or "").encode("utf-8"))
        qdoc.db_set("xml_file", file_url)
        _append_comment(qdoc, _format_msgs("SRI (Autorización) AUTORIZADO", a_msgs) + f"\nArchivo: `{file_url}`")
        _db_set_state(qdoc, "Autorizado")
        try:
            _cleanup_after_authorized(os.path.basename(file_url))
        except Exception:
            pass
        return

    if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        frappe.flags.sri_devuelto_origin = "Autorización"
        base = os.path.basename(qdoc.xml_file).rsplit(".", 1)[0]
        nat_name = f"{base}.no_autorizado.xml"
        if auto.get("xml_wrapper"):
            nat_url = _write_to_sri(paths.NOT_AUTH, nat_name, auto["xml_wrapper"].encode("utf-8"))
            qdoc.db_set("xml_file", nat_url)
        else:
            moved = _move_xml_file(qdoc.xml_file, "Devuelto", origin="Autorización")
            if moved:
                qdoc.db_set("xml_file", moved)
        _append_comment(qdoc, _format_msgs(f"SRI (Autorización) {a_estado}", a_msgs))
        _db_set_state(qdoc, "Devuelto")
        return

    # Still PPR
    _append_comment(qdoc, _format_msgs(f"SRI (Autorización) {a_estado or 'PPR'}", a_msgs))
    try:
        from josfe.sri_invoicing.transmission import poller2
        poller2.poll_autorizacion_job(queue_name=qdoc.name, clave=clave, ambiente=ambiente, attempt=0)
    except Exception:
        frappe.enqueue(
            "josfe.sri_invoicing.transmission.poller2.poll_autorizacion_job",
            queue_name=qdoc.name, clave=clave, ambiente=ambiente, attempt=0,
            queue="long", job_name=f"sri_poll:{qdoc.name}:0", enqueue_after_commit=True
        )


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
            from josfe.sri_invoicing.transmission import soap
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
            from josfe.sri_invoicing.transmission import soap
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
            from josfe.sri_invoicing.transmission import poller2
            poller2.poll_autorizacion_job(queue_name=qdoc.name, clave=clave, ambiente=ambiente, attempt=0)
        except Exception:
            frappe.enqueue(
                "josfe.sri_invoicing.transmission.poller2.poll_autorizacion_job",
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
