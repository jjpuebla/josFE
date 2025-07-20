import os
import frappe
import subprocess
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from pathlib import Path

@frappe.whitelist()
def convertir_y_validar(company_name, p12_password):
    company = frappe.get_doc("Company", company_name)
    if not company.custom_jos_firma_electronica:
        return {"status": "error", "msg": "No se ha subido ningún archivo .p12."}

    # Ruta de entrada (.p12)
    p12_filename = company.custom_jos_firma_electronica.rsplit("/", 1)[-1]
    site_path = frappe.get_site_path("private", "files", p12_filename)

    # Ruta de salida (.pem cifrado)
    pem_output_path = frappe.get_site_path("private", "files", "actualpem.pem")

    # Convertir usando openssl con clave de salida
        # ------ Set OpenSSL configuration to legacy. openssl legacy is at: mode apps/josfe/josfe/openssl/openssl_legacy.cnf------ 
    env = os.environ.copy()
    env["OPENSSL_CONF"] = frappe.get_app_path("josfe", "openssl", "openssl_legacy.cnf")
        # ------ Set OpenSSL configuration to legacy mode ------ 

    result = subprocess.run([
        "openssl", "pkcs12",
        "-in", site_path,
        "-out", pem_output_path,
        "-passin", f"pass:{p12_password}",
        "-passout", f"pass:{p12_password}"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        frappe.log_error(result.stderr, "Error OpenSSL PEM cifrado")
        return {"status": "error", "msg": f"Error al convertir .p12: {result.stderr}"}

    try:
        # Leer el certificado
        pem_data = Path(pem_output_path).read_text(encoding='utf-8')
        cert = x509.load_pem_x509_certificate(pem_data.encode())

        # Extraer RUC
        ruc_oid = x509.ObjectIdentifier("1.3.6.1.4.1.37746.3.11")
        try:
            ext = cert.extensions.get_extension_for_oid(ruc_oid)
            raw_ruc = ext.value.value
            ruc = raw_ruc.decode('utf-8').replace('\x0c', '').strip()
        except Exception:
            ruc = "No encontrado"

        # Guardar en campos
        company.custom_jos_ruc_certificado = ruc
        company.custom_jos_fecha_expiracion = cert.not_valid_after.date()
        company.save()

        return {
            "status": "success",
            "msg": "Certificado válido",
            "ruc": ruc,
            "fecha_expiracion": str(cert.not_valid_after.date())
        }

    except Exception as e:
        return {"status": "error", "msg": f"Error al leer certificado: {str(e)}"}
