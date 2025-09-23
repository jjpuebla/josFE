import frappe
from frappe import _
import re
# from josfe.sri_invoicing.core.numbering.state import peek_next

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

