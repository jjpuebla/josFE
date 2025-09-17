# apps/josfe/josfe/sri_invoicing/transmission/submitters.py

import base64
import frappe
from zeep import Client, Settings
from .endpoints import resolve_wsdl, get_test_xml_b64

@frappe.whitelist()
def transmitir_dummy(cred_name: str):
    """Transmite un XML dummy con WSDL fijo (cambiar manualmente a real)."""

    # 1. Leer XML dummy
    try:
        test_xml_path = frappe.get_app_path("josfe", "private", "files", "dummyxml", "generado.xml")
        with open(test_xml_path, "rb") as f:
            xml_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return {"status": "error", "msg": f"No se pudo leer XML dummy: {e}"}

    # 2. WSDL URL (fake por ahora, cámbialo a real manualmente cuando quieras)
    # wsdl_url = "http://127.0.0.1:9999/fake?wsdl"
    wsdl_url = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
    
    # 3. Intentar conectar
    try:
        settings = Settings(strict=True, xml_huge_tree=True)
        client = Client(wsdl=wsdl_url, settings=settings)
        sri_response = client.service.validarComprobante(xml_b64)
    except Exception as e:
        # ✅ keep title short, details in message
        return {"status": "error", "msg": f"Error al conectar a SRI: {e}"}

    # 4. Procesar respuesta
    estado = getattr(sri_response, "estado", "SIN_ESTADO")
    return {"status": "success", "estado": estado}
        
@frappe.whitelist()
def transmitir_xml(cred_name: str):
    """Envía un XML (base64) a la Recepción del SRI usando SRI Endpoint por ambiente."""
    doc = frappe.get_doc("Credenciales SRI", cred_name)

    # Asegura que la credencial ya generó PEM (tu lógica actual de prechequeo)
    if not getattr(doc, "jos_pem_file", None):
        return {"status": "error", "msg": "Primero convierta/valide para generar el PEM (jos_pem_file)."}

    # Determinar ambiente y empresa (según tu modelo)
    ambiente = (doc.jos_ambiente or "Pruebas").capitalize()  # "Pruebas" / "Producción"
    company = getattr(doc, "company", None)

    # Resolver WSDL desde el nuevo Doctype
    wsdl_url = resolve_wsdl("Recepción", ambiente, company)
    if not wsdl_url:
        return {"status": "error", "msg": f"No hay endpoint configurado para Recepción / {ambiente}."}

    # Conseguir XML de prueba: desde el endpoint (attach) o fallback a tu archivo antiguo
    xml_b64 = get_test_xml_b64("Recepción", ambiente, company)
    if not xml_b64:
        # Fallback: tu ruta anterior empaquetada en la app
        try:
            test_xml_path = frappe.get_app_path("josfe", "private", "xml_test", "000099712.xml")
            with open(test_xml_path, "rb") as f:
                xml_b64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            return {"status": "error", "msg": f"No se pudo leer el XML de prueba: {e}"}

    # Llamar al servicio
    try:
        client = Client(wsdl=wsdl_url)
        sri_response = client.service.validarComprobante(xml_b64)
    except Exception as e:
        return {"status": "error", "msg": f"Error al conectar a SRI: {e}"}

    # Parsear respuesta (idéntico a tu versión actual)
    estado = getattr(sri_response, "estado", "SIN_ESTADO")
    mensajes = []
    try:
        comp = sri_response.comprobantes.comprobante[0]
        if hasattr(comp, "mensajes") and comp.mensajes and comp.mensajes.mensaje:
            for m in comp.mensajes.mensaje:
                mensajes.append(getattr(m, "informacionAdicional", None) or getattr(m, "mensaje", ""))
    except Exception:
        pass

    # Marcar último test en el endpoint opcionalmente (no rompe si no existe permiso)
    try:
        ep_name = frappe.get_all("SRI Endpoint",
                                 filters={"service": "Recepción", "ambiente": ambiente, "active": 1},
                                 fields=["name"], limit=1)
        if ep_name:
            frappe.db.set_value("SRI Endpoint", ep_name[0]["name"], {
                "last_tested": frappe.utils.now_datetime(),
                "last_status": estado
            })
    except Exception:
        pass

    return {"status": "success", "estado": estado, "mensajes": mensajes}

