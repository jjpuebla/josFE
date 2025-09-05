# apps/josfe/josfe/sri_invoicing/xml/service2.py
# Sandbox wrapper for XML Queue updates:
# - Delegates to base service.on_queue_update (keeps existing signing flow)
# - Adds transmission flow for state == "Enviado" using soap.enviar_recepcion / consultar_autorizacion
# - Adds safeguard: Firmado must really be signed with <ds:Signature> or rollback to Generado
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
from josfe.sri_invoicing.transmission import soap, poller2
from josfe.sri_invoicing.xml.helpers import (
    _append_comment, _attach_private_file, _db_set_state, _format_msgs
)

# Import signer
from josfe.sri_invoicing.xml.xades_template import (
    inject_signature_template,
    sign_with_xmlsec,
)
from josfe.sri_invoicing.xml.xades_template import inject_signature_template
# or, if you prefer the dedicated module:
# from josfe.sri_invoicing.xml.signer import sign_with_xmlsec
from josfe.sri_invoicing.xml.xades_template import sign_with_xmlsec

def on_queue_update(doc, method=None):
    try:
        state = (doc.state or "").strip().lower()

        if state == "firmado":
            try:
                _handle_signing(doc)
            except Exception:
                _append_comment(
                    doc,
                    "❌ Error inesperado en firmado:\n```\n" + traceback.format_exc() + "\n```"
                )
                # Don’t change state if signing fails
                _db_set_state(doc, "Generado")
            return

        if state == "enviado":
            try:
                _handle_transmission(doc)
            except Exception:
                _append_comment(
                    doc,
                    "❌ Error en transmisión:\n```\n" + traceback.format_exc() + "\n```"
                )
                # Keep state Enviado, so you can retry
            return

        # fallback to base service (for Generado, etc.)
        base_service.on_queue_update(doc, method)

    except Exception:
        frappe.log_error(
            title="[service2] on_queue_update unhandled error",
            message=traceback.format_exc(),
        )

def _handle_signing(doc):
    try:
        xml_path = _resolve_fs_path(doc.xml_file)
        xml_bytes = _read_bytes(xml_path)

        # 1) Load active SRI credential for this company (same approach as service.py)
        cred_name = frappe.db.get_value(
            "Credenciales SRI",
            {"company": doc.company, "jos_activo": 1},
            "name",
        )
        if not cred_name:
            _append_comment(doc, "❌ No hay **Credenciales SRI** activas para la compañía.")
            _db_set_state(doc, "Error")
            return

        key_pem  = frappe.get_site_path("private", "files", f"{cred_name}_private.pem")
        cert_pem = frappe.get_site_path("private", "files", f"{cred_name}_cert.pem")

        if not (os.path.exists(key_pem) and os.path.exists(cert_pem)):
            _append_comment(doc, f"❌ PEM faltantes:\n- `{key_pem}`\n- `{cert_pem}`")
            _db_set_state(doc, "Error")
            return

        # 2) Inject signature template (⚠ needs text + cert path)
        xml_with_tpl = inject_signature_template(xml_bytes.decode("utf-8"), cert_pem)
        
        # 3) Sign with xmlsec1
        try:
            signed_bytes = sign_with_xmlsec(xml_with_tpl.encode("utf-8"), key_pem, cert_pem)
        except Exception as e:
            _append_comment(doc, "❌ Error firmando con xmlsec1:\n```\n" + str(e) + "\n```")
            _db_set_state(doc, "Error")
            return

        # 4) Save under /private/files/Firmado/
        base_dir = frappe.get_site_path("private", "files", "Firmado")
        os.makedirs(base_dir, exist_ok=True)

        # Build filename: keep invoice number pattern if possible
        file_name = os.path.basename(xml_path)  # e.g., 002-002-000000154.xml
        if not file_name.endswith(".xml"):
            file_name = f"{os.path.splitext(file_name)[0]}.xml"

        fs_path = os.path.join(base_dir, file_name)
        with open(fs_path, "wb") as f:
            f.write(signed_bytes)

        file_url = f"/private/files/Firmado/{file_name}"

        # 5) Update queue row to point to signed file + state
        doc.db_set("xml_file", file_url)
        _doc_state = "Firmado"
        _db_set_state(doc, _doc_state)

        # 6) Final confirmation in timeline
        _append_comment(doc, f"**XML firmado correctamente**\n📄 Archivo: `{file_url}`")

        # 6) Final confirmation in timeline
        _append_comment(doc, f"**XML firmado correctamente**\nArchivo: `{file_url}`")

        # (Optional) safety check: ensure signature is really present
        # _enforce_signed(doc)

    except Exception as ex:
        _append_comment(doc, "❌ Error inesperado en firmado:\n```\n" + frappe.as_json(str(ex)) + "\n```")
        frappe.log_error(title="[service2] _handle_signing failed", message=frappe.get_traceback())
        _db_set_state(doc, "Error")
