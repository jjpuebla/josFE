# apps/josfe/josfe/sri_invoicing/signing/pem_tools.py
import os
import base64
import subprocess
import frappe
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import hashlib

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
    ruc_value, fecha_exp_str = "DESCONOCIDO", "DESCONOCIDA"
    try:
        # Subject OID 2.5.4.5
        for attr in certificate.subject:
            if attr.oid.dotted_string == "2.5.4.5":
                ruc_value = attr.value.strip()
        # Extension override
        from cryptography.x509.oid import ObjectIdentifier
        for ext in certificate.extensions:
            if ext.oid == ObjectIdentifier("1.3.6.1.4.1.37746.3.11"):
                try:
                    decoded = ext.value.value.decode("utf-8").strip()
                    if decoded.isdigit():
                        ruc_value = decoded
                except Exception:
                    pass
                break
        # Expiration
        fecha_expiracion = certificate.not_valid_after
        fecha_exp_str = fecha_expiracion.strftime("%Y-%m-%d %H:%M:%S")
        if fecha_expiracion < datetime.utcnow():
            estado_certificado = "Expirado"
    except Exception as e:
        estado_certificado = f"Error: {e}"

    # --- Step 5a: Export encrypted PEM (your original design) ---
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

    # --- Step 5b: Export plain PEMs for signing with xmlsec1 ---
    try:
        priv_pem = frappe.get_site_path("private", "files", f"{doc.name}_private.pem")
        cert_pem = frappe.get_site_path("private", "files", f"{doc.name}_cert.pem")
        # Write private key without encryption (xmlsec1 needs plain PEM)
        with open(priv_pem, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        os.chmod(priv_pem, 0o600)
        # Write certificate + intermediates (full chain for xmlsec1 trust)
        with open(cert_pem, "wb") as f:
            f.write(pem_cert)
            if pem_cas:
                f.write(pem_cas)
        pem_log = f"✔ PEM generados: {os.path.basename(priv_pem)}, {os.path.basename(cert_pem)} (incluye cadena)"
    except Exception as e:
        pem_log = f"❌ Error generando PEM firmables: {e}"

    # --- Step 6: Update validation log ---
    log_text = (
        f"<b>Fecha de Expiración:</b> {fecha_exp_str}\n"
        f"<b>RUC del Certificado:</b> {ruc_value}\n"
        f"<b>Estado del Certificado:</b> {estado_certificado}\n"
        f"{pem_log}"
    )
    doc.jos_validacion_log = log_text
    doc.save(ignore_permissions=True)

    # --- Step 7: Cleanup sensitive vars ---
    del password, pem_data, encrypted_pem, key

    return {"msg": "✅ Certificado validado y PEM disponibles para firma."}

def extract_cert_info(cert_pem_path: str) -> dict:
    """
    Load a PEM certificate and return SHA1 digest, issuer DN, and serial number.
    """
    with open(cert_pem_path, "rb") as f:
        cert_data = f.read()

    cert = x509.load_pem_x509_certificate(cert_data, default_backend())

    # Digest of DER
    der_bytes = cert.public_bytes(serialization.Encoding.DER)
    sha1_digest = hashlib.sha1(der_bytes).digest()
    digest_b64 = base64.b64encode(sha1_digest).decode()

    issuer_name = cert.issuer.rfc4514_string()
    serial_number = str(cert.serial_number)

    return {
        "digest": digest_b64,
        "issuer": issuer_name,
        "serial": serial_number,
    }