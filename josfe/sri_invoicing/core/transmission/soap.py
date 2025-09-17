# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/transmission/soap.py

from __future__ import annotations
import base64
from typing import Dict, Any, Optional, Tuple, List
import requests
from zeep import Client, Settings, helpers
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport
from lxml import etree
import frappe

from .endpoints import resolve_wsdl, get_endpoint_flags

def _ambiente_from_xml(xml_bytes: bytes) -> str:
    """
    Derive ambiente from the XML payload (infoTributaria/ambiente).
    SRI spec: 1=Pruebas, 2=Producción. Default to Pruebas.
    """
    try:
        root = etree.fromstring(xml_bytes)
        vals: List[str] = root.xpath('//*[local-name()="ambiente"]/text()')
        if vals:
            v = (vals[0] or "").strip()
            if v == "2" or v.lower().startswith("prod"):
                return "Producción"
            return "Pruebas"
    except Exception:
        pass
    # Fallback: naive scan
    try:
        text = xml_bytes.decode("utf-8", errors="ignore").lower()
        if ">2<" in text or "producción" in text or "produccion" in text:
            return "Producción"
    except Exception:
        pass
    return "Pruebas"

def _zeep_client(service: str, ambiente: str) -> Tuple[Client, HistoryPlugin]:
    wsdl = resolve_wsdl(service, ambiente)
    if not wsdl:
        raise RuntimeError(f"No WSDL configured for service={service}, ambiente={ambiente}")

    verify_ssl, timeout = get_endpoint_flags(service, ambiente)
    session = requests.Session()
    session.verify = verify_ssl
    transport = Transport(session=session, timeout=timeout)
    settings = Settings(strict=False, xml_huge_tree=True)

    history = HistoryPlugin()
    client = Client(wsdl=wsdl, transport=transport, settings=settings, plugins=[history])
    return client, history

def enviar_recepcion(xml_bytes: bytes, ambiente: Optional[str] = None) -> Dict[str, Any]:
    """
    Send XML to SRI Recepción. If ambiente not provided, it is inferred from the XML.
    Returns dict: {estado, mensajes, raw_xml, ambiente, xml_wrapper?}
    """
    amb = ambiente or _ambiente_from_xml(xml_bytes)
    client, hist = _zeep_client("Recepción", amb)

    xml_b64 = base64.b64encode(xml_bytes).decode()
    try:
        res = client.service.validarComprobante(xml_b64)
        data = helpers.serialize_object(res) or {}
    except Exception as e:
        return {"estado": "ERROR", "mensajes": [f"Error de conexión/Zeep: {e!r}"], "raw_xml": "", "ambiente": amb}

    raw_xml = ""
    if hist.last_received and "envelope" in hist.last_received:
        raw_xml = etree.tostring(hist.last_received["envelope"], encoding="utf-8").decode("utf-8")

    estado = (data.get("estado") or "").upper()
    mensajes = []
    try:
        comps = (data.get("comprobantes") or {}).get("comprobante") or []
        if isinstance(comps, dict):
            comps = [comps]
        for c in comps:
            mm = (c.get("mensajes") or {}).get("mensaje") or []
            if isinstance(mm, dict):
                mm = [mm]
            for m in mm:
                mensajes.append({
                    "identificador": m.get("identificador"),
                    "mensaje": m.get("mensaje"),
                    "informacionAdicional": m.get("informacionAdicional"),
                    "tipo": m.get("tipo"),
                })
    except Exception:
        # best-effort only
        pass

    # Mark DEVUELTO origin for Recepción and build a compact wrapper for storage (optional)
    xml_wrapper = ""
    if estado in ("DEVUELTA", "RECHAZADO"):
        frappe.flags.sri_devuelto_origin = "Recepción"
        xml_wrapper = _build_recepcion_wrapper(estado, mensajes, raw_xml, amb)

    return {"estado": estado, "mensajes": mensajes, "raw_xml": raw_xml, "ambiente": amb, "xml_wrapper": xml_wrapper}

