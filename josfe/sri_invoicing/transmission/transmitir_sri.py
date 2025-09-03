import frappe
from pathlib import Path
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from zeep import Client
import base64

@frappe.whitelist(allow_guest=False)
def transmitir_xml(company_name):
    company = frappe.get_doc("Company", company_name)

    # 1. Ruta del archivo .pem exportado (ya convertido previamente desde .p12)
    file_path = frappe.get_site_path(company.custom_jos_firma_electronica.strip('/'))

    # 2. Leer el contenido del .pem (opcional para futura firma real del XML)
    try:
        with open(file_path, "rb") as f:
            pem_data = f.read()
    except Exception as e:
        return {"status": "error", "msg": f"No se pudo leer el archivo PEM: {e}"}

    # 3. Leer XML de prueba
    try:
        test_xml_path = frappe.get_app_path("josfe", "private", "xml_test", "000099712.xml")
        with open(test_xml_path, "rb") as f:
            xml_data = f.read()
    except Exception as e:
        return {"status": "error", "msg": f"No se pudo leer el XML: {e}"}

    # 4. Convertir el XML a base64
    xml_b64 = base64.b64encode(xml_data).decode()

    # 5. Enviar a Recepción SRI (ambiente de pruebas)
    try:
        wsdl_url = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
        client = Client(wsdl=wsdl_url)
        sri_response = client.service.validarComprobante(xml_b64)
    except Exception as e:
        return {"status": "error", "msg": f"Error al conectar a SRI: {e}"}

    estado = sri_response.estado
    mensajes = sri_response.comprobantes.comprobante[0].mensajes.mensaje if sri_response.comprobantes else []

    return {
        "status": "success",
        "estado": estado,
        "mensajes": [m.informacionAdicional if hasattr(m, 'informacionAdicional') else m.mensaje for m in mensajes]
    }
