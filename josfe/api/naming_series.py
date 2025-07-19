import frappe
from frappe import _

@frappe.whitelist()
def get_naming_series_options_for(doctype):
    try:
        # Naming series are stored in tabSeries as keys like 'SINV-.YYYY.-'
        # Fetch allowed series from DocType's 'naming_series' field
        doc = frappe.get_doc("DocType", doctype)
        field = next((f for f in doc.fields if f.fieldname == "naming_series"), None)

        if field and field.options:
            series_list = [s.strip() for s in field.options.split("\n") if s.strip()]
            return [{"name": s} for s in series_list]
        else:
            return []
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