import frappe
from frappe import _

@frappe.whitelist()
def get_source_invoice_items(source_name: str) -> dict:
    """
    Return a safe, minimal projection of items from a submitted (non-return) Sales Invoice.
    """
    if not source_name:
        return {"items": []}

    si = frappe.get_doc("Sales Invoice", source_name)

    # guard rails
    if not si.docstatus == 1:
        frappe.throw(_("Source Sales Invoice must be submitted."))
    if getattr(si, "is_return", 0):
        frappe.throw(_("Source Sales Invoice cannot be a return."))

    # (G) You can extend this list if your posting flow needs more fields.
    fields = [
        "item_code", "item_name", "description",
        "uom", "stock_uom", "conversion_factor",
        "warehouse",
        "rate", "price_list_rate",
        "discount_percentage", "discount_amount",
        "item_tax_template",
        "income_account", "cost_center",
        "batch_no", "serial_no",
    ]

    items = []
    for it in si.items:
        row = {f: it.get(f) for f in fields}
        # For a return, ERPNext typically expects negative quantities.
        # We'll pass the *original* qty to the client and let client set the sign when `is_return=1`.
        row["qty"] = it.get("qty") or 0
        items.append(row)

    return {"items": items}
