import frappe
from josfe.sri_invoicing.numbering.state import next_sequential
from frappe.utils import cint

def z3(v): 
    return str(v or "").strip().zfill(3)

def z9(n): 
    return f"{int(n):09d}"

def _establishment_of(warehouse_name: str) -> str:
    est = frappe.db.get_value("Warehouse", warehouse_name, "custom_establishment_code")
    if not est:
        frappe.throw("El Warehouse seleccionado no tiene Establecimiento (EC) configurado.")
    return z3(est)

def _ensure_sri_fields(doc):
    """Idempotente: rellena/asegura los campos SRI en el doc si están disponibles."""
    wh = getattr(doc, "custom_jos_level3_warehouse", None)
    pe = getattr(doc, "custom_jos_sri_emission_point_code", None)
    if not wh or not pe:
        return

    pe_code = z3(str(pe).split(" - ", 1)[0])
    est_code = _establishment_of(wh)

    # Asienta códigos
    doc.sri_establishment_code = est_code
    doc.sri_emission_point_code = pe_code

    # Si el name ya luce como EC-PE-SEQ, intenta derivar el secuencial al campo
    if getattr(doc, "name", None) and "-" in doc.name:
        parts = doc.name.split("-")
        if len(parts) == 3:
            try:
                doc.sri_sequential_assigned = int(parts[2])
            except Exception:
                pass

    # Espejo para el preview en el formulario
    if getattr(doc, "name", None):
        doc.custom_sri_serie = doc.name

def si_autoname(doc, method):
    # En enmendados, deja que Frappe maneje el autoname original
    if getattr(doc, "amended_from", None):
        return

    wh = getattr(doc, "custom_jos_level3_warehouse", None)
    pe = getattr(doc, "custom_jos_sri_emission_point_code", None)
    if not wh or not pe:
        frappe.throw("Seleccione Sucursal (3er nivel) y Punto de Emisión antes de guardar.")

    pe_code = z3(str(pe).split(" - ", 1)[0])
    est_code = _establishment_of(wh)
    seq = next_sequential(wh, pe_code, "Factura")  # asignador atómico

    # Persistir en el doc (estos campos deben existir en el DocType)
    doc.sri_establishment_code = est_code
    doc.sri_emission_point_code = pe_code
    doc.sri_sequential_assigned = seq

    # Nombre final
    doc.name = f"{est_code}-{pe_code}-{z9(seq)}"

    # Espejo a campo de ayuda de UI
    doc.custom_sri_serie = doc.name

def si_before_save(doc, method):
    _ensure_sri_fields(doc)



import frappe
from frappe.utils import cint

def sync_pe_next(est_code, ep_code, label, last_used):
    """Ensure PE row shows next available sequential (last_used + 1)."""
    fieldmap = {
        "Factura": "seq_factura",
        "Nota de Crédito": "seq_nc",
        "Nota de Débito": "seq_nd",
        "Comprobante Retención": "seq_ret",
        "Liquidación de Compra": "seq_liq",
        "Guía de Remisión": "seq_gr",
    }
    fn = fieldmap.get(label)
    if not fn:
        return

    # find the PE row
    pe = frappe.get_all(
        "SRI Puntos Emision",
        filters={"parenttype": "Warehouse",
                 "parentfield": "custom_sri_puntos_emision",
                 "emission_point_code": ep_code},
        fields=["name"],
        limit=1,
    )
    if not pe:
        return

    next_val = cint(last_used) + 1
    frappe.db.set_value("SRI Puntos Emision", pe[0].name, fn, next_val)
