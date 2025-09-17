# apps/josfe/josfe/sri_invoicing/transmission/endpoints.py
import frappe

DEFAULTS = {
    ("Recepción", "Pruebas"): "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    ("Recepción", "Producción"): "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    ("Autorización", "Pruebas"): "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    ("Autorización", "Producción"): "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
}

_SERVICE_ALIASES = {
    "recepcion": "Recepción",
    "recepción": "Recepción",
    "autorizacion": "Autorización",
    "autorización": "Autorización",
}

_AMBIENTE_ALIASES = {
    "1": "Pruebas",
    "pruebas": "Pruebas",
    "test": "Pruebas",
    "sandbox": "Pruebas",
    "2": "Producción",
    "produccion": "Producción",
    "producción": "Producción",
    "prod": "Producción",
    "production": "Producción",
}

def _norm_service(service: str) -> str:
    if not service:
        return "Recepción"
    key = service.strip().lower()
    return _SERVICE_ALIASES.get(key, service)

def _norm_ambiente(ambiente: str) -> str:
    if not ambiente:
        return "Pruebas"
    key = ambiente.strip().lower()
    return _AMBIENTE_ALIASES.get(key, ambiente.title())

def resolve_wsdl(service: str, ambiente: str) -> str:
    """
    Resolve WSDL URL from SRI Endpoint (active record, by service+ambiente).
    Falls back to DEFAULTS if none configured.
    """
    service = _norm_service(service)
    ambiente = _norm_ambiente(ambiente)

    ep = frappe.get_all(
        "SRI Endpoint",
        filters={"service": service, "ambiente": ambiente, "active": 1},
        fields=["name", "wsdl_url"],
        order_by="modified desc",
        limit=1,
    )
    if ep and ep[0].get("wsdl_url"):
        return ep[0]["wsdl_url"]

    return DEFAULTS.get((service, ambiente))

def get_endpoint_flags(service: str, ambiente: str) -> tuple[bool, int]:
    """
    Returns (verify_ssl, timeout_seconds) from SRI Endpoint if present, else (True, 40).
    """
    service = _norm_service(service)
    ambiente = _norm_ambiente(ambiente)

    ep = frappe.get_all(
        "SRI Endpoint",
        filters={"service": service, "ambiente": ambiente, "active": 1},
        fields=["verify_ssl", "timeout_seconds"],
        limit=1,
    )
    verify_ssl, timeout = True, 40
    if ep:
        verify_ssl = bool(ep[0].get("verify_ssl", 1))
        timeout = int(ep[0].get("timeout_seconds") or timeout)
    return verify_ssl, timeout

def get_test_xml_b64(service: str, ambiente: str) -> str | None:
    """
    Optional helper used by legacy testers to fetch a base64 test XML stored in the Endpoint.
    """
    import base64
    service = _norm_service(service)
    ambiente = _norm_ambiente(ambiente)

    ep = frappe.get_all(
        "SRI Endpoint",
        filters={"service": service, "ambiente": ambiente, "active": 1},
        fields=["name", "test_xml"],
        limit=1,
    )
    if ep and ep[0].get("test_xml"):
        content = frappe.utils.file_manager.get_file(ep[0]["test_xml"])[1]
        return base64.b64encode(content).decode()
    return None
