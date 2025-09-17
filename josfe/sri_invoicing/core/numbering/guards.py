import frappe

SEQ_FIELDS = ["seq_factura","seq_nc","seq_nd","seq_ret","seq_liq","seq_gr"]

def _rows_by_name(rows):
    return {r.name: r for r in rows or []}

def validate_warehouse_seq_edits(doc, method):
    """
    Prevent direct edits to seq_* in child table SRI Puntos Emision.
    Allowed path is only via initiate_or_edit() RPC, which writes with db.set_value.
    """
    # If this save is coming from our RPC, you could set a request header/context flag and allow it.
    # Here we simply block any diffs on user saves.
    try:
      before = doc.get_doc_before_save()
    except Exception:
      before = None

    if not before:
        return

    old_map = _rows_by_name(before.get("custom_sri_puntos_emision"))
    for row in (doc.get("custom_sri_puntos_emision") or []):
        prev = old_map.get(row.name)
        if not prev:
            # New row — allow creation but not setting seq_* directly
            if any(getattr(row, f) for f in SEQ_FIELDS):
                frappe.throw("Direct editing of sequentials is not allowed. Use the ‘Init / Edit’ button.")
            continue

        for f in SEQ_FIELDS:
            old_val = int(getattr(prev, f) or 0)
            new_val = int(getattr(row, f) or 0)
            if new_val != old_val:
                frappe.throw("Direct editing of sequentials is not allowed. Use the ‘Init / Edit’ button.")
