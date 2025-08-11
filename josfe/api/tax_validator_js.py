import frappe
from josfe.taxidvalidator.ec_tax_validator import enforce_tax_id_immutability

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

    
