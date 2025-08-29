# -*- coding: utf-8 -*-
import frappe
from frappe import _

CHILD_DOCTYPE = "SRI Puntos Emision"

# Candidate child table fieldnames on Warehouse (first match wins)
WAREHOUSE_CHILD_FIELDS = (
    "custom_jos_SRI_puntos_emision",
    "custom_jos_Sri_puntos_emision",
    "custom_sri_puntos_emision",
)

SEQ_LABELS = {
    "seq_factura": "Factura",
    "seq_nc": "Nota de Crédito",
    "seq_nd": "Nota de Débito",
    "seq_ret": "Comprobante Retención",
    "seq_liq": "Liquidación Compra",
    "seq_gr": "Guía de Remisión",
}
def validate_no_duplicate_pe_per_parent(doc, method=None):
    # Find the child table field actually used on Warehouse
    for fieldname in ("custom_jos_SRI_puntos_emision",
                      "custom_jos_Sri_puntos_emision",
                      "custom_sri_puntos_emision"):
        rows = doc.get(fieldname)
        if rows:
            break
    else:
        return

    seen = set()
    for r in rows:
        code = (r.get("emission_point_code") or "").strip()
        if not code:
            frappe.throw(f"Fila {r.idx}: Código de Punto de Emisión vacío.")
        if code in seen:
            frappe.throw(f"Fila {r.idx}: Punto de Emisión '{code}' repetido en esta Sucursal.")
        seen.add(code)


def _child_fieldname_on_warehouse() -> str | None:
    meta = frappe.get_meta("Warehouse")
    for f in WAREHOUSE_CHILD_FIELDS:
        df = meta.get_field(f)
        if df and df.fieldtype == "Table" and (df.options or "").strip() == CHILD_DOCTYPE:
            return f
    return None

def _as_int(v) -> int:
    try:
        return int(v)
    except Exception:
        return 0

def validate_warehouse_sri(doc, method=None): 
    """
    Server-side guard:

    - Normalize blank estado to "Inactivo".
    - Ensure only one Punto de Emisión can be Activo at any time
      (even before INIT).
    - Sequential rules stay the same.
    """
    child_field = _child_fieldname_on_warehouse()
    if not child_field:
        return

    rows = getattr(doc, child_field, []) or []

    # --- Normalize estado + sequential checks ---
    for idx, row in enumerate(rows, start=1):
        # Normalize estado
        current_estado = (row.estado or "").strip()
        if not current_estado:
            row.estado = "Inactivo"

        initiated = int(row.initiated or 0)

        # Normalize empties to 0 and block negatives
        for fn, label in SEQ_LABELS.items():
            n = _as_int(getattr(row, fn, 0))
            if n < 0:
                frappe.throw(f"Fila {idx}: Secuencial inválido para {label}. No se permiten negativos.")
            setattr(row, fn, n)  # write back normalized

        if initiated:
            # After INIT: all must be >= 1
            for fn, label in SEQ_LABELS.items():
                if _as_int(getattr(row, fn, 0)) < 1:
                    frappe.throw(f"Fila {idx}: Secuencial inicial inválido para {label}. Debe ser ≥ 1.")

    # --- NEW RULE: Only one row can be Activo ---
    active_rows = [r for r in rows if (r.estado or "").strip().lower() == "activo"]
    if len(active_rows) > 1:
        raise frappe.ValidationError(
            _("Solo un Punto de Emisión puede estar en estado Activo en la bodega '{0}'. "
              "Actualmente activos: {1}")
            .format(doc.name, ", ".join([r.emission_point_code or "?" for r in active_rows]))
        )
