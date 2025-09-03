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
    Returns dict: {estado, mensajes, raw_xml, ambiente}
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

    return {"estado": estado, "mensajes": mensajes, "raw_xml": raw_xml, "ambiente": amb}

def consultar_autorizacion(clave_acceso: str, ambiente: str) -> Dict[str, Any]:
    """
    Query SRI Autorización for the given access key and ambiente.
    Returns dict: {estado, numero, fecha, xml_autorizado, raw_xml}
    """
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
        return {"estado": "PPR", "raw_xml": raw_xml}  # En Proceso / no payload yet

    a0 = auths[0]
    estado = (a0.get("estado") or "").upper()
    numero = a0.get("numeroAutorizacion")
    fecha = a0.get("fechaAutorizacion")
    xml_autorizado = a0.get("comprobante")  # original XML as string

    out = {
        "estado": estado,
        "numero": numero,
        "fecha": fecha,
        "xml_autorizado": xml_autorizado,
        "raw_xml": raw_xml,
    }
    # Attach mensajes if present (consistent shape with Recepción)
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
