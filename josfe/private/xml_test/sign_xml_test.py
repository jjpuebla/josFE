from lxml import etree
from signxml import XMLSigner, methods
from cryptography.hazmat.primitives import serialization
import os
import frappe

# --- CONFIGURATION ---
base_path = "/home/erpnext_user/frappe-bench/apps/josfe/josfe/private/xml_test"
pem_path = frappe.get_site_path("private", "files", "claudia5e369f.pem")  # your .PEM
pem_password = b"Pepelit0"  # replace with your actual password
xml_input_path = os.path.join(base_path, "000099712.xml")
xml_output_path = os.path.join(base_path, "000099712_signed.xml")

# --- LOAD CERTIFICATE AND PRIVATE KEY ---
with open(pem_path, "rb") as pem_file:
    pem_data = pem_file.read()

# Load private key
private_key = serialization.load_pem_private_key(pem_data, password=None)

# Extract certificate part
cert_start = pem_data.find(b"-----BEGIN CERTIFICATE-----")
cert_end = pem_data.find(b"-----END CERTIFICATE-----") + len(b"-----END CERTIFICATE-----")
cert_data = pem_data[cert_start:cert_end]

# --- LOAD XML ---
with open(xml_input_path, "rb") as f:
    xml_content = f.read()

# --- SIGN XML ---
root = etree.fromstring(xml_content)
signer = XMLSigner(method=methods.enveloped, digest_algorithm="sha256")
signed_root = signer.sign(root, key=private_key, cert=cert_data)

# --- SAVE SIGNED XML ---
with open(xml_output_path, "wb") as f:
    f.write(etree.tostring(signed_root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

print("✅ XML firmado y guardado como:", xml_output_path)

# to run:
# exec(open('/home/erpnext_user/frappe-bench/apps/josfe/josfe/private/xml_test/sign_xml_test.py').read())
