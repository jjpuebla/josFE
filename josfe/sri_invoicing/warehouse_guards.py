# apps/josfe/josfe/sri_invoicing/warehouse_guards.py
import frappe

def prevent_deleting_emission_point(doc, method=None):
    """
    Allow delete only if no SRI docs exist for this Est + PE.
    Otherwise block with a clear message.
    """
    # get establishment code from parent warehouse
    est_code = frappe.db.get_value("Warehouse", doc.parent, "custom_establishment_code")
    ep_code = (doc.emission_point_code or "").strip()

    if not (est_code and ep_code):
        return  # nothing to check, allow delete

    # check across doctypes
    doctypes = [
        "Sales Invoice",
        "Nota de Crédito",
        "Nota de Débito",
        "Comprobante de Retención",
        "Liquidación de Compra",
        "Guía de Remisión",
    ]
    for dt in doctypes:
        if frappe.db.exists(dt, {"custom_establishment_code": est_code, "custom_emission_point_code": ep_code}):
            frappe.throw("Ya existen documentos emitidos en este punto de Emisión. No se puede eliminar, solo desactivar.")