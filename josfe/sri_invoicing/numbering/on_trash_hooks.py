# josfe/sri_invoicing/numbering/on_trash_hooks.py

import frappe

DOC_MAP = {
    "Sales Invoice": "seq_factura",
    "Nota de Crédito": "seq_nc",
    "Nota de Débito": "seq_nd",
    "Comprobante de Retención": "seq_ret",
    "Liquidación de Compra": "seq_liq",
    "Guía de Remisión": "seq_gr",
}

def handle_pe_delete(doc, method=None):
    """
    Triggered when a SRI Puntos Emision row is deleted.
    - If docs exist, reseeds next sequential to max+1.
    - If no docs exist, warns user that manual Init is required.
    """
    warehouse = doc.parent
    pe_code = doc.emission_point_code

    frappe.logger("josfe").info(f"Deleting PE row: WH={warehouse}, PE={pe_code}")

    any_updated = False

    for doctype, seq_field in DOC_MAP.items():
        try:
            res = frappe.db.sql(f"""
                SELECT MAX(sri_sequential_assigned) as max_seq
                FROM `tab{doctype}`
                WHERE docstatus = 1
                  AND sri_emission_point_code = %s
                  AND sri_establishment_code = (
                        SELECT custom_establishment_code
                        FROM `tabWarehouse`
                        WHERE name = %s
                  )
            """, (pe_code, warehouse), as_dict=True)

            max_seq = res[0].get("max_seq") if res else None
            if max_seq:
                next_seq = int(max_seq) + 1
                frappe.db.sql(f"""
                    UPDATE `tabSRI Puntos Emision`
                    SET {seq_field} = %s
                    WHERE parent = %s AND emission_point_code = %s
                """, (next_seq, warehouse, pe_code))
                frappe.logger("josfe").info(
                    f"Re-seeded {doctype} seq to {next_seq} for {warehouse}/{pe_code}"
                )
                any_updated = True

        except Exception as e:
            frappe.log_error(f"PE delete hook failed for {doctype}", str(e))

    if not any_updated:
        # No docs exist for this PE → manual init is needed
        frappe.msgprint(
            f"No existen documentos emitidos para PE {pe_code} en {warehouse}. "
            "Debe inicializar manualmente los secuenciales con el botón Init/Edit."
        )

    frappe.db.commit()
