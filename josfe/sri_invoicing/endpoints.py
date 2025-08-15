# apps/josfe/josfe/sri_invoicing/endpoints.py
import frappe

DEFAULTS = {
    ("Recepción", "Pruebas"): "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    ("Recepción", "Producción"): "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    ("Autorización", "Pruebas"): "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    ("Autorización", "Producción"): "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
}

def resolve_wsdl(service: str, ambiente: str) -> str:
    """
    Return the preferred active WSDL URL from SRI Endpoint, with sane fallbacks.
    Now company-agnostic — any company-specific logic must be handled before calling this.
    """
    filters = {"service": service, "ambiente": ambiente, "active": 1}

    rows = frappe.get_all(
        "SRI Endpoint",
        filters=filters,
        fields=["wsdl_url"],
        order_by="priority asc, modified desc",
        limit=1
    )
    if rows:
        return rows[0]["wsdl_url"]

    return DEFAULTS.get((service, ambiente))  # may be None if not defined

def get_test_xml_b64(service: str, ambiente: str) -> str | None:
    """
    If the endpoint has an attached sample XML, return it Base64-encoded.
    Company-agnostic — any filtering by company should be done before calling this.
    """
    import base64
    filters = {"service": service, "ambiente": ambiente, "active": 1}

    ep = frappe.get_all(
        "SRI Endpoint",
        filters=filters,
        fields=["name", "test_xml"],
        limit=1
    )
    if ep and ep[0].get("test_xml"):
        content = frappe.utils.file_manager.get_file(ep[0]["test_xml"])[1]
        return base64.b64encode(content).decode()

    return None
