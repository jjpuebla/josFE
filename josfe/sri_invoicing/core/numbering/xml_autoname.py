import frappe
from frappe.utils import now_datetime

def xml_queue_autoname(doc, method=None):
    """
    Autoname for SRI XML Queue.
    Format: XML-{EC}-{YY}-{#####}
    - EC: establishment code (3 digits) from Warehouse.custom_establishment_code
    - YY: 2-digit year
    - #####: per-EC+Year counter
    """
    # 1) Resolve Warehouse on the queue row or from the referenced document
    wh = getattr(doc, "custom_jos_level3_warehouse", None)

    if not wh and getattr(doc, "sales_invoice", None):
        wh = frappe.db.get_value("Sales Invoice", doc.sales_invoice, "custom_jos_level3_warehouse")

    if not wh and getattr(doc, "reference_doctype", None) == "Nota Credito FE":
        wh = frappe.db.get_value("Nota Credito FE", getattr(doc, "reference_name", None), "custom_jos_level3_warehouse")

    # 2) Establishment from Warehouse
    ec = frappe.get_cached_value("Warehouse", wh, "custom_establishment_code") if wh else None
    if not ec:
        frappe.throw("Falta el código de establecimiento en el Warehouse (custom_establishment_code). Seleccione una Sucursal válida.")

    # 3) Prefix: XML-EC-YY-
    year = now_datetime().year % 100
    prefix = f"XML-{ec}-{year:02d}-"

    # 4) Allocate next sequential within prefix
    frappe.db.sql("LOCK TABLES `tabSRI XML Queue` WRITE")
    try:
        row = frappe.db.sql(
            """
            SELECT name
            FROM `tabSRI XML Queue`
            WHERE name LIKE %s
            ORDER BY name DESC
            LIMIT 1
            """,
            (f"{prefix}%",),
            as_dict=True,
        )
        last_seq = 0
        if row:
            try:
                last_seq = int(row[0].name.split("-")[-1])
            except Exception:
                last_seq = 0
        doc.name = f"{prefix}{last_seq + 1:05d}"
    finally:
        frappe.db.sql("UNLOCK TABLES")
