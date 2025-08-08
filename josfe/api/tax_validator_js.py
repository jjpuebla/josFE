import frappe
from josfe.taxidvalidator.ec_tax_validator import is_valid_ec_tax_id

@frappe.whitelist()
def validate_tax_id_js(value, doctype):
    value = value.strip().upper()

    if value.startswith("P-"):
        return {"status": "valid", "value": value[2:]}

    if value == "9999999999999":
        return {"status": "valid", "value": value}

    if not is_valid_ec_tax_id(value):
        return {"status": "invalid"}

    if doctype == "Customer" and frappe.db.exists("Customer", {"tax_id": value}):
        return {"status": "duplicate"}

    if doctype == "Company" and frappe.db.exists("Company", {"tax_id": value}):
        return {"status": "duplicate"}

    if doctype == "Supplier" and frappe.db.exists("Supplier", {"tax_id": value}):
        return {"status": "duplicate"}

    return {"status": "valid", "value": value}

    
@frappe.whitelist()
def prevent_tax_id_change(doc, method):
    # Only prevent changes if the document is not new (already saved)
    if doc.is_new():
        return

    # Check if tax_id is being changed
    if not doc.get("tax_id"):
        return

    old_doc = frappe.get_doc(doc.doctype, doc.name)
    if old_doc.tax_id and old_doc.tax_id != doc.tax_id:
        frappe.throw("El campo Tax ID no puede ser modificado una vez guardado.")

    # Check if custom tax ID field is being changed
    custom_field = {
        "Customer": "custom_jos_tax_id_validador",
        "Supplier": "custom_jos_ruc_supplier",
        "Company": "custom_jos_ruc",
    }.get(doc.doctype)

    if custom_field:
        if old_doc.get(custom_field) and old_doc.get(custom_field) != doc.get(custom_field):
            frappe.throw("El campo de identificación tributaria no puede ser modificado.")
