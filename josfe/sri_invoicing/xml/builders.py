from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import frappe
from josfe.sri_invoicing.xml.utils import (
    _text, D, money, qty6, ddmmyyyy,
    get_company_address, get_warehouse_address, get_ce_pe_seq,
    get_obligado_contabilidad, buyer_id_type,
    get_forma_pago, map_tax_item, map_tax_invoice, get_info_adicional,
    hash8_from_string,
)

from josfe.sri_invoicing.validations.access_key import generate_access_key



# -------------------------
# Pretty-print XML helper
# -------------------------
def to_pretty_xml(elem: Element) -> str:
    """Return a pretty-printed XML string for the Element."""
    raw = tostring(elem, encoding="utf-8")
    parsed = minidom.parseString(raw)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    # Remove empty lines minidom injects
    pretty = "\n".join([line for line in pretty.splitlines() if line.strip()])
    return pretty


def _resolve_ambiente(si) -> str:
    """
    Conservative fallback:
    - If FE Settings.env_override == 'Pruebas' -> '1' else '2'
    You can later replace with your Credenciales SRI doctype lookup.
    """
    try:
        env = frappe.db.get_single_value("FE Settings", "env_override")
        return "1" if (env or "").strip().lower().startswith("prueb") else "2"
    except Exception:
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
    total_desc = money(D(getattr(si, "discount_amount", 0)))
    importe_total = money(D(getattr(si, "grand_total", 0)))
    _text(infoFac, "totalSinImpuestos", total_sin_imp)
    _text(infoFac, "totalDescuento", total_desc)

    # totalConImpuestos (invoice-level)
    totalConImp = SubElement(infoFac, "totalConImpuestos")
    ti = SubElement(totalConImp, "totalImpuesto")
    inv_tax_map = map_tax_invoice(si)  # IVA 15% aggregate
    for k, v in inv_tax_map.items():
        _text(ti, k, v)

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
        _text(d, "cantidad", qty6(it.qty))
        _text(d, "precioUnitario", qty6(it.rate))
        _text(d, "descuento", money(D(getattr(it, "discount_amount", 0))))
        _text(d, "precioTotalSinImpuesto", money(D(getattr(it, "net_amount", getattr(it, "amount", 0)))))

        imp = SubElement(d, "impuestos")
        i = SubElement(imp, "impuesto")
        tmap = map_tax_item(it)  # IVA 15% at item level
        for k, v in tmap.items():
            _text(i, k, v)

    # -------------------------
    # infoAdicional
    # -------------------------
    adicionales = get_info_adicional(si)
    if adicionales:
        infoAd = SubElement(factura, "infoAdicional")
        for campo in adicionales:
            ca = SubElement(infoAd, "campoAdicional", {"nombre": campo["nombre"]})
            ca.text = str(campo["valor"])

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
    
