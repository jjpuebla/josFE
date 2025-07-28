import frappe
from josfe.taxidvalidator.ec_tax_validator import validate_and_assign_tax_id

def validate(doc, method):
    frappe.log_error(f"✔️ validate: {doc.name}", "🔥 Customer.validate [Tax_Id_Validador]")

    validate_and_assign_tax_id(doc, "custom_jos_tax_id_validador", assign_tax_id=True, assign_customer_type=True)

