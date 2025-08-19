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

# --- SRI serie preview (non-allocating) ----------------------------------------
import re

def _z3(v: str) -> str:
    """Normalize to 3-digit zero-padded code (accepts '001 - Foo')."""
    if v is None:
        return ""
    v = str(v).strip()
    v = v.split(" - ", 1)[0].strip() or v
    try:
        return f"{int(v):03d}"
    except Exception:
        # keep only digits if any, else empty
        digits = re.sub(r"\D", "", v)
        return digits.zfill(3) if digits else ""

def _z9(n: int) -> str:
    return f"{int(n):09d}"

@frappe.whitelist()
def peek_next_si_series(warehouse: str, pe_code: str) -> str:
    """
    Return preview 'EST-PE-#########' for Sales Invoice WITHOUT allocating.
    Uses last SI name for the same EST/PE to infer the next number.
    """
    if not warehouse or not pe_code:
        return ""

    est_raw = frappe.db.get_value("Warehouse", warehouse, "custom_establishment_code") or ""
    est = _z3(est_raw)
    pe  = _z3(pe_code)

    if not est or not pe:
        return ""

    # Try to infer next number from existing Sales Invoice names
    last = frappe.db.sql(
        """
        select name
        from `tabSales Invoice`
        where name like %s
        order by name desc
        limit 1
        """,
        (f"{est}-{pe}-%",),
    )

    next_num = 1
    if last and last[0][0]:
        try:
            suffix = last[0][0].rsplit("-", 1)[1]
            next_num = int(suffix) + 1
        except Exception:
            next_num = 1

    return f"{est}-{pe}-{_z9(next_num)}"
