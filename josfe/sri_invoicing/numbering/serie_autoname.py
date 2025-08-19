import frappe
from josfe.sri_invoicing.numbering.state import next_sequential

def _z3(v): return str(v or "").strip().zfill(3)
def _z9(n): return f"{int(n):09d}"

def _establishment_of(warehouse_name: str) -> str:
    est = frappe.db.get_value("Warehouse", warehouse_name, "custom_establishment_code")
    if not est:
        frappe.throw("El Warehouse seleccionado no tiene Establecimiento (EC) configurado.")
    return _z3(est)

def si_autoname(doc, method):
    if getattr(doc, "amended_from", None):
        return  # let Frappe handle amended naming

    wh = getattr(doc, "custom_jos_level3_warehouse", None)
    pe = getattr(doc, "custom_jos_sri_emission_point_code", None)
    if not wh or not pe:
        frappe.throw("Seleccione Sucursal (3er nivel) y Punto de Emisión antes de guardar.")

    pe_code = _z3(pe.split(" - ", 1)[0])
    est_code = _establishment_of(wh)
    seq = next_sequential(wh, pe_code, "Factura")  # your atomic allocator

    # stash components (if you have these fields; otherwise keep as `doc.db_set` later)
    doc.sri_establishment_code = est_code
    doc.sri_emission_point_code = pe_code
    doc.sri_sequential_assigned = seq

    doc.name = f"{est_code}-{pe_code}-{_z9(seq)}"

    # mirror the final series for in-form display (Data, read-only)
    doc.custom_sri_serie = doc.name

