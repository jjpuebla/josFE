from xml.etree.ElementTree import Element, SubElement, tostring
from lxml import etree
from decimal import Decimal, ROUND_UP, ROUND_CEILING, ROUND_HALF_UP

import frappe
from josfe.sri_invoicing.xml.utils import (
    _text, D, money, qty6, ddmmyyyy,
    get_company_address, get_warehouse_address, get_ce_pe_seq,
    get_obligado_contabilidad, buyer_id_type,
    get_forma_pago, map_tax_item, map_tax_invoice, get_info_adicional,
    hash8_from_string,
)

from josfe.sri_invoicing.core.validations.access_key import generate_access_key
from josfe.sri_invoicing.core.utils import common
from josfe.sri_invoicing.xml.utils import format_xml_bytes


# -------------------------
# Pretty-print XML helper
# -------------------------
def to_pretty_xml(elem: Element) -> str:
    """
    Return XML string with pretty-printing and preserved UTF-8 characters.
    Uses the shared utils formatter for consistency.
    """
    raw = tostring(elem, encoding="utf-8")      # bytes from ElementTree
    return format_xml_bytes(raw).decode("utf-8")


def _resolve_ambiente(si) -> str:
    """
    Resolve ambiente:
    - Prefer Credenciales SRI.jos_ambiente for the invoice's company
    - Fallback to FE Settings.env_override
    - Default: '2' (Producción)
    """
    try:
        # 1. Check Credenciales SRI for this company
        amb = frappe.db.get_value(
            "Credenciales SRI",
            {"company": si.company, "jos_activo": 1},
            "jos_ambiente"
        )
        if amb:
            return "1" if amb.strip().lower().startswith("prueb") else "2"

        # 2. Fallback: FE Settings
        env = frappe.db.get_single_value("FE Settings", "env_override")
        if env:
            return "1" if env.strip().lower().startswith("prueb") else "2"

    except Exception:
        pass

    # 3. Default
    return "2"