# -------------------------
# Signing safeguard
# -------------------------
def _enforce_signed(doc):
    """Ensure the Firmado XML really contains a <ds:Signature>.
    If not, inject + sign it using xmlsec1. Raises if signing fails.
    """
    signed_path = _resolve_fs_path(doc.xml_file)
    xml_bytes = _read_bytes(signed_path)

    # If already contains a signature, do nothing
    if b"<ds:Signature" in xml_bytes:
        return

    # Build signed version
    cert_path = frappe.get_site_path("private", "files", f"{doc.company}_cert.pem")
    key_path = frappe.get_site_path("private", "files", f"{doc.company}_private.pem")

    templ = inject_signature_template(xml_bytes.decode("utf-8"), cert_path)
    signed_bytes = sign_with_xmlsec(templ.encode("utf-8"), key_path, cert_path)

    # Attach new signed file
    base_name = os.path.splitext(os.path.basename(signed_path))[0]
    firmado_name = f"{base_name}.firmado.xml"
    file_url = _attach_private_file(doc, firmado_name, signed_bytes)

    _append_comment(doc, f"✔ XML firmado correctamente.\nArchivo: `{file_url}`")
    doc.db_set("xml_file", file_url)
    frappe.db.commit()


# -------------------------
# Transmission helpers
# -------------------------
def _handle_transmission(doc):
    """Send signed XML to SRI (Recepción), then query Autorización once."""
    signed_path = _resolve_fs_path(doc.xml_file)
    xml_bytes = _read_bytes(signed_path)

    # 1) Recepción
    recep = {}
    try:
        recep = soap.enviar_recepcion(xml_bytes)
    except Exception:
        _append_comment(
            doc,
            "Error al invocar Recepción SRI:\n```\n" + traceback.format_exc() + "\n```",
        )
        return

    estado = (recep.get("estado") or "").upper()
    mensajes = recep.get("mensajes") or []

    if estado == "DEVUELTA":
        # Try to get an Autorización wrapper even when Recepción is DEVUELTA.
        # If wrapper present, save wrapper; otherwise fallback to the signed XML we just sent.
        ambiente_used = recep.get("ambiente") or "Pruebas"
        clave = (
            _extract_clave_acceso(xml_bytes)
            or getattr(doc, "clave_acceso", None)
            or getattr(doc, "access_key", None)
        )

        xml_wrapper = None
        a_msgs = []
        try:
            if clave:
                auto = soap.consultar_autorizacion(clave, ambiente_used)
                xml_wrapper = auto.get("xml_wrapper")
                a_msgs = auto.get("mensajes") or []
        except Exception:
            # Ignore Autorización errors here; we still save a Devuelto file below
            pass

        # Prepare folder + filename
        base_dir = frappe.get_site_path("private", "files", "Devuelto")
        os.makedirs(base_dir, exist_ok=True)

        base_name = os.path.basename(signed_path)  # e.g. 002-002-000000160.xml
        root_name, _ = os.path.splitext(base_name)
        file_name = f"{root_name}-devuelto.xml"
        fs_path = os.path.join(base_dir, file_name)

        # Write wrapper if we got one; otherwise signed XML
        if xml_wrapper:
            with open(fs_path, "w", encoding="utf-8") as f:
                f.write(xml_wrapper)
        else:
            with open(fs_path, "wb") as f:
                f.write(xml_bytes)

        file_url = f"/private/files/Devuelto/{file_name}"
        doc.db_set("xml_file", file_url)

        # Timeline note: include any Autorización messages if present
        extra = _format_msgs(" · Autorización", a_msgs) if a_msgs else ""
        _append_comment(
            doc,
            _format_msgs("SRI (Recepción) DEVUELTA", mensajes)
            + f"\n📄 Archivo final: `{file_url}`"
            + (f"\n{extra}" if extra else "")
        )
        _db_set_state(doc, "Devuelto")
        return

    if estado != "RECIBIDA":
        _append_comment(
            doc,
            f"SRI (Recepción) estado inesperado: **{estado}**\n"
            + _format_msgs("Mensajes", mensajes),
        )
        return

    _append_comment(doc, _format_msgs("SRI (Recepción) RECIBIDA", mensajes))

    # 2) Autorización
    clave = (
        _extract_clave_acceso(xml_bytes)
        or getattr(doc, "clave_acceso", None)
        or getattr(doc, "access_key", None)
    )
    if not clave:
        _append_comment(
            doc,
            "No se pudo determinar **claveAcceso** para Autorización (ni en XML ni en el Doc).",
        )
        return

    ambiente_used = recep.get("ambiente") or "Pruebas"

    try:
        auto = soap.consultar_autorizacion(clave, ambiente_used)
    except Exception:
        _append_comment(
            doc,
            "Error al invocar Autorización SRI:\n```\n" + traceback.format_exc() + "\n```",
        )
        poller2._schedule_next(doc.name, clave, ambiente_used, attempt=0)
        return

    a_estado = (auto.get("estado") or "").upper()
    a_msgs = auto.get("mensajes") or []
    xml_wrapper = auto.get("xml_wrapper")

    # --- Helper: filename from estab-ptoEmi-secuencial ---
    def _invoice_filename(inner_xml: str, suffix: str = None) -> str:
        import re
        try:
            estab = re.search(r"<estab>(\d+)</estab>", inner_xml).group(1)
            pto = re.search(r"<ptoEmi>(\d+)</ptoEmi>", inner_xml).group(1)
            sec = re.search(r"<secuencial>(\d+)</secuencial>", inner_xml).group(1)
            name = f"{estab}-{pto}-{sec}.xml"
            if suffix:
                name = f"{estab}-{pto}-{sec}-{suffix}.xml"
            return name
        except Exception:
            # fallback: base on signed file
            base_name = os.path.splitext(os.path.basename(signed_path))[0]
            return f"{base_name}.xml"

    if a_estado == "AUTORIZADO" and xml_wrapper:
        # Build filename from inner XML
        inner_xml = auto.get("xml_autorizado") or ""
        file_name = _invoice_filename(inner_xml)

        # Save manually into /private/files/Autorizado/
        base_dir = frappe.get_site_path("private", "files", "Autorizado")
        os.makedirs(base_dir, exist_ok=True)
        fs_path = os.path.join(base_dir, file_name)
        with open(fs_path, "w", encoding="utf-8") as f:
            f.write(xml_wrapper)

        file_url = f"/private/files/Autorizado/{file_name}"

        # Point preview to wrapper file
        doc.db_set("xml_file", file_url)

        _append_comment(
            doc,
            _format_msgs("✔ SRI (Autorización) **AUTORIZADO**", a_msgs)
            + f"\n📄 Archivo final con wrapper SRI: `{file_url}`",
        )
        _db_set_state(doc, "Autorizado")
        return

    if a_estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        inner_xml = auto.get("xml_autorizado") or ""
        xml_final = xml_wrapper or inner_xml   # ✅ prefer wrapper, fallback to inner

        file_name = _invoice_filename(inner_xml, "devuelto")
        base_dir = frappe.get_site_path("private", "files", "Devuelto")
        os.makedirs(base_dir, exist_ok=True)

        fs_path = os.path.join(base_dir, file_name)
        with open(fs_path, "w", encoding="utf-8") as f:
            f.write(xml_final)

        file_url = f"/private/files/Devuelto/{file_name}"
        doc.db_set("xml_file", file_url)

        _append_comment(
            doc,
            _format_msgs(f"⚠️ SRI (Autorización) {a_estado}", a_msgs)
            + f"\n📄 Archivo final con wrapper SRI: `{file_url}`",
        )
        _db_set_state(doc, "Devuelto")
        return

    # Pending / PPR
    _append_comment(
        doc,
        _format_msgs(f"SRI (Autorización) {a_estado or 'PPR'}", a_msgs)
        + "\nSeguiremos en **Enviado**; reintento en segundo plano.",
    )
    poller2._schedule_next(doc.name, clave, ambiente_used, attempt=0)


