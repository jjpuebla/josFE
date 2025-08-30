import frappe
from frappe.utils import now_datetime

def xml_queue_autoname(doc, method=None):
    """
    Autoname for SRI XML Queue.
    Format: XML-{EC}-{YY}-{#####}
    - EC: establishment code (3 digits)
    - YY: 2-digit year
    - ##### sequential counter (per EC+Year, resets every January 1st)
    """
    ec = getattr(doc, "custom_jos_ec_code", None)
    if not ec:
        frappe.throw("Falta el código de establecimiento (custom_jos_ec_code).")

    # Two-digit year suffix
    year = now_datetime().year % 100
    prefix = f"XML-{ec}-{year:02d}-"

    # Lock table to avoid race conditions (multi-user safety)
    frappe.db.sql("LOCK TABLES `tabSRI XML Queue` WRITE")

    try:
        # Only count within current EC+Year prefix
        last = frappe.db.sql(
            """
            SELECT name FROM `tabSRI XML Queue`
            WHERE name LIKE %s
            ORDER BY name DESC
            LIMIT 1
            """,
            (f"{prefix}%",),
            as_dict=True,
        )

        if last:
            try:
                last_seq = int(last[0].name.split("-")[-1])
            except Exception:
                last_seq = 0
        else:
            last_seq = 0

        # Next sequential
        next_seq = last_seq + 1
        doc.name = f"{prefix}{next_seq:05d}"

    finally:
        frappe.db.sql("UNLOCK TABLES")
