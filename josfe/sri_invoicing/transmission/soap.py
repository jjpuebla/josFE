# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/transmission/soap.py

from __future__ import annotations
import base64
import requests
from typing import Dict, Any, Optional
from zeep import Client, Settings, helpers
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport
import frappe
from lxml import etree

from .endpoints import resolve_wsdl

def _zeep_client(service: str, ambiente: str) -> tuple[Client, HistoryPlugin]:
    wsdl = resolve_wsdl(service, ambiente)
    if not wsdl:
        frappe.throw(f"No WSDL configured for {service}/{ambiente}")

    # Pull optional flags from SRI Endpoint if present
    ep = frappe.get_all("SRI Endpoint",
                        filters={"service": service, "ambiente": ambiente, "active": 1},
                        fields=["verify_ssl", "timeout_seconds"], limit=1)
    verify_ssl = True
    timeout = 40
    if ep:
        verify_ssl = bool(ep[0].get("verify_ssl", 1))
        timeout = int(ep[0].get("timeout_seconds") or timeout)

    session = requests.Session()
    session.verify = verify_ssl
    transport = Transport(session=session, timeout=timeout)
    settings = Settings(strict=False, xml_huge_tree=True)
    history = HistoryPlugin()
    client = Client(wsdl=wsdl, transport=transport, settings=settings, plugins=[history])
    return client, history

def enviar_recepcion(xml_bytes: bytes, ambiente: str) -> Dict[str, Any]:
    client, hist = _zeep_client("Recepción", ambiente)
    xml_b64 = base64.b64encode(xml_bytes).decode()
    res = client.service.validarComprobante(xml_b64)  # SOAP op
    data = helpers.serialize_object(res) or {}

    raw_xml = ""
    if hist.last_received and "envelope" in hist.last_received:
        raw_xml = etree.tostring(hist.last_received["envelope"], encoding="utf-8").decode("utf-8")

    # rest of the code...
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
        pass
    return {"estado": estado, "mensajes": mensajes, "raw_xml": raw_xml}

def consultar_autorizacion(clave_acceso: str, ambiente: str) -> Dict[str, Any]:
    client, hist = _zeep_client("Autorización", ambiente)
    res = client.service.autorizacionComprobante(clave_acceso)
    data = helpers.serialize_object(res) or {}
    raw_xml = ""
    if hist.last_received and "envelope" in hist.last_received:
        raw_xml = etree.tostring(hist.last_received["envelope"], encoding="utf-8").decode("utf-8")

    # Usually res.autorizaciones.autorizacion is a list
    auths = (data.get("autorizaciones") or {}).get("autorizacion") or []
    if isinstance(auths, dict):
        auths = [auths]

    if not auths:
        return {"estado": "PPR", "raw_xml": raw_xml}  # En Proceso / no payload yet

    a0 = auths[0]
    estado = (a0.get("estado") or "").upper()
    numero = a0.get("numeroAutorizacion")
    fecha = a0.get("fechaAutorizacion")
    xml_autorizado = a0.get("comprobante")  # string with original XML
    return {
        "estado": estado,
        "numero": numero,
        "fecha": fecha,
        "xml_autorizado": xml_autorizado,
        "raw_xml": raw_xml,
    }
