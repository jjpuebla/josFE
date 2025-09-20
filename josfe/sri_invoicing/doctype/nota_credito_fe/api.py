import frappe
from frappe.utils import add_years, getdate, nowdate
from frappe import _

@frappe.whitelist()
def si_last_12mo(doctype, txt, searchfield, start, page_len, filters):
    customer = (filters or {}).get("customer")
    company  = (filters or {}).get("company")
    if not customer:
        return []
    since = add_years(getdate(nowdate()), -1)
    rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": customer,
            "company": company,
            "docstatus": 1,
            "is_return": 0,
            "posting_date": [">=", since],
        },
        fields=["name", "posting_date", "grand_total", "status"],
        order_by="posting_date desc",
        start=start, page_length=page_len,
    )
    return [
        (r["name"], f'{r["posting_date"]} | {r["grand_total"]} | {r["status"]}')
        for r in rows
    ]

@frappe.whitelist()
def get_source_invoice_items(source_name: str) -> dict:
    """Return items from a submitted (non-return) Sales Invoice."""
    if not source_name:
        return {"items": []}

    si = frappe.get_doc("Sales Invoice", source_name)

    if si.docstatus != 1:
        frappe.throw(_("Source Sales Invoice must be submitted."))
    if getattr(si, "is_return", 0):
        frappe.throw(_("Source Sales Invoice cannot be a return."))

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
        row["qty"] = it.get("qty") or 0
        items.append(row)

    return {"items": items}
