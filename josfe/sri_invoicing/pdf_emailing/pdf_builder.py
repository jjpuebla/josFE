# apps/josfe/josfe/sri_invoicing/pdf_emailing/pdf_builder.py
# -*- coding: utf-8 -*-

import os
import base64
import frappe
import xml.etree.ElementTree as ET
from io import BytesIO
from frappe.utils import getdate
from frappe.utils.pdf import get_pdf
from josfe.sri_invoicing.xml import paths as xml_paths

import qrcode
import barcode
from barcode.writer import ImageWriter


# ---------------- QR + Barcode helpers ----------------

def _generate_qr_base64(clave_acceso: str) -> str:
    """Generate QR code for claveAcceso and return as base64 data URI."""
    if not clave_acceso:
        return ""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(clave_acceso)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"

def _file_to_base64(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"

def _generate_barcode_base64(clave_acceso: str) -> str:
    """Generate Code128 barcode for claveAcceso as base64 data URI."""
    if not clave_acceso:
        return ""
    code128 = barcode.get("code128", clave_acceso, writer=ImageWriter())
    buffer = BytesIO()
    code128.write(buffer, options={"module_height": 8.0, "font_size": 5.5, "text_distance": 2.5 })
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


# ---------------- XML parser ----------------

def _parse_autorizado_xml(abs_xml_path: str) -> dict:
    """Parse AUTORIZADO XML and extract all relevant fields into a dict."""
    if not os.path.exists(abs_xml_path):
        return {}

    try:
        tree = ET.parse(abs_xml_path)
        root = tree.getroot()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error parsing AUTORIZADO XML")
        return {}

    auth = {}

    # numeroAutorizacion + fechaAutorizacion come from wrapper
    for tag in ("numeroAutorizacion", "fechaAutorizacion", "ambiente", "tipoEmision"):
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            auth[tag] = el.text.strip()

    # Parse <comprobante> inner XML (CDATA)
    comprobante_el = root.find(".//comprobante")
    if comprobante_el is not None and comprobante_el.text:
        try:
            inner_xml = comprobante_el.text.strip()
            inner_root = ET.fromstring(inner_xml)

            # Clave de Acceso (inside comprobante, not wrapper)
            el = inner_root.find(".//claveAcceso")
            if el is not None and el.text:
                auth["claveAcceso"] = el.text.strip()

            # Basic invoice fields
            for tag in (
                "razonSocialComprador",
                "identificacionComprador",
                "direccionComprador",
                "fechaEmision",
                "totalSinImpuestos",
                "totalDescuento",
                "importeTotal",
                "obligadoContabilidad",
                "ruc",
                "dirMatriz",
                "dirEstablecimiento",
                "estab",
                "ptoEmi",
                "secuencial",
            ):
                el = inner_root.find(f".//{tag}")
                if el is not None and el.text:
                    auth[tag] = el.text.strip()

            # Totals (list of impuestos)
            auth["totalConImpuestos"] = []
            for imp in inner_root.findall(".//totalConImpuesto"):
                entry = {}
                for subtag in ("codigo", "codigoPorcentaje", "baseImponible", "valor"):
                    el = imp.find(subtag)
                    if el is not None and el.text:
                        entry[subtag] = el.text.strip()
                if entry:
                    auth["totalConImpuestos"].append(entry)

            # Pagos
            auth["pagos"] = []
            for pago in inner_root.findall(".//pago"):
                entry = {}
                for subtag in ("formaPago", "total"):
                    el = pago.find(subtag)
                    if el is not None and el.text:
                        entry[subtag] = el.text.strip()

                # add description mapping
                if "formaPago" in entry:
                    descriptions = {
                        "01": "SIN UTILIZACIÓN DEL SISTEMA FINANCIERO",
                        "15": "COMPENSACIÓN DE DEUDAS",
                        "16": "TARJETA DE DÉBITO",
                        "17": "DINERO ELECTRÓNICO",
                        "18": "TARJETA PREPAGO",
                        "19": "TARJETA DE CRÉDITO",
                        "20": "OTROS CON UTILIZACIÓN DEL SISTEMA FINANCIERO",
                        "21": "ENDOSO DE TÍTULOS",
                    }
                    entry["descripcion"] = descriptions.get(entry["formaPago"], entry["formaPago"])
                auth["pagos"].append(entry)
            # Información adicional
            auth["infoAdicional"] = []
            for campo in inner_root.findall(".//campoAdicional"):
                entry = {}
                if "nombre" in campo.attrib:
                    entry["nombre"] = campo.attrib["nombre"]
                entry["valor"] = campo.text.strip() if campo.text else ""
                if entry:
                    auth["infoAdicional"].append(entry)

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Error parsing inner comprobante XML")

    # Add QR + barcode
    auth["qr"] = _generate_qr_base64(auth.get("claveAcceso"))
    auth["barcode"] = _generate_barcode_base64(auth.get("claveAcceso"))

    return auth


# ---------------- PDF builder ----------------

def build_invoice_pdf(qdoc) -> str:
    """
    Render Sales Invoice into PDF, enriched with values from AUTORIZADO XML.
    Saves under /private/files/SRI/RIDE/mm-YYYY/<QueueName>.pdf
    Returns the /private/files/... URL.
    """
    # Load linked Sales Invoice
    inv = None
    if qdoc.get("sales_invoice"):
        inv = frappe.get_doc("Sales Invoice", qdoc.sales_invoice)
    elif qdoc.get("reference_doctype") == "Sales Invoice":
        inv = frappe.get_doc("Sales Invoice", qdoc.reference_name)
    else:
        frappe.throw("SRI XML Queue row missing Sales Invoice link.")

    # Locate AUTORIZADO XML
    xml_url = qdoc.get("xml_file")
    auth_fields = {}
    if xml_url:
        abs_xml_path = frappe.get_site_path("private", "files", xml_url.replace("/private/files/", ""))
        auth_fields = _parse_autorizado_xml(abs_xml_path)

    # Add company logo absolute path
    logo_url = frappe.db.get_value("Company", inv.company, "company_logo")
    logo_abs = ""
    if logo_url:
        try:
            file_doc = frappe.get_doc("File", {"file_url": logo_url})
            raw_path = file_doc.get_full_path()
            logo_abs = os.path.abspath(raw_path)   # ensure absolute
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Error resolving company logo path")

    auth_fields["logo_base64"] = _file_to_base64(logo_abs)

    # Render template
    html = frappe.render_template(
        "josfe/sri_invoicing/pdf_emailing/templates/factura.html",
        {"doc": inv, "queue": qdoc, "auth": auth_fields},
    )
    pdf_bytes = get_pdf(html)

    # Save PDF under RIDE/mm-YYYY
    d = getdate(inv.posting_date)
    rel_dir = f"RIDE/{d.month:02d}-{d.year}"
    fname = f"{qdoc.name}.pdf"
    abs_path = xml_paths.abs_path(rel_dir, fname)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    with open(abs_path, "wb") as f:
        f.write(pdf_bytes)

    return xml_paths.to_file_url(rel_dir, fname)
