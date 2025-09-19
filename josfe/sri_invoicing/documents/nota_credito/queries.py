# apps/josfe/josfe/sri_invoicing/credit_note/queries.py
import frappe
from frappe.utils import add_years, getdate, nowdate

@frappe.whitelist()
def si_last_12mo(doctype, txt, searchfield, start, page_len, filters):
    customer = (filters or {}).get("customer")
    company  = (filters or {}).get("company")
    if not customer:
        return []

    since = add_years(getdate(nowdate()), -1)

    invoices = frappe.get_all(
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
        start=start,
        page_length=page_len,
    )

    # format for Link field query: list of tuples
    return [
        (i["name"], f"{i['posting_date']} | {i['grand_total']} | {i['status']}")
        for i in invoices
    ]
