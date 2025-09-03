# apps/josfe/josfe/sri_invoicing/xml/signer.py
import subprocess, tempfile, os

def sign_with_xmlsec(input_xml: bytes, key_pem_path: str, cert_pem_path: str) -> bytes:
    """
    Sign an XML (that already contains a <ds:Signature> template) with xmlsec1.
    """
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "in.xml")
        out_path = os.path.join(td, "out.xml")
        with open(in_path, "wb") as f:
            f.write(input_xml)

        cmd = [
            "xmlsec1", "--sign",
            "--privkey-pem", f"{key_pem_path},{cert_pem_path}",
            "--id-attr:id", "factura",          # reference to #comprobante
            "--id-attr:Id", "SignedProperties", # reference to SignedProperties element
            "--id-attr:Id", "KeyInfo",          # (optional) explicit if you include it
            "--output", out_path,
            in_path,
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError("xmlsec1 failed:\n" + p.stderr.decode("utf-8", "ignore"))

        return open(out_path, "rb").read()
