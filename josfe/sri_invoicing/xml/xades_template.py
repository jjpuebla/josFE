# apps/josfe/josfe/sri_invoicing/xml/xades_template.py
from __future__ import annotations

import base64
import datetime
import os
import subprocess
import tempfile
import uuid

from lxml import etree
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from josfe.sri_invoicing.xml.utils import format_xml_bytes

DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"
NSMAP = {"ds": DS_NS, "xades": XADES_NS}
DS = "{%s}" % DS_NS
XADES = "{%s}" % XADES_NS


def _ensure_root_has_comprobante_id(root: etree._Element) -> None:
    """
    SRI expects the signed object (factura, notaCredito, etc.) to be referenced as #comprobante.
    Ensure the root carries id="comprobante" if no other element does.
    """
    # If any element already has id="comprobante", keep it.
    if root.get("id") == "comprobante":
        return
    if root.xpath('//*[@id="comprobante"]'):
        return
    # Add it on the root.
    root.set("id", "comprobante")


def _read_cert_bits(cert_pem_path: str) -> tuple[str, str, int, str]:
    """
    Returns (cert_b64_der, issuer_name, serial_number, sha1_digest_b64)
    """
    with open(cert_pem_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())

    # b64 DER for <ds:X509Certificate>
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode("ascii")

    issuer_name = cert.issuer.rfc4514_string()  # e.g. "CN=..., O=..., C=EC"
    serial_number = cert.serial_number

    # SHA1 digest of DER (XAdES SigningCertificate -> CertDigest)
    digest = hashes.Hash(hashes.SHA1())
    digest.update(cert_der)
    sha1_b64 = base64.b64encode(digest.finalize()).decode("ascii")

    return cert_b64, issuer_name, serial_number, sha1_b64


def inject_signature_template(xml_text: str, cert_pem_path: str) -> str:
    """
    Inject a VALID XMLDSig + XAdES-BES template into the document.
    Key points:
      - QualifyingProperties is wrapped inside <ds:Object> (required by xmlsec1)
      - SignedInfo has 3 References: #comprobante (with enveloped + c14n transforms), #SignedProperties (Type attr), #KeyInfo
      - Root carries id="comprobante"
    """
    cert_b64, issuer_name, serial_number, cert_sha1_b64 = _read_cert_bits(cert_pem_path)

    # Parse source
    root = etree.fromstring(xml_text.encode("utf-8"))
    _ensure_root_has_comprobante_id(root)

    # IDs
    sig_id = f"Signature-{uuid.uuid4().int % 1_000_000}"
    signedprops_id = f"SignedProperties-{uuid.uuid4().int % 1_000_000}"
    keyinfo_id = f"KeyInfo-{uuid.uuid4().int % 1_000_000}"
    ref_comprobante_id = f"Reference-Comprobante-{uuid.uuid4().int % 1_000_000}"

    # <ds:Signature>
    signature = etree.Element(DS + "Signature", nsmap=NSMAP, Id=sig_id)

    # <ds:SignedInfo>
    signed_info = etree.SubElement(signature, DS + "SignedInfo", Id=f"SignedInfo-{uuid.uuid4().int % 1_000_000}")
    etree.SubElement(
        signed_info,
        DS + "CanonicalizationMethod",
        Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    etree.SubElement(signed_info, DS + "SignatureMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1")

    # Reference #comprobante (with BOTH transforms)
    ref1 = etree.SubElement(signed_info, DS + "Reference", Id=ref_comprobante_id, URI="#comprobante")
    tr1 = etree.SubElement(ref1, DS + "Transforms")
    etree.SubElement(tr1, DS + "Transform", Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature")
    etree.SubElement(tr1, DS + "Transform", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(ref1, DS + "DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
    etree.SubElement(ref1, DS + "DigestValue")

    # Reference #SignedProperties (Type attribute required by XAdES)
    ref2 = etree.SubElement(
        signed_info,
        DS + "Reference",
        Type="http://uri.etsi.org/01903#SignedProperties",
        URI=f"#{signedprops_id}",
    )
    etree.SubElement(ref2, DS + "DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
    etree.SubElement(ref2, DS + "DigestValue")

    # Reference #KeyInfo
    ref3 = etree.SubElement(signed_info, DS + "Reference", URI=f"#{keyinfo_id}")
    etree.SubElement(ref3, DS + "DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
    etree.SubElement(ref3, DS + "DigestValue")

    # <ds:SignatureValue>
    etree.SubElement(signature, DS + "SignatureValue")

    # <ds:KeyInfo>
    key_info = etree.SubElement(signature, DS + "KeyInfo", Id=keyinfo_id)
    x509data = etree.SubElement(key_info, DS + "X509Data")
    x509cert = etree.SubElement(x509data, DS + "X509Certificate")
    x509cert.text = cert_b64

    # <ds:Object><xades:QualifyingProperties> ... </xades:QualifyingProperties></ds:Object>
    ds_object = etree.SubElement(signature, DS + "Object")
    qp = etree.SubElement(ds_object, XADES + "QualifyingProperties", Target="#" + sig_id)
    sp = etree.SubElement(qp, XADES + "SignedProperties", Id=signedprops_id)

    # SignedSignatureProperties
    ssp = etree.SubElement(sp, XADES + "SignedSignatureProperties")
    etree.SubElement(ssp, XADES + "SigningTime").text = (
        datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    )
    sc = etree.SubElement(ssp, XADES + "SigningCertificate")
    cert_node = etree.SubElement(sc, XADES + "Cert")
    cert_digest = etree.SubElement(cert_node, XADES + "CertDigest")
    etree.SubElement(cert_digest, DS + "DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
    etree.SubElement(cert_digest, DS + "DigestValue").text = cert_sha1_b64
    issuer_serial = etree.SubElement(cert_node, XADES + "IssuerSerial")
    etree.SubElement(issuer_serial, DS + "X509IssuerName").text = issuer_name
    etree.SubElement(issuer_serial, DS + "X509SerialNumber").text = str(serial_number)

    # SignedDataObjectProperties
    sdop = etree.SubElement(sp, XADES + "SignedDataObjectProperties")
    dof = etree.SubElement(sdop, XADES + "DataObjectFormat", ObjectReference=f"#{ref_comprobante_id}")
    etree.SubElement(dof, XADES + "Description").text = "contenido comprobante"
    etree.SubElement(dof, XADES + "MimeType").text = "text/xml"

    # Append signature to root (end of document)
    root.append(signature)

    # Return pretty-stable bytes
    return format_xml_bytes(
        etree.tostring(root, encoding="utf-8", xml_declaration=False)
    ).decode("utf-8")


def sign_with_xmlsec(input_xml: bytes, key_pem_path: str, cert_pem_path: str) -> bytes:
    """
    Call xmlsec1 to sign the XML produced by inject_signature_template.
    IMPORTANT: we declare ID attributes so xmlsec can resolve our references.
    """
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "in.xml")
        out_path = os.path.join(td, "out.xml")
        with open(in_path, "wb") as f:
            f.write(input_xml)

        cmd = [
            "xmlsec1",
            "--sign",
            "--privkey-pem",
            f"{key_pem_path},{cert_pem_path}",
            "--id-attr:id",
            "factura",            # SRI invoices root element
            "--id-attr:Id",
            "SignedProperties",
            "--id-attr:Id",
            "KeyInfo",
            "--output",
            out_path,
            in_path,
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(f"xmlsec1 failed:\n{p.stderr.decode('utf-8', 'ignore')}")
        return open(out_path, "rb").read()
