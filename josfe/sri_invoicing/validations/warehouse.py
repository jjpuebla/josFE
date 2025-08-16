# -*- coding: utf-8 -*-
import frappe

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
    Server-side guard that matches the UI flow:

    - Before INIT (initiated == 0): allow seq_* == 0 (or blank). Just block negatives.
    - After INIT  (initiated == 1): require all seq_* >= 1. (UI also enforces this.)
    """
    child_field = _child_fieldname_on_warehouse()
    if not child_field:
        return

    rows = getattr(doc, child_field, []) or []
    for idx, row in enumerate(rows, start=1):
        initiated = int(row.initiated or 0)

        # Normalize empties to 0 and block negatives
        for fn, label in SEQ_LABELS.items():
            n = _as_int(getattr(row, fn, 0))
            if n < 0:
                frappe.throw(f"Fila {idx}: Secuencial inválido para {label}. No se permiten negativos.")
            # write back normalized value (avoids None/'' issues)
            setattr(row, fn, n)

        if initiated:
            # After INIT: all must be >= 1
            for fn, label in SEQ_LABELS.items():
                if _as_int(getattr(row, fn, 0)) < 1:
                    frappe.throw(f"Fila {idx}: Secuencial inicial inválido para {label}. Debe ser ≥ 1.")
        else:
            # Before INIT: zeros are fine (UI will block Save anyway if any row not INITed)
            pass
