# apps/josfe/josfe/sri_invoicing/firma_combined.py
import os
import base64
import frappe
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
from datetime import datetime

@frappe.whitelist()
def convertir_y_validar_seguro(cred_name=None, enc_password=None):
    if not cred_name:
        frappe.throw("❌ Falta el nombre del documento.")
    if not enc_password:
        frappe.throw("❌ Falta la contraseña encriptada.")

    doc = frappe.get_doc("Credenciales SRI", cred_name)

    # --- Step 1: Decode password from base64 ---
    try:
        password = base64.b64decode(enc_password).decode()
    except Exception:
        frappe.throw("❌ No se pudo decodificar la contraseña enviada.")

    # --- Step 2: Locate the .p12 file ---
    if not doc.jos_firma_electronica:
        frappe.throw("❌ No se ha cargado el archivo de la firma electrónica.")
    p12_path = frappe.get_site_path("private", "files", os.path.basename(doc.jos_firma_electronica))
    if not os.path.exists(p12_path):
        frappe.throw(f"❌ No se encontró el archivo: {p12_path}")

    with open(p12_path, "rb") as f:
        p12_data = f.read()

    # --- Step 3: Load certificate ---
    try:
        private_key, certificate, add_certs = pkcs12.load_key_and_certificates(
            p12_data, password.encode(), backend=default_backend()
        )

    except Exception as e:
        frappe.throw(f"❌ Error abriendo el .p12: {e}")

    # --- Step 4: Extract RUC & Expiration ---
    estado_certificado = "Válido"
    ruc_value = "DESCONOCIDO"
    try:
        # Step 4.1: Try subject OID 2.5.4.5 first
        for attr in certificate.subject:
            if attr.oid.dotted_string == "2.5.4.5":
                ruc_value = attr.value.strip()
                break

        # Step 4.2: Override if extension 1.3.6.1.4.1.37746.3.11 exists
        from cryptography.x509.oid import ObjectIdentifier
        for ext in certificate.extensions:
            if ext.oid == ObjectIdentifier("1.3.6.1.4.1.37746.3.11"):
                val = ext.value.value  # Raw value
                try:
                    decoded = val.decode("utf-8").strip()
                    if decoded.isdigit():
                        ruc_value = decoded
                except Exception:
                    pass
                break

        # Step 4.3: Extract expiration date
        fecha_expiracion = certificate.not_valid_after
        fecha_exp_str = fecha_expiracion.strftime("%Y-%m-%d %H:%M:%S")

        # Step 4.4: Expiration state
        if fecha_expiracion < datetime.utcnow():
            estado_certificado = "Expirado"

    except Exception as e:
        ruc_value = "DESCONOCIDO"
        fecha_exp_str = "DESCONOCIDA"
        estado_certificado = f"Error: {e}"

    # --- Step 5: Export & encrypt PEM ---
    pem_key = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=BestAvailableEncryption(password.encode())
    )
    pem_cert = certificate.public_bytes(serialization.Encoding.PEM)
    pem_cas = b"".join(c.public_bytes(serialization.Encoding.PEM) for c in (add_certs or []))
    pem_data = pem_key + pem_cert + pem_cas

    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_pem = fernet.encrypt(pem_data)

    pem_path = frappe.get_site_path("private", "files", f"{doc.name}_cert.pem.enc")
    key_path = frappe.get_site_path("private", "files", f"{doc.name}_pem.key")

    with open(pem_path, "wb") as f:
        f.write(encrypted_pem)
    with open(key_path, "wb") as f:
        f.write(key)

    # --- Step 6: Update only the validation log ---
    log_text = (
        f"<b>Fecha de Expiración:</b> {fecha_exp_str}\n"
        f"<b>RUC del Certificado:</b> {ruc_value}\n"
        f"<b>Estado del Certificado:</b> {estado_certificado}"
    )
    doc.jos_validacion_log = log_text
    doc.save(ignore_permissions=True)

    # --- Step 7: Cleanup sensitive vars ---
    del password, pem_data, encrypted_pem, key

    return {"msg": "✅ Certificado convertido y almacenado de forma segura."}
