# -*- coding: utf-8 -*-
# apps/josfe/josfe/sri_invoicing/xml/builders.py
import frappe
from frappe.utils import flt
from xml.etree.ElementTree import Element, SubElement, tostring

def _z3(v): 
    return str(v or "").strip().zfill(3)

def _z9(n): 
    return f"{int(n):09d}"

def _text(parent, tag, value):
    el = SubElement(parent, tag)
    el.text = "" if value is None else str(value)
    return el

def _ambiente_for(company: str) -> str:
    """Map Credenciales SRI 'Pruebas/Producción' -> 1/2. Defaults to 1."""
    cred = frappe.get_all(
        "Credenciales SRI",
        filters={"company": company, "jos_activo": 1},
        fields=["name", "jos_ambiente"],
        limit=1,
    )
    if not cred:
        return "1"
    return "2" if (cred[0].get("jos_ambiente") == "Producción") else "1"

def build_sales_invoice_xml(si) -> str:
    """
    Build a minimal SRI 'factura' XML string (unsigned).
    NOTE: This is an MVP scaffold: structure is correct, but you must
    later plug exact XSD compliance, impuestos por detalle, claveAcceso, etc.
    """
    if isinstance(si, str):
        si = frappe.get_doc("Sales Invoice", si)

    company = frappe.get_doc("Company", si.company)
    customer_name = getattr(si, "customer_name", getattr(si, "customer", "")) or ""
    buyer_tax = getattr(si, "tax_id", "") or getattr(si, "customer_tax_id", "") or ""
    posting_date = frappe.utils.getdate(getattr(si, "posting_date", None))
    fecha_emision = posting_date.strftime("%d/%m/%Y") if posting_date else ""

    estab = _z3(getattr(si, "sri_establishment_code", ""))
    ptoEmi = _z3(getattr(si, "sri_emission_point_code", ""))
    sec = _z9(getattr(si, "sri_sequential_assigned", 0))
    ambiente = _ambiente_for(si.company)

    total_sin_imp = flt(getattr(si, "net_total", getattr(si, "total", 0)))
    total_desc = flt(getattr(si, "discount_amount", 0))
    importe_total = flt(getattr(si, "grand_total", 0))

    # --- XML build ---
    factura = Element("factura", attrib={"id": "comprobante", "version": "1.1.0"})

    infoTrib = SubElement(factura, "infoTributaria")
    _text(infoTrib, "ambiente", ambiente)           # 1 pruebas, 2 producción
    _text(infoTrib, "tipoEmision", "1")             # normal
    _text(infoTrib, "razonSocial", company.company_name or company.name)
    _text(infoTrib, "nombreComercial", company.company_name or company.name)
    _text(infoTrib, "ruc", getattr(company, "tax_id", "") or "")
    _text(infoTrib, "claveAcceso", "PENDIENTE")     # TODO: generar claveAcceso válida
    _text(infoTrib, "codDoc", "01")                 # 01: Factura
    _text(infoTrib, "estab", estab)
    _text(infoTrib, "ptoEmi", ptoEmi)
    _text(infoTrib, "secuencial", sec)
    _text(infoTrib, "dirMatriz", "")                # TODO: direccion matriz

    infoFact = SubElement(factura, "infoFactura")
    _text(infoFact, "fechaEmision", fecha_emision)
    _text(infoFact, "dirEstablecimiento", "")       # TODO: direccion establecimiento
    _text(infoFact, "obligadoContabilidad", "NO")   # TODO: parametrizar
    _text(infoFact, "tipoIdentificacionComprador", "05")  # TODO: mapear según RUC/Cédula/Pasaporte
    _text(infoFact, "razonSocialComprador", customer_name)
    _text(infoFact, "identificacionComprador", buyer_tax)
    _text(infoFact, "totalSinImpuestos", f"{total_sin_imp:.2f}")
    _text(infoFact, "totalDescuento", f"{total_desc:.2f}")

    totalConImp = SubElement(infoFact, "totalConImpuestos")
    # MVP: single IVA 12% bucket if taxes exist; refine later per detalle
    # (Schema requires children; we provide a zero line if no taxes.)
    totalImpuesto = SubElement(totalConImp, "totalImpuesto")
    _text(totalImpuesto, "codigo", "2")             # IVA
    _text(totalImpuesto, "codigoPorcentaje", "2")   # 12% (MVP default)
    _text(totalImpuesto, "baseImponible", f"{total_sin_imp:.2f}")
    # naive 12% for MVP; replace with computed taxes
    _text(totalImpuesto, "valor", f"{(total_sin_imp * 0.12):.2f}")

    _text(infoFact, "propina", "0.00")
    _text(infoFact, "importeTotal", f"{importe_total:.2f}")
    _text(infoFact, "moneda", getattr(si, "currency", "USD") or "USD")

    detalles = SubElement(factura, "detalles")
    for it in (si.items or []):
        d = SubElement(detalles, "detalle")
        _text(d, "codigoPrincipal", getattr(it, "item_code", "") or "")
        _text(d, "descripcion", getattr(it, "item_name", "") or getattr(it, "description", "") or "")
        _text(d, "cantidad", f"{flt(getattr(it, 'qty', 0)):.6f}")
        _text(d, "precioUnitario", f"{flt(getattr(it, 'rate', 0)):.6f}")
        _text(d, "descuento", f"{flt(getattr(it, 'discount_amount', 0)):.2f}")
        net = flt(getattr(it, "net_amount", getattr(it, "amount", 0)))
        _text(d, "precioTotalSinImpuesto", f"{net:.2f}")

        imp = SubElement(d, "impuestos")
        detImp = SubElement(imp, "impuesto")
        _text(detImp, "codigo", "2")                # IVA
        _text(detImp, "codigoPorcentaje", "2")      # 12% MVP
        _text(detImp, "tarifa", "12.00")
        _text(detImp, "baseImponible", f"{net:.2f}")
        _text(detImp, "valor", f"{(net * 0.12):.2f}")

    # Optional info adicional
    infoAd = SubElement(factura, "infoAdicional")
    if getattr(si, "remarks", None):
        ca = SubElement(infoAd, "campoAdicional", attrib={"nombre": "Observación"})
        ca.text = si.remarks

    xml_bytes = tostring(factura, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
    return xml_bytes.decode("utf-8")