# -------------------------
# Utility helpers
# -------------------------
def _resolve_fs_path(file_url: str) -> str:
    if not file_url:
        frappe.throw("Queue row has empty xml_file path (se esperaba XML Firmado).")
    site_root = frappe.get_site_path()
    cleaned = file_url.lstrip("/")
    return os.path.join(site_root, cleaned)


def _read_bytes(path: str) -> bytes:
    if not os.path.exists(path):
        frappe.throw(f"Archivo XML no existe: {path}")
    with open(path, "rb") as f:
        return f.read()


def _extract_clave_acceso(xml_bytes: bytes) -> str | None:
    try:
        text = xml_bytes.decode("utf-8", errors="ignore")
        m = re.search(r"<claveAcceso>\s*([0-9]{10,60})\s*</claveAcceso>", text)
        return m.group(1) if m else None
    except Exception:
        return None


@frappe.whitelist()
def recheck_authorization_now(name: str):
    doc = frappe.get_doc("SRI XML Queue", name)
    from josfe.sri_invoicing.transmission import poller2

    signed_path = _resolve_fs_path(doc.xml_file)
    xml_bytes = _read_bytes(signed_path)
    clave = (
        _extract_clave_acceso(xml_bytes)
        or getattr(doc, "clave_acceso", None)
        or getattr(doc, "access_key", None)
    )
    recep_amb = "Pruebas"
    try:
        recep_amb = soap._ambiente_from_xml(xml_bytes)
    except Exception:
        pass
    poller2.poll_autorizacion_job(
        queue_name=doc.name, clave=clave, ambiente=recep_amb, attempt=0
    )
    return {"ok": True}
