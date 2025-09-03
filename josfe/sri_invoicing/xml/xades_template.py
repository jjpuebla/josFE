# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/xades_template.py

from __future__ import annotations
from xml.etree import ElementTree as ET
import datetime
from josfe.sri_invoicing.signing.pem_tools import extract_cert_info

# Keep stable prefixes in output
ET.register_namespace("ds", "http://www.w3.org/2000/09/xmldsig#")
ET.register_namespace("xades", "http://uri.etsi.org/01903/v1.3.2#")

SIGNATURE_TEMPLATE_XML = """<ds:Signature Id="SignatureSP"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:xades="http://uri.etsi.org/01903/v1.3.2#">
  <ds:SignedInfo>
    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
    <ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
    <ds:Reference Id="SignedDataRef" URI="#comprobante">
      <ds:Transforms>
        <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
        <ds:Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
      </ds:Transforms>
      <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
      <ds:DigestValue></ds:DigestValue>
    </ds:Reference>
  </ds:SignedInfo>
  <ds:SignatureValue></ds:SignatureValue>
  <ds:KeyInfo>
    <ds:X509Data>
      <ds:X509Certificate></ds:X509Certificate>
    </ds:X509Data>
  </ds:KeyInfo>
  <ds:Object>
    <xades:QualifyingProperties Target="#SignatureSP">
      <xades:SignedProperties Id="SignedPropertiesID">
        <xades:SignedSignatureProperties>
          <xades:SigningTime></xades:SigningTime>
          <xades:SigningCertificate>
            <xades:Cert>
              <xades:CertDigest>
                <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
                <ds:DigestValue></ds:DigestValue>
              </xades:CertDigest>
              <xades:IssuerSerial>
                <ds:X509IssuerName></ds:X509IssuerName>
                <ds:X509SerialNumber></ds:X509SerialNumber>
              </xades:IssuerSerial>
            </xades:Cert>
          </xades:SigningCertificate>
        </xades:SignedSignatureProperties>
      </xades:SignedProperties>
    </xades:QualifyingProperties>
  </ds:Object>
</ds:Signature>"""

def inject_signature_template(xml_text: str, cert_pem_path: str) -> str:
    """
    Ensure <factura id="comprobante"> has a <ds:Signature> template.
    Populate SigningTime, CertDigest, IssuerSerial from certificate.
    """
    root = ET.fromstring(xml_text)

    if not root.tag.endswith("factura"):
        raise ValueError("Root XML is not <factura>.")

    if root.get("id") != "comprobante":
        if root.get("Id") == "comprobante":
            root.attrib.pop("Id", None)
        root.set("id", "comprobante")

    ns = {"ds": "http://www.w3.org/2000/09/xmldsig#", "xades": "http://uri.etsi.org/01903/v1.3.2#"}
    ds_sig = root.find("ds:Signature", ns)

    if ds_sig is None:
        sig_el = ET.fromstring(SIGNATURE_TEMPLATE_XML)
        root.append(sig_el)
        ds_sig = sig_el

    # Load cert info
    cert_info = extract_cert_info(cert_pem_path)

    # Fill SigningTime
    el = ds_sig.find(".//xades:SigningTime", ns)
    if el is not None:
        el.text = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    # Fill DigestValue
    el = ds_sig.find(".//xades:CertDigest/ds:DigestValue", ns)
    if el is not None:
        el.text = cert_info["digest"]

    # Fill Issuer
    el = ds_sig.find(".//xades:IssuerSerial/ds:X509IssuerName", ns)
    if el is not None:
        el.text = cert_info["issuer"]

    # Fill Serial
    el = ds_sig.find(".//xades:IssuerSerial/ds:X509SerialNumber", ns)
    if el is not None:
        el.text = cert_info["serial"]

    return ET.tostring(root, encoding="utf-8").decode("utf-8")