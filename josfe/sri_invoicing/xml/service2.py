# -*- coding: utf-8 -*-
# josfe.sri_invoicing.xml.service2
#
# Sandbox version of service.py — only for Transmission + Authorization testing.
# Does not override the main workflow. Call from bench console:
#
#   import frappe
#   from josfe.sri_invoicing.xml import service2
#   doc = frappe.get_doc("SRI XML Queue", "<queue_name>")
#   service2._process_transmission2(doc, "Enviado")

import os, shutil
import frappe
from pathlib import Path
from xml.etree import ElementTree as ET

from josfe.sri_invoicing.doctype.sri_xml_queue.sri_xml_queue import SRIQueueState
from josfe.sri_invoicing.transmission.soap import enviar_recepcion, consultar_autorizacion

PRIVATE_PREFIX = "/private/files/"
RECEPCION_DIR = "Recepcion"
AUTORIZADO_DIR = "Autorizado"

# --- Helpers ------------------------------------------------------------

def _site_files_path(*parts) -> str:
    return os.path.join(frappe.get_site_path("private", "files"), *parts)

def _read_disk_xml(absolute_path: str) -> bytes:
    with open(absolute_path, "rb") as f:
        return f.read()

def _save_disk_xml(stage_folder: str, base_name: str, suffix: str, xml_text: str) -> str:
    """Save xml_text under /private/files/<stage>/<file>.<suffix>.xml and return relative path."""
    folder = _site_files_path(stage_folder)
    os.makedirs(folder, exist_ok=True)
    fname = f"{Path(base_name).stem}.{suffix}.xml"
    full = os.path.join(folder, fname)
    with open(full, "w", encoding="utf-8") as f:
        f.write(xml_text or "")
    return PRIVATE_PREFIX + f"{stage_folder}/{fname}"

def _extract_clave_acceso(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
        ca = root.find(".//infoTributaria/claveAcceso")
        return ca.text.strip() if ca is not None and ca.text else None
    except Exception:
        return None

def _detect_ambiente(doc) -> str:
    """Try to detect ambiente from Credenciales SRI or fallback to 'Pruebas'."""
    try:
        amb = frappe.db.get_value(
            "Credenciales SRI",
            {"company": doc.company, "jos_activo": 1},
            "jos_ambiente"
        )
        if amb:
            return amb
    except Exception:
        pass
    return "Pruebas"

# --- Core ---------------------------------------------------------------

def _process_transmission2(doc, target_state: str):
    """
    Sandbox transmission: call Recepción / Autorización and persist responses.
    Use ONLY for testing; does not replace service.py.
    """
    if not doc.xml_file:
        frappe.throw("No xml_file on this queue row")

    base_rel = doc.xml_file.replace(PRIVATE_PREFIX, "", 1)
    xml_abs = _site_files_path(base_rel)
    if not os.path.exists(xml_abs):
        frappe.throw(f"XML file not found: {doc.xml_file}")

    ambiente = _detect_ambiente(doc)

    if target_state == SRIQueueState.Enviado.value:
        _test_recepcion(doc, xml_abs, ambiente)

    elif target_state == SRIQueueState.Autorizado.value:
        _test_autorizacion(doc, xml_abs, ambiente)

    else:
        frappe.throw(f"Unsupported target_state {target_state}")

def _test_recepcion(doc, xml_abs: str, ambiente: str):
    xml_bytes = _read_disk_xml(xml_abs)
    rec = enviar_recepcion(xml_bytes, ambiente=ambiente)

    # Save raw SOAP
    doc.recepcion_xml_file = _save_disk_xml(RECEPCION_DIR, os.path.basename(xml_abs), "recepcion", rec.get("raw_xml", ""))

    doc.recepcion_estado = rec.get("estado")
    doc.recepcion_mensajes_json = frappe.as_json(rec.get("mensajes") or [])

    frappe.log_error(f"Recepcion result for {doc.name}", str(rec))

    if rec.get("estado") == "RECIBIDA":
        doc.state = SRIQueueState.Enviado.value
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Doc {doc.name} → RECIBIDA, state=Enviado")
    else:
        doc.state = SRIQueueState.Devuelto.value
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Doc {doc.name} → {doc.recepcion_estado}, state=Devuelto")

def _test_autorizacion(doc, xml_abs: str, ambiente: str):
    xml_text = _read_disk_xml(xml_abs).decode("utf-8", errors="ignore")
    clave = getattr(doc, "clave_acceso", None) or _extract_clave_acceso(xml_text)
    if not clave:
        frappe.throw("Clave de acceso not found")

    au = consultar_autorizacion(clave, ambiente=ambiente)

    doc.autorizacion_xml_file = _save_disk_xml(AUTORIZADO_DIR, os.path.basename(xml_abs), "autorizacion", au.get("raw_xml", ""))
    frappe.log_error(f"Autorizacion result for {doc.name}", str(au))

    estado = au.get("estado")
    if estado == "AUTORIZADO":
        doc.sri_authorization = au.get("numero")
        doc.sri_authorized_at = au.get("fecha")
        # Save authorized comprobante if returned
        comp_xml = au.get("xml_autorizado") or ""
        if comp_xml:
            doc.xml_file = _save_disk_xml(AUTORIZADO_DIR, os.path.basename(xml_abs), "comprobante", comp_xml)
        doc.state = SRIQueueState.Autorizado.value
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Doc {doc.name} AUTORIZADO")
    elif estado == "NO AUTORIZADO":
        doc.state = SRIQueueState.Devuelto.value
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Doc {doc.name} NO AUTORIZADO")
    else:
        # PPR or undefined
        doc.state = SRIQueueState.Enviado.value
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.msgprint(f"Doc {doc.name} remains ENVIADO (estado={estado})")

# --- Convenience API ----------------------------------------------------

@frappe.whitelist()
def force_transmit(name: str, target_state: str):
    """
    Manual trigger from JS / API for testing.
    Example:
        frappe.call("josfe.sri_invoicing.xml.service2.force_transmit", {
            "name": "002-002-000000123",
            "target_state": "Enviado"
        })
    """
    doc = frappe.get_doc("SRI XML Queue", name)
    _process_transmission2(doc, target_state)
    return {"ok": True, "state": doc.state}