def build_factura_xml(si_name: str) -> tuple[str, dict]:
    """Build deterministic SRI Factura XML for the given Sales Invoice."""
    si = frappe.get_doc("Sales Invoice", si_name)
    company = frappe.get_doc("Company", si.company)

    # Root (match sample spec)
    factura = Element("factura", {"id": "comprobante", "version": "1.0.0"})

    # -------------------------
    # infoTributaria
    # -------------------------
    infoTrib = SubElement(factura, "infoTributaria")
    ambiente = _resolve_ambiente(si)
    tipo_emision = "1"

    _text(infoTrib, "ambiente", ambiente)
    _text(infoTrib, "tipoEmision", tipo_emision)
    _text(infoTrib, "razonSocial", company.custom_jos_razon_social or company.company_name)
    _text(infoTrib, "nombreComercial", company.custom_jos_nombre_comercial or company.company_name)
    _text(infoTrib, "ruc", company.tax_id)

    codes = get_ce_pe_seq(si)  # {'ce': '002', 'pe': '002', 'secuencial': '000000051'}

    # Access key (clave de acceso)
    clave = generate_access_key(
        fecha_emision_ddmmyyyy=ddmmyyyy(si.posting_date),
        cod_doc="01",
        ruc=company.tax_id,
        ambiente=ambiente,
        estab=codes["ce"],
        pto_emi=codes["pe"],
        secuencial_9d=codes["secuencial"],
        codigo_numerico_8d="12345678",   # ✅ always fixed as per SRI guidance
        tipo_emision=tipo_emision,
    )
    _text(infoTrib, "claveAcceso", clave)
    _text(infoTrib, "codDoc", "01")
    _text(infoTrib, "estab", codes["ce"])
    _text(infoTrib, "ptoEmi", codes["pe"])
    _text(infoTrib, "secuencial", codes["secuencial"])
    _text(
        infoTrib,
        "dirMatriz",
        company.custom_jos_direccion_matriz or get_company_address(company.name, prefer_title="Matriz"),
    )

    # -------------------------
    # calculate totals (first pass)
    # -------------------------
    total_desc = D("0.00")
    for it in si.items:
        precio_unitario = (D(it.net_amount or 0) / D(it.qty or 1)).quantize(D("0.01"), rounding=ROUND_UP)
        descuento = (precio_unitario * D(it.qty or 0)) - D(it.net_amount or 0)
        total_desc += descuento

    # -------------------------
    # infoFactura
    # -------------------------
    infoFac = SubElement(factura, "infoFactura")
    _text(infoFac, "fechaEmision", si.posting_date.strftime("%d/%m/%Y"))
    _text(infoFac, "dirEstablecimiento", get_warehouse_address(getattr(si, "custom_jos_level3_warehouse", None)))
    _text(infoFac, "obligadoContabilidad", get_obligado_contabilidad(company.name))

    buyer_id = si.tax_id
    _text(infoFac, "tipoIdentificacionComprador", buyer_id_type(buyer_id))
    _text(infoFac, "razonSocialComprador", si.customer_name)
    _text(infoFac, "identificacionComprador", buyer_id)

    _text(
        infoFac,
        "direccionComprador",
        frappe.db.get_value("Address", {"name": si.customer_address}, "address_line1"),
    )

    # Totals
    total_sin_imp = money(D(getattr(si, "net_total", getattr(si, "total", 0))))
    importe_total = money(D(getattr(si, "grand_total", 0)))
    _text(infoFac, "totalSinImpuestos", total_sin_imp)
    _text(infoFac, "totalDescuento", total_desc)

    # totalConImpuestos (invoice-level)
    totalConImp = SubElement(infoFac, "totalConImpuestos")
    for tmap in map_tax_invoice(si):
        ti = SubElement(totalConImp, "totalImpuesto")
        _text(ti, "codigo", tmap["codigo"])
        _text(ti, "codigoPorcentaje", tmap["codigoPorcentaje"])
        _text(ti, "baseImponible", tmap["baseImponible"])
        _text(ti, "valor", tmap["valor"])
    _text(infoFac, "propina", "0.00")
    _text(infoFac, "importeTotal", importe_total)
    _text(infoFac, "moneda", company.default_currency or "USD")

    # pagos
    pagos = get_forma_pago(si)
    if pagos:
        pagos_el = SubElement(infoFac, "pagos")
        for p in pagos:
            pago_el = SubElement(pagos_el, "pago")
            _text(pago_el, "formaPago", p["formaPago"])  # code only (01/20/16/19)
            _text(pago_el, "total", p["total"])

    # -------------------------
    # detalles
    # -------------------------
    detalles = SubElement(factura, "detalles")
    for it in si.items:
        d = SubElement(detalles, "detalle")
        _text(d, "codigoPrincipal", it.item_code)
        _text(d, "descripcion", it.item_name or it.description)
        
        # ✅ unidadMedida (optional, but valid if present)
        if getattr(it, "stock_uom", None):
            _text(d, "unidadMedida", it.stock_uom)
            
        _text(d, "cantidad", qty6(it.qty))
        precio_unitario = (D(it.net_amount or 0) / D(it.qty or 1)).quantize(D("0.01"), rounding=ROUND_UP)
        _text(d, "precioUnitario", money(precio_unitario))
        # descuento = adjustment for rounding differences
        descuento = (precio_unitario * D(it.qty or 0)) - D(it.net_amount or 0)
        _text(d, "descuento", money(descuento))
        _text(d, "precioTotalSinImpuesto", money(it.net_amount))

        imp = SubElement(d, "impuestos")
        # Render all applicable taxes for this item (IVA/ICE/IRBPNR, mixed rates)
        for tmap in map_tax_item(si, it):
            i = SubElement(imp, "impuesto")
            _text(i, "codigo", tmap["codigo"])
            _text(i, "codigoPorcentaje", tmap["codigoPorcentaje"])
            # <tarifa> is expected at item level for IVA; optional for other taxes
            if tmap.get("tarifa") is not None:
                _text(i, "tarifa", tmap["tarifa"])
            _text(i, "baseImponible", tmap["baseImponible"])
            _text(i, "valor", tmap["valor"])
    # -------------------------
    # infoAdicional
    # -------------------------
    adicionales = get_info_adicional(si)
    if adicionales:
        infoAd = SubElement(factura, "infoAdicional")
        for campo in adicionales:
            ca = SubElement(infoAd, "campoAdicional", {"nombre": campo["nombre"][:300]})
            ca.text = str(campo["valor"])[:300]

    # --- Validation: ensure taxes reconcile ---
    xml_val = sum(D(imp["valor"]) for it in si.items for imp in map_tax_item(si, it))
    if abs(xml_val - D(si.total_taxes_and_charges or 0)) > D("0.01"):
        frappe.throw(f"El XML no cuadra impuestos (ERP={si.total_taxes_and_charges}, XML={xml_val})")



    # -------------------------
    # Output
    # -------------------------
    xml_string = to_pretty_xml(factura)
    meta = {
        "clave_acceso": clave,
        "estab": codes["ce"],
        "pto_emi": codes["pe"],
        "secuencial": codes["secuencial"],
        "importe_total": importe_total,
    }
    return xml_string, meta
    