def consultar_autorizacion(clave_acceso: str, ambiente: str) -> Dict[str, Any]:
    client, hist = _zeep_client("Autorización", ambiente)
    try:
        res = client.service.autorizacionComprobante(clave_acceso)
        data = helpers.serialize_object(res) or {}
    except Exception as e:
        return {"estado": "ERROR", "mensajes": [f"Error de conexión/Zeep: {e!r}"], "raw_xml": ""}

    raw_xml = ""
    if hist.last_received and "envelope" in hist.last_received:
        raw_xml = etree.tostring(hist.last_received["envelope"], encoding="utf-8").decode("utf-8")

    auths = ((data.get("autorizaciones") or {}).get("autorizacion") or [])
    if isinstance(auths, dict):
        auths = [auths]
    if not auths:
        return {"estado": "PPR", "raw_xml": raw_xml}  # processing

    a0 = auths[0]
    estado = (a0.get("estado") or "").upper()
    numero = a0.get("numeroAutorizacion")
    fecha = a0.get("fechaAutorizacion")
    xml_inner = a0.get("comprobante")  # original XML as string
    xml_wrapper = _build_autorizacion_wrapper(a0)

    # If NAT/DEVUELTA, tag origin=Autorización so the mover routes to NO_AUTORIZADOS
    if estado in {"NO AUTORIZADO", "RECHAZADO", "DEVUELTA"}:
        frappe.flags.sri_devuelto_origin = "Autorización"

    out = {
        "estado": estado,
        "numero": numero,
        "fecha": fecha,
        "xml_autorizado": xml_inner,
        "xml_wrapper": xml_wrapper,
        "raw_xml": raw_xml,
    }

    # keep mensajes
    try:
        mm = (a0.get("mensajes") or {}).get("mensaje") or []
        if isinstance(mm, dict):
            mm = [mm]
        out["mensajes"] = [{
            "identificador": m.get("identificador"),
            "mensaje": m.get("mensaje"),
            "informacionAdicional": m.get("informacionAdicional"),
            "tipo": m.get("tipo"),
        } for m in mm]
    except Exception:
        pass

    return out

def _build_recepcion_wrapper(estado: str, mensajes: List[dict], raw_xml: str, ambiente: str) -> str:
    """Compact wrapper for Recepción DEVUELTA/RECHAZADO responses."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<respuestaRecepcion>',
        f'  <estado>{(estado or "").upper()}</estado>',
        f'  <ambiente>{ambiente or ""}</ambiente>',
    ]
    if mensajes:
        parts.append('  <mensajes>')
        for m in mensajes:
            parts.append('    <mensaje>')
            if m.get("identificador"):       parts.append(f'      <identificador>{m["identificador"]}</identificador>')
            if m.get("mensaje"):             parts.append(f'      <mensaje>{m["mensaje"]}</mensaje>')
            if m.get("informacionAdicional"):parts.append(f'      <informacionAdicional>{m["informacionAdicional"]}</informacionAdicional>')
            if m.get("tipo"):                parts.append(f'      <tipo>{m["tipo"]}</tipo>')
            parts.append('    </mensaje>')
        parts.append('  </mensajes>')
    if raw_xml:
        parts.append('  <sobre><![CDATA[' + raw_xml + ']]></sobre>')
    parts.append('</respuestaRecepcion>')
    return "\n".join(parts)

def _build_autorizacion_wrapper(a0: dict) -> str:
    """
    Build a compact <autorizacion> XML wrapper, embedding the original comprobante in CDATA.
    a0 is the first item in 'autorizaciones/autorizacion' from SRI.
    """
    import datetime

    def _fmt(value):
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        if value is None:
            return ""
        return str(value).strip()

    estado = _fmt(a0.get("estado")).upper()
    numero = _fmt(a0.get("numeroAutorizacion"))
    fecha  = _fmt(a0.get("fechaAutorizacion"))
    ambiente = _fmt(a0.get("ambiente"))
    inner = _fmt(a0.get("comprobante"))

    # mensajes (present on NAT/DEVUELTO or warnings)
    mensajes = []
    mm = (a0.get("mensajes") or {}).get("mensaje") or []
    if isinstance(mm, dict):
        mm = [mm]
    for m in mm:
        mensajes.append({
            "identificador": _fmt(m.get("identificador")),
            "mensaje": _fmt(m.get("mensaje")),
            "informacionAdicional": _fmt(m.get("informacionAdicional")),
            "tipo": _fmt(m.get("tipo")),
        })

    # Compose wrapper
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<autorizacion>',
        f'  <estado>{estado}</estado>',
        f'  <numeroAutorizacion>{numero}</numeroAutorizacion>',
        f'  <fechaAutorizacion>{fecha}</fechaAutorizacion>',
    ]
    if ambiente:
        parts.append(f'  <ambiente>{ambiente}</ambiente>')
    parts.append('  <comprobante><![CDATA[' + inner + ']]></comprobante>')

    if mensajes:
        parts.append('  <mensajes>')
        for m in mensajes:
            parts.append('    <mensaje>')
            if m["identificador"]:
                parts.append(f'      <identificador>{m["identificador"]}</identificador>')
            if m["mensaje"]:
                parts.append(f'      <mensaje>{m["mensaje"]}</mensaje>')
            if m["informacionAdicional"]:
                parts.append(f'      <informacionAdicional>{m["informacionAdicional"]}</informacionAdicional>')
            if m["tipo"]:
                parts.append(f'      <tipo>{m["tipo"]}</tipo>')
            parts.append('    </mensaje>')
        parts.append('  </mensajes>')

    parts.append('</autorizacion>')
    return "\n".join(parts)
