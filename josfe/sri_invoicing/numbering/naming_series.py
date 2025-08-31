import frappe
from frappe import _

@frappe.whitelist()
def get_naming_series_options_for(doctype):
    try:
        # First check for property setter override
        custom_series = frappe.db.get_value(
            "Property Setter",
            {
                "doc_type": doctype,
                "field_name": "naming_series",
                "property": "options"
            },
            "value"
        )

        if not custom_series:
            doc = frappe.get_doc("DocType", doctype)
            field = next((f for f in doc.fields if f.fieldname == "naming_series"), None)
            custom_series = field.options if field else ""

        series_list = [s.strip() for s in custom_series.split("\n") if s.strip()]
        return [{"name": s} for s in series_list]
    except Exception as e:
        frappe.throw(_("Error fetching naming series: {0}").format(str(e)))

@frappe.whitelist()
def get_address_for_warehouse(warehouse):
    try:
        # Get the linked address
        address_link = frappe.db.get_value(
            "Dynamic Link",
            {
                "link_doctype": "Warehouse",
                "link_name": warehouse,
                "parenttype": "Address"
            },
            "parent"
        )

        if not address_link:
            return ""

        return frappe.db.get_value("Address", address_link, "address_line1") or ""
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_address_for_warehouse")
        return ""

# --- SRI serie preview (authoritative, non-allocating) ---
import re
from josfe.sri_invoicing.numbering.state import peek_next

def z3(v: str) -> str:
    v = (v or "").strip().split(" - ", 1)[0]
    digits = re.sub(r"\D", "", v)
    return digits.zfill(3) if digits else ""

def z9(n: int) -> str:
    return f"{int(n):09d}"

@frappe.whitelist()
def peek_next_si_series(warehouse: str, pe_code: str) -> str:
    """
    Return 'EST-PE-#########' WITHOUT allocating,
    reading the stored 'next to issue' from the counter row.
    """
    if not warehouse or not pe_code:
        return ""

    est = z3(frappe.db.get_value("Warehouse", warehouse, "custom_establishment_code") or "")
    pe  = z3(pe_code)
    if not est or not pe:
        return ""

    nxt = peek_next(warehouse_name=warehouse, emission_point_code=pe, doc_type="Factura")
    return f"{est}-{pe}-{z9(nxt)}"