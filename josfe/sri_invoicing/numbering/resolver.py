# apps/josfe/josfe/sri_invoicing/numbering/resolver.py
import frappe

# Map SRI document type → current counter field kept in the child row
DOC_TYPE_TO_FIELD = {
    "Factura": "seq_factura",
    "Nota de Crédito": "seq_nc",
    "Nota de Débito": "seq_nd",
    "Comprobante Retención": "seq_ret",
    "Liquidación Compra": "seq_liq",
    "Guía de Remisión": "seq_gr",
}

def _zpad3(s: str) -> str:
    return str(s or "").strip().zfill(3)

def _get_active_row(wh_doc, emission_point_code: str):
    """Find the active child row (SRI Punto de Emisión) matching the 3-digit code."""
    target = _zpad3(emission_point_code)
    for r in (wh_doc.get("custom_sri_puntos_emision") or []):
        code = _zpad3(r.emission_point_code)
        estado = str(r.estado or "").strip().upper()
        if code == target and estado == "ACTIVO":
            return r
    return None

def resolve_sri_current(warehouse_name: str, emission_point_code: str, doc_type: str):
    """
    Return establishment code, 3-digit emission point, and CURRENT sequential for a given doc_type.
    This matches the M2 model: only 'seq_*' counters exist and are monotonically increased.
    """
    field = DOC_TYPE_TO_FIELD.get(doc_type)
    if not field:
        frappe.throw(f"Unsupported doc_type: {doc_type}")

    # Load Warehouse and establishment code
    wh = frappe.get_doc("Warehouse", warehouse_name)
    est = (wh.get("custom_establishment_code") or "").strip()
    if not est:
        frappe.throw(f"Warehouse '{warehouse_name}' has no establishment code (custom_establishment_code).")

    # Find active emission point row
    row = _get_active_row(wh, emission_point_code)
    if not row:
        frappe.throw(
            f"No active emission point '{_zpad3(emission_point_code)}' for warehouse '{warehouse_name}'."
        )

    # Get current counter (default 0 if not set)
    curr = getattr(row, field, None)
    if curr is None:
        # Keep the error explicit so setup issues are obvious
        frappe.throw(
            f"Missing current sequential field '{field}' for {doc_type} at emission point '{_zpad3(emission_point_code)}'."
        )

    return {
        "establishment_code": est,
        "emission_point_code": _zpad3(emission_point_code),
        "seq_current": int(curr or 0),
    }

# --- Back-compat helper (optional) ---
def resolve_sri_start(warehouse_name: str, emission_point_code: str, doc_type: str):
    """
    DEPRECATED: Kept for temporary compatibility with old callers.
    The new model does not use '*_start' fields. This returns the CURRENT value instead.
    Update callers to use resolve_sri_current() and 'seq_current'.
    """
    res = resolve_sri_current(warehouse_name, emission_point_code, doc_type)
    # Mirror the previous key name to ease transitional refactors, but the value is current.
    return {
        "establishment_code": res["establishment_code"],
        "emission_point_code": res["emission_point_code"],
        "seq_start": res["seq_current"],  # transitional alias
    }
