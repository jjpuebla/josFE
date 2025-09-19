# apps/josfe/josfe/sri_invoicing/xml/signer.py
import subprocess, tempfile, os
from lxml import etree

def _root_local_name(xml_bytes: bytes) -> str:
    tag = etree.fromstring(xml_bytes).tag
    return tag.split("}", 1)[-1]  # strip ns if present

def sign_with_xmlsec(input_xml: bytes, key_pem_path: str, cert_pem_path: str) -> bytes:
    """
    Sign XML that contains a <ds:Signature> template. Root can be 'factura' or 'notaCredito'.
    """
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "in.xml")
        out_path = os.path.join(td, "out.xml")
        with open(in_path, "wb") as f:
            f.write(input_xml)

        root_name = _root_local_name(input_xml)
        cmd = [
            "xmlsec1", "--sign",
            "--privkey-pem", f"{key_pem_path},{cert_pem_path}",
            "--id-attr:id", root_name,      # reference to #comprobante on the actual root
            "--id-attr:Id", "SignedProperties",
            "--id-attr:Id", "KeyInfo",
            "--output", out_path, in_path,
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError("xmlsec1 failed:\n" + p.stderr.decode("utf-8", "ignore"))

        return open(out_path, "rb").read()
