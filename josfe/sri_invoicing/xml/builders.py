from xml.etree.ElementTree import Element, SubElement, tostring
from josfe.sri_invoicing.xml.utils import _text, D, money, qty6, z3, z9, z8, ddmmyyyy, get_party_address_name, get_party_address_display
from josfe.sri_invoicing.validations.access_key import generate_access_key

import frappe

def build_factura_xml(si_name: str) -> tuple[str, dict]:
    """Build deterministic SRI Factura XML for the given Sales Invoice."""

    si = frappe.get_doc("Sales Invoice", si_name)

    # Root
    factura = Element("factura", {"id": "comprobante", "version": "1.1.0"})

    # -------------------------
    # infoTributaria
    # -------------------------
    infoTrib = SubElement(factura, "infoTributaria")
    ambiente = "1" if frappe.db.get_single_value("FE Settings", "env_override") == "Pruebas" else "2"
    tipo_emision = "1"

    _text(infoTrib, "ambiente", ambiente)
    _text(infoTrib, "tipoEmision", tipo_emision)
    _text(infoTrib, "razonSocial", si.company)
    _text(infoTrib, "nombreComercial", si.company)
    _text(infoTrib, "ruc", si.company_tax_id)

    # Access key
    clave = generate_access_key(
        fecha_emision_ddmmyyyy=ddmmyyyy(si.posting_date),
        cod_doc="01",
        ruc=si.company_tax_id,
        ambiente=ambiente,
        estab=z3(getattr(si, "sri_establishment_code", "001")),
        pto_emi=z3(getattr(si, "sri_emission_point_code", "001")),
        secuencial_9d=z9(getattr(si, "sri_sequential_assigned", 0)),
        codigo_numerico_8d=z8(si.name),
        tipo_emision=tipo_emision,
    )
    _text(infoTrib, "claveAcceso", clave)

    _text(infoTrib, "codDoc", "01")
    _text(infoTrib, "estab", z3(getattr(si, "sri_establishment_code", "001")))
    _text(infoTrib, "ptoEmi", z3(getattr(si, "sri_emission_point_code", "001")))
    _text(infoTrib, "secuencial", z9(getattr(si, "sri_sequential_assigned", 0)))

    dir_matriz = get_party_address_display("Company", si.company) or ""
    _text(infoTrib, "dirMatriz", dir_matriz)


    # -------------------------
    # infoFactura
    # -------------------------
    infoFac = SubElement(factura, "infoFactura")
    _text(infoFac, "fechaEmision", si.posting_date.strftime("%d/%m/%Y"))
    dir_establecimiento = get_party_address_display("Warehouse", si.custom_jos_level3_warehouse or "") or dir_matriz
    _text(infoFac, "dirEstablecimiento", dir_establecimiento)
    # _text(infoFac, "dirEstablecimiento", getattr(si, "custom_jos_level3_warehouse", ""))

    # Buyer
    buyer_id = si.tax_id
    buyer_type = "04" if len(buyer_id) == 13 else "05" if len(buyer_id) == 10 else "06"
    _text(infoFac, "tipoIdentificacionComprador", buyer_type)
    _text(infoFac, "razonSocialComprador", si.customer_name)
    _text(infoFac, "identificacionComprador", buyer_id)

    # Totals
    base_val = D(si.net_total or si.total)
    total_sin_imp = money(base_val)
    total_desc = money(D(si.discount_amount or 0))
    importe_total = money(D(si.grand_total or 0))

    _text(infoFac, "totalSinImpuestos", total_sin_imp)
    _text(infoFac, "totalDescuento", total_desc)

    totalConImp = SubElement(infoFac, "totalConImpuestos")
    ti = SubElement(totalConImp, "totalImpuesto")
    _text(ti, "codigo", "2")
    _text(ti, "codigoPorcentaje", "2")
    _text(ti, "tarifa", "12.00")
    _text(ti, "baseImponible", money(base_val))
    _text(ti, "valor", money(base_val * D("0.12")))

    _text(infoFac, "propina", "0.00")
    _text(infoFac, "importeTotal", importe_total)
    _text(infoFac, "moneda", "USD")

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
        _text(d, "descuento", "0.00")

        amount_val = D(it.amount)
        _text(d, "precioTotalSinImpuesto", money(amount_val))

        imp = SubElement(d, "impuestos")
        i = SubElement(imp, "impuesto")
        _text(i, "codigo", "2")
        _text(i, "codigoPorcentaje", "2")
        _text(i, "tarifa", "12.00")
        _text(i, "baseImponible", money(amount_val))
        _text(i, "valor", money(amount_val * D("0.12")))

    # -------------------------
    # Output
    # -------------------------
    xml_string = tostring(factura, encoding="utf-8").decode("utf-8")
    meta = {
        "clave_acceso": clave,
        "estab": z3(getattr(si, "sri_establishment_code", "001")),
        "pto_emi": z3(getattr(si, "sri_emission_point_code", "001")),
        "secuencial": z9(getattr(si, "sri_sequential_assigned", 0)),
        "importe_total": importe_total,
    }

    return xml_string, meta

