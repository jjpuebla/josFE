import frappe

def has_emitted_docs(est_code: str, ep_code: str) -> bool:
    """Return True if any SRI docs exist for this establishment+emission point (EC-EP)."""

    # normalize to 3 digits
    est_code = str(est_code).zfill(3)
    ep_code = str(ep_code).zfill(3)
    prefix = f"{est_code}-{ep_code}-"

    doctypes = [
        "Sales Invoice",           # Factura
        "Guias Remision",          # Guía de Remisión
        "Liquidaciones Compra",    # Liquidación de Compra
        "Comprobantes Retencion",  # Comprobante de Retención
    ]

    for dt in doctypes:
        rows = frappe.get_all(
            dt,
            filters={"name": ["like", f"{prefix}%"]},
            fields=["name"],
            limit=1
        )
        if rows:
            frappe.log_error(
                title="SRI DEBUG has_emitted_docs",
                message=f"✅ Found {dt} for {prefix} → {rows}"
            )
            return True

    frappe.log_error(
        title="SRI DEBUG has_emitted_docs",
        message=f"❌ No docs found for {prefix}"
    )
    return False

@frappe.whitelist()
def can_delete_pe(warehouse_name: str, emission_point_code: str) -> bool:
    """Return True if PE can be safely deleted (no docs exist)."""

    est_code = frappe.get_value("Warehouse", warehouse_name, "custom_establishment_code")

    if not est_code:
        frappe.log_error(
            title="SRI DEBUG can_delete_pe",
            message=f"WH={warehouse_name} has no EC → allow delete"
        )
        return True

    result = not has_emitted_docs(est_code, emission_point_code)

    frappe.log_error(
        title="SRI DEBUG can_delete_pe",
        message=f"WH={warehouse_name} EC={est_code} EP={emission_point_code} result={result}"
    )
    return result
